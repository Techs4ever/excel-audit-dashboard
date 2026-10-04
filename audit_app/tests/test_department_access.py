"""Department master data and dashboard Department-filter scope."""
from __future__ import annotations

import json

import pytest
from django.core.exceptions import ValidationError
from django.urls import reverse

from audit_app.department_access import (
    apply_department_scope_to_html,
    department_scope_tokens_for_dashboard,
)
from audit_app.models import Department, UserDepartmentAccess
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
    )
    Department.objects.create(name="HR")
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
    department = Department.objects.create(name="HR")
    UserDepartmentAccess.objects.create(user=viewer, department=department)
    assert department_scope_tokens_for_dashboard(viewer, dashboard) == ["HR"]


@pytest.mark.django_db
def test_creator_and_reviewer_are_not_department_scoped(btc_company):
    creator = make_user("full_creator")
    reviewer = make_user("full_reviewer")
    make_membership(reviewer, btc_company, can_review=True)
    dashboard = make_dashboard(btc_company, creator, name="Full")
    department = Department.objects.create(name="IT")
    UserDepartmentAccess.objects.create(user=creator, department=department)
    UserDepartmentAccess.objects.create(user=reviewer, department=department)
    assert department_scope_tokens_for_dashboard(creator, dashboard) is None
    assert department_scope_tokens_for_dashboard(reviewer, dashboard) is None


@pytest.mark.django_db
def test_department_name_is_unique_ignoring_case(btc_company):
    Department.objects.create(name="Finance")
    duplicate = Department(name=" finance ")
    with pytest.raises(ValidationError):
        duplicate.full_clean()


@pytest.mark.django_db
def test_admin_can_add_department(admin_client, btc_company):
    response = admin_client.post(
        reverse("admin:audit_app_department_add"),
        {
            "name": "Internal Audit",
            "excel_aliases": "IA\nالتدقيق الداخلي",
            "is_active": "on",
            "_save": "Save",
        },
    )
    assert response.status_code == 302, response.content[:500]
    department = Department.objects.get(name="Internal Audit")
    assert department.match_tokens() == ["Internal Audit", "IA", "التدقيق الداخلي"]


@pytest.mark.django_db
def test_removing_department_access_soft_deletes_the_link(admin_client, btc_company):
    user = make_user("unlink_dept", email="unlink_dept@example.com")
    department = Department.objects.create(name="Legal")
    access = UserDepartmentAccess.objects.create(user=user, department=department)
    response = admin_client.post(
        reverse("admin:auth_user_change", args=[user.pk]),
        {
            "username": user.username,
            "email": user.email,
            "first_name": "Test",
            "last_name": "User",
            "job_title": "Tester",
            "password_expiry_enabled": "on",
            "receive_workflow_emails": "on",
            "is_active": "on",
            "_save": "Save",
            "company_memberships-TOTAL_FORMS": "0",
            "company_memberships-INITIAL_FORMS": "0",
            "company_memberships-MIN_NUM_FORMS": "0",
            "company_memberships-MAX_NUM_FORMS": "1000",
            "department_accesses-TOTAL_FORMS": "1",
            "department_accesses-INITIAL_FORMS": "1",
            "department_accesses-MIN_NUM_FORMS": "0",
            "department_accesses-MAX_NUM_FORMS": "1000",
            "department_accesses-0-id": str(access.pk),
            "department_accesses-0-department": str(department.pk),
            "department_accesses-0-DELETE": "on",
        },
    )
    assert response.status_code == 302, response.content[:800]
    access.refresh_from_db()
    assert access.is_deleted is True
    assert UserDepartmentAccess.objects.filter(pk=access.pk).exists()


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
