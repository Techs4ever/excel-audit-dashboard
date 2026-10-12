"""Department master data and dashboard Department-filter scope."""
from __future__ import annotations

import json
import re

import pytest
from django.core.exceptions import ValidationError
from django.urls import reverse

from audit_app.department_access import (
    apply_department_scope_to_html,
    department_scope_tokens_for_dashboard,
)
from audit_app.models import COMPANY_KIND_SUBSIDIARY, Company, Department, UserDepartmentAccess
from reports_app.services.report_generation import inject_dashboard_serve_context
from tests.factories import make_dashboard, make_membership, make_user


def _payload_html() -> str:
    payload = {
        "audit_observation": {
            "rows": [
                {"d": "IT", "obs": "keep"},
                {"d": "HR", "obs": "hide"},
                {"d": "  it ", "obs": "keep-alias-case"},
            ],
            "filter_dims": [
                {"key": "y", "values": ["2024"]},
                {"key": "d", "label": "Department", "values": ["HR", "IT", "Finance"]},
            ],
        }
    }
    return "<html><body><script>const payload = " + json.dumps(payload) + ";</script></body></html>"


@pytest.mark.django_db
def test_assigned_viewer_department_scope_limits_filter(btc_company):
    creator = make_user("dept_creator")
    viewer = make_user("dept_viewer")
    make_membership(viewer, btc_company)
    dashboard = make_dashboard(btc_company, creator, name="Scoped")
    department = Department.objects.create(
        name="IT",
        excel_aliases="Information Technology",
        company=btc_company,
    )
    Department.objects.create(name="HR", company=btc_company)
    UserDepartmentAccess.objects.create(user=viewer, department=department)

    tokens = department_scope_tokens_for_dashboard(viewer, dashboard)
    assert tokens == ["IT", "Information Technology"]

    scoped = apply_department_scope_to_html(_payload_html(), tokens)
    start = scoped.index("const payload = ") + len("const payload = ")
    payload, _end = json.JSONDecoder().raw_decode(scoped, start)
    rows = payload["audit_observation"]["rows"]
    assert [row["obs"] for row in rows] == ["keep", "keep-alias-case"]
    dims = {dim["key"]: dim["values"] for dim in payload["audit_observation"]["filter_dims"]}
    assert dims["d"] == ["IT"]
    assert dims["y"] == ["2024"]
    assert "HR" not in scoped.split("const payload = ", 1)[1]


@pytest.mark.django_db
def test_user_without_departments_keeps_full_filter(btc_company):
    creator = make_user("open_creator")
    viewer = make_user("open_viewer")
    make_membership(viewer, btc_company)
    dashboard = make_dashboard(btc_company, creator, name="Open")
    assert department_scope_tokens_for_dashboard(viewer, dashboard) is None


@pytest.mark.django_db
def test_uploader_viewing_another_dashboard_is_department_scoped(btc_company):
    creator = make_user("upload_creator")
    viewer = make_user("upload_viewer")
    make_membership(viewer, btc_company, can_upload=True)
    dashboard = make_dashboard(btc_company, creator, name="Assigned")
    department = Department.objects.create(name="HR", company=btc_company)
    UserDepartmentAccess.objects.create(user=viewer, department=department)
    assert department_scope_tokens_for_dashboard(viewer, dashboard) == ["HR"]


@pytest.mark.django_db
def test_creator_and_reviewer_are_not_department_scoped(btc_company):
    creator = make_user("full_creator")
    reviewer = make_user("full_reviewer")
    make_membership(reviewer, btc_company, can_review=True)
    dashboard = make_dashboard(btc_company, creator, name="Full")
    department = Department.objects.create(name="IT", company=btc_company)
    UserDepartmentAccess.objects.create(user=creator, department=department)
    UserDepartmentAccess.objects.create(user=reviewer, department=department)
    assert department_scope_tokens_for_dashboard(creator, dashboard) is None
    assert department_scope_tokens_for_dashboard(reviewer, dashboard) is None


@pytest.mark.django_db
def test_department_name_is_unique_ignoring_case(btc_company):
    Department.objects.create(name="Finance", company=btc_company)
    duplicate = Department(name=" finance ", company=btc_company)
    with pytest.raises(ValidationError):
        duplicate.full_clean()


@pytest.mark.django_db
def test_same_department_name_is_allowed_for_another_company(btc_company, nat_company):
    Department.objects.create(name="HR", company=btc_company)
    other = Department(name="HR", company=nat_company)
    other.full_clean()
    other.save()
    assert Department.objects.filter(name="HR", is_deleted=False).count() == 2


def _tiny_logo():
    from io import BytesIO

    from django.core.files.uploadedfile import SimpleUploadedFile
    from PIL import Image

    buffer = BytesIO()
    Image.new("RGB", (8, 8), color="blue").save(buffer, format="PNG")
    return SimpleUploadedFile("logo.png", buffer.getvalue(), content_type="image/png")


@pytest.mark.django_db
def test_admin_can_add_department(admin_client, btc_company):
    payload = {
        "code": btc_company.code,
        "name": btc_company.name,
        "company_kind": "main",
        "is_active": "on",
        "excel_company_names": "[]",
        "use_workflow_v2": "on",
        "notify_creator_on_publish": "on",
        "departments-TOTAL_FORMS": "1",
        "departments-INITIAL_FORMS": "0",
        "departments-MIN_NUM_FORMS": "0",
        "departments-MAX_NUM_FORMS": "1000",
        "departments-0-name": "Internal Audit",
        "departments-0-excel_aliases": "IA\nالتدقيق الداخلي",
        "departments-0-is_active": "on",
        "_save": "Save",
    }
    if not btc_company.logo:
        payload["logo"] = _tiny_logo()
    response = admin_client.post(
        reverse("admin:audit_app_company_change", args=[btc_company.pk]),
        payload,
    )
    assert response.status_code == 302, response.content[:800]
    department = Department.objects.get(name="Internal Audit")
    assert department.company_id == btc_company.pk
    assert department.match_tokens() == ["Internal Audit", "IA", "التدقيق الداخلي"]


@pytest.mark.django_db
def test_departments_are_edited_on_the_main_company_above_attachments(
    admin_client, btc_company
):
    Department.objects.create(name="BTC HR", company=btc_company)
    subsidiary = Company.objects.create(
        code="SUBCO",
        name="Subsidiary Co",
        company_kind=COMPANY_KIND_SUBSIDIARY,
        parent=btc_company,
    )
    main_page = admin_client.get(
        reverse("admin:audit_app_company_change", args=[btc_company.pk])
    )
    assert main_page.status_code == 200
    main_html = main_page.content.decode()
    departments_at = main_html.find('id="departments-heading"')
    attachments_at = main_html.find("company-attachments")
    assert 0 <= departments_at < attachments_at
    assert "BTC HR" in main_html
    assert "field-company" not in main_html[departments_at:attachments_at]

    subsidiary_page = admin_client.get(
        reverse("admin:audit_app_company_change", args=[subsidiary.pk])
    )
    assert subsidiary_page.status_code == 200
    subsidiary_html = subsidiary_page.content.decode()
    assert "departments-group" not in subsidiary_html
    assert "BTC HR" in subsidiary_html
    assert "company-inherited-departments" in subsidiary_html

    duplicate = Department(name="HR", company=subsidiary)
    with pytest.raises(ValidationError):
        duplicate.full_clean()


def _user_change_post(user, membership, **extra):
    payload = {
        "username": user.username,
        "email": user.email,
        "first_name": "Test",
        "last_name": "User",
        "job_title": "Tester",
        "password_expiry_enabled": "on",
        "receive_workflow_emails": "on",
        "is_active": "on",
        "_save": "Save",
        "company_memberships-TOTAL_FORMS": "1",
        "company_memberships-INITIAL_FORMS": "1",
        "company_memberships-MIN_NUM_FORMS": "0",
        "company_memberships-MAX_NUM_FORMS": "1000",
        "company_memberships-0-id": str(membership.pk),
        "company_memberships-0-company": str(membership.company_id),
    }
    payload.update(extra)
    return payload


@pytest.mark.django_db
def test_membership_selector_grants_and_removes_company_departments(
    admin_client, btc_company, nat_company
):
    user = make_user("unlink_dept", email="unlink_dept@example.com")
    membership = make_membership(user, btc_company)
    legal = Department.objects.create(name="Legal", company=btc_company)
    hr = Department.objects.create(name="HR", company=btc_company)
    nat_hr = Department.objects.create(name="HR", company=nat_company)
    access = UserDepartmentAccess.objects.create(user=user, department=legal)
    grant = admin_client.post(
        reverse("admin:auth_user_change", args=[user.pk]),
        _user_change_post(
            user,
            membership,
            **{"company_memberships-0-department_access": str(hr.pk)},
        ),
    )
    assert grant.status_code == 302, grant.content[:800]
    access.refresh_from_db()
    assert access.is_deleted is True
    granted = UserDepartmentAccess.objects.get(user=user, department=hr)
    assert granted.is_deleted is False
    assert not UserDepartmentAccess.objects.filter(user=user, department=nat_hr).exists()

    remove = admin_client.post(
        reverse("admin:auth_user_change", args=[user.pk]),
        _user_change_post(user, membership),
    )
    assert remove.status_code == 302, remove.content[:800]
    granted.refresh_from_db()
    assert granted.is_deleted is True
    assert UserDepartmentAccess.objects.filter(user=user, department=hr).exists()


@pytest.mark.django_db
def test_user_form_lists_only_that_companys_departments(
    admin_client, btc_company, nat_company
):
    user = make_user("scoped_dept_ui", email="scoped_dept_ui@example.com")
    make_membership(user, btc_company)
    btc_hr = Department.objects.create(name="BTC HR", company=btc_company)
    nat_hr = Department.objects.create(name="NAT HR", company=nat_company)
    response = admin_client.get(reverse("admin:auth_user_change", args=[user.pk]))
    assert response.status_code == 200
    content = response.content.decode()
    match = re.search(
        r'<select[^>]*id="id_company_memberships-0-department_access"[^>]*>(.*?)</select>',
        content,
        re.S,
    )
    assert match, content[content.find("department_access") - 200:content.find("department_access") + 400]
    options = match.group(1)
    assert f'value="{btc_hr.pk}"' in options
    assert "BTC HR" in options
    assert "NAT HR" not in options
    assert f'value="{nat_hr.pk}"' not in options
    assert "NAT HR" in content
    assert "department_accesses-group" not in content
    assert "password_rules.js" in content


@pytest.mark.django_db
def test_other_company_grant_does_not_scope_this_dashboard(btc_company, nat_company):
    creator = make_user("cross_creator")
    viewer = make_user("cross_viewer")
    make_membership(viewer, btc_company)
    dashboard = make_dashboard(btc_company, creator, name="Cross")
    nat_hr = Department.objects.create(name="HR", company=nat_company)
    UserDepartmentAccess.objects.create(user=viewer, department=nat_hr)
    assert department_scope_tokens_for_dashboard(viewer, dashboard) is None
    btc_hr = Department.objects.create(name="HR", company=btc_company)
    UserDepartmentAccess.objects.create(user=viewer, department=btc_hr)
    assert department_scope_tokens_for_dashboard(viewer, dashboard) == ["HR"]


def test_preview_table_keeps_only_granted_department():
    html = """
    <table class='preview-filter-table'><thead><tr>
      <th><span class="preview-col-label">Department</span>
        <select class="preview-col-filter preview-col-filter--select" data-col-idx="0" data-filter-mode="select" aria-label="Department">
          <option value="">All (3)</option>
          <option value="Finance">Finance (1)</option>
          <option value="HR">HR (1)</option>
          <option value="IT">IT (1)</option>
        </select>
      </th>
      <th><span class="preview-col-label">Audit Cycle/ Department</span>
        <select class="preview-col-filter preview-col-filter--select" data-col-idx="1" data-filter-mode="select" aria-label="Audit Cycle/ Department">
          <option value="">All (3)</option>
          <option value="Cycle A">Cycle A (2)</option>
          <option value="Cycle B">Cycle B (1)</option>
        </select>
      </th>
    </tr></thead><tbody>
      <tr><td>Finance</td><td>Cycle A</td></tr>
      <tr><td>HR</td><td>Cycle A</td></tr>
      <tr><td>IT</td><td>Cycle B</td></tr>
    </tbody></table>
    """
    scoped = apply_department_scope_to_html(html, ["HR"])
    assert scoped.count("<tr><td>HR</td><td>Cycle A</td></tr>") == 1
    assert "Finance" not in scoped
    assert ">IT<" not in scoped
    assert "Cycle B" not in scoped
    assert "Cycle A (1)" in scoped
    assert "All (1)" in scoped


def test_serve_context_applies_department_scope():
    html = _payload_html().replace("<html>", "<html><head></head>")
    out = inject_dashboard_serve_context(
        html,
        mail_url="http://test/api/mail",
        plan_url="http://test/api/plan",
        user_edits_save_url="",
        can_save_user_edits=False,
        department_scope_tokens=["HR"],
    )
    start = out.index("const payload = ") + len("const payload = ")
    payload, _end = json.JSONDecoder().raw_decode(out, start)
    assert [row["obs"] for row in payload["audit_observation"]["rows"]] == ["hide"]
