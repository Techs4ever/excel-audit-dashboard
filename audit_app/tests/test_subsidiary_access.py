"""Subsidiary visibility grants and dashboard company-filter scope."""
from __future__ import annotations

import json

import pytest
from django.urls import reverse

from audit_app.models import COMPANY_KIND_SUBSIDIARY, Company, UserSubsidiaryAccess
from audit_app.subsidiary_access import (
    apply_subsidiary_scope_to_html,
    filter_rows_by_subsidiary_scope,
    subsidiary_scope_tokens_for_dashboard,
)
from reports_app.services.report_generation import inject_dashboard_serve_context
from tests.factories import make_dashboard, make_membership, make_user


def _aum(parent):
    return Company.objects.create(
        code="SUBA",
        name="AUM Unit",
        excel_company_names=["AUM"],
        company_kind=COMPANY_KIND_SUBSIDIARY,
        parent=parent,
    )


def _payload_html() -> str:
    payload = {
        "audit_observation": {
            "rows": [
                {"sco": "AUM", "obs": "aum-row"},
                {"sco": "AUM Unit", "obs": "alias-row"},
                {"sco": "NAT", "obs": "nat-row"},
                {"sco": "OTHER", "obs": "other-row"},
            ],
            "filter_dims": [
                {"key": "y", "values": ["2024"]},
                {"key": "sco", "label": "Subcompany", "values": ["AUM", "NAT", "OTHER"]},
            ],
        }
    }
    return "<html><body><script>const payload = " + json.dumps(payload) + ";</script></body></html>"


@pytest.mark.django_db
def test_assigned_viewer_sees_only_granted_subsidiaries(nat_company):
    creator = make_user("sub_creator")
    viewer = make_user("sub_viewer")
    make_membership(viewer, nat_company)
    dashboard = make_dashboard(nat_company, creator, name="NAT dash")
    aum = _aum(nat_company)
    UserSubsidiaryAccess.objects.create(user=viewer, company=aum)

    tokens = subsidiary_scope_tokens_for_dashboard(viewer, dashboard)
    assert tokens == ["SUBA", "AUM Unit", "AUM"]

    scoped = apply_subsidiary_scope_to_html(_payload_html(), tokens)
    start = scoped.index("const payload = ") + len("const payload = ")
    payload, _end = json.JSONDecoder().raw_decode(scoped, start)
    rows = payload["audit_observation"]["rows"]
    assert [row["obs"] for row in rows] == ["aum-row", "alias-row"]
    dims = {dim["key"]: dim["values"] for dim in payload["audit_observation"]["filter_dims"]}
    assert dims["sco"] == ["AUM"]
    assert dims["y"] == ["2024"]
    assert "other-row" not in scoped


@pytest.mark.django_db
def test_parent_and_subsidiary_can_both_be_granted(nat_company):
    creator = make_user("both_creator")
    viewer = make_user("both_viewer")
    make_membership(viewer, nat_company)
    dashboard = make_dashboard(nat_company, creator, name="Both")
    aum = _aum(nat_company)
    UserSubsidiaryAccess.objects.create(user=viewer, company=nat_company)
    UserSubsidiaryAccess.objects.create(user=viewer, company=aum)

    tokens = subsidiary_scope_tokens_for_dashboard(viewer, dashboard)
    scoped = apply_subsidiary_scope_to_html(_payload_html(), tokens)
    start = scoped.index("const payload = ") + len("const payload = ")
    payload, _end = json.JSONDecoder().raw_decode(scoped, start)
    assert [row["obs"] for row in payload["audit_observation"]["rows"]] == [
        "aum-row",
        "alias-row",
        "nat-row",
    ]


@pytest.mark.django_db
def test_user_without_subsidiary_grants_keeps_full_dashboard(nat_company):
    creator = make_user("open_sub_creator")
    viewer = make_user("open_sub_viewer")
    make_membership(viewer, nat_company)
    dashboard = make_dashboard(nat_company, creator, name="Open")
    _aum(nat_company)
    assert subsidiary_scope_tokens_for_dashboard(viewer, dashboard) is None


@pytest.mark.django_db
def test_creator_and_reviewer_are_not_subsidiary_scoped(nat_company):
    creator = make_user("full_sub_creator")
    reviewer = make_user("full_sub_reviewer")
    make_membership(reviewer, nat_company, can_review=True)
    dashboard = make_dashboard(nat_company, creator, name="Full")
    aum = _aum(nat_company)
    UserSubsidiaryAccess.objects.create(user=creator, company=aum)
    UserSubsidiaryAccess.objects.create(user=reviewer, company=aum)
    assert subsidiary_scope_tokens_for_dashboard(creator, dashboard) is None
    assert subsidiary_scope_tokens_for_dashboard(reviewer, dashboard) is None


@pytest.mark.django_db
def test_grant_on_another_tenant_does_not_scope_this_dashboard(btc_company, nat_company):
    creator = make_user("cross_sub_creator")
    viewer = make_user("cross_sub_viewer")
    make_membership(viewer, btc_company)
    dashboard = make_dashboard(btc_company, creator, name="BTC")
    aum = _aum(nat_company)
    UserSubsidiaryAccess.objects.create(user=viewer, company=aum)
    assert subsidiary_scope_tokens_for_dashboard(viewer, dashboard) is None


def test_preview_table_keeps_only_granted_subcompany():
    html = """
    <table class='preview-filter-table'><thead><tr>
      <th><span class="preview-col-label">Subcompany</span>
        <select class="preview-col-filter preview-col-filter--select" data-col-idx="0" data-filter-mode="select" aria-label="Subcompany">
          <option value="">All (3)</option>
          <option value="AUM">AUM (1)</option>
          <option value="NAT">NAT (1)</option>
          <option value="OTHER">OTHER (1)</option>
        </select>
      </th>
      <th><span class="preview-col-label">Department</span>
        <select class="preview-col-filter preview-col-filter--select" data-col-idx="1" data-filter-mode="select" aria-label="Department">
          <option value="">All (3)</option>
          <option value="HR">HR (2)</option>
          <option value="IT">IT (1)</option>
        </select>
      </th>
    </tr></thead><tbody>
      <tr><td>AUM</td><td>HR</td></tr>
      <tr><td>NAT</td><td>HR</td></tr>
      <tr><td>OTHER</td><td>IT</td></tr>
    </tbody></table>
    """
    scoped = apply_subsidiary_scope_to_html(html, ["AUM"])
    assert scoped.count("<tr><td>AUM</td><td>HR</td></tr>") == 1
    assert ">NAT<" not in scoped
    assert "OTHER" not in scoped
    assert ">IT<" not in scoped
    assert "HR (1)" in scoped
    assert "All (1)" in scoped


def test_snapshot_pack_keeps_only_granted_subsidiary_rows():
    pack = {
        "rows": [
            {"الشركة التابعة": "AUM", "النص النظامي": "نص أ"},
            {"الشركة التابعة": "NAT", "النص النظامي": "نص ب"},
        ],
        "legal_details": {"نص أ": {"ok": 1}, "نص ب": {"ok": 2}},
    }
    html = '<script type="application/json" id="snapshot-pack">' + json.dumps(pack, ensure_ascii=False) + "</script>"
    scoped = apply_subsidiary_scope_to_html(html, ["AUM"])
    start = scoped.index('id="snapshot-pack">') + len('id="snapshot-pack">')
    loaded, _end = json.JSONDecoder().raw_decode(scoped, start)
    assert loaded["rows"] == [{"الشركة التابعة": "AUM", "النص النظامي": "نص أ"}]
    assert list(loaded["legal_details"]) == ["نص أ"]


def test_rows_without_subsidiary_column_stay_intact():
    rows = [{"الإدارة المسؤولة": "HR"}, {"الإدارة المسؤولة": "IT"}]
    assert filter_rows_by_subsidiary_scope(rows, ["AUM"]) == rows


def test_serve_context_applies_subsidiary_scope():
    html = _payload_html().replace("<html>", "<html><head></head>")
    out = inject_dashboard_serve_context(
        html,
        mail_url="http://test/api/mail",
        plan_url="http://test/api/plan",
        user_edits_save_url="",
        can_save_user_edits=False,
        subsidiary_scope_tokens=["NAT"],
    )
    start = out.index("const payload = ") + len("const payload = ")
    payload, _end = json.JSONDecoder().raw_decode(out, start)
    assert [row["obs"] for row in payload["audit_observation"]["rows"]] == ["nat-row"]


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
def test_user_form_lists_parent_and_subsidiaries(admin_client, nat_company, btc_company):
    user = make_user("sub_ui", email="sub_ui@example.com")
    make_membership(user, nat_company)
    aum = _aum(nat_company)
    other = Company.objects.create(
        code="ZZZ",
        name="Other Child",
        company_kind=COMPANY_KIND_SUBSIDIARY,
        parent=btc_company,
    )
    response = admin_client.get(reverse("admin:auth_user_change", args=[user.pk]))
    assert response.status_code == 200
    content = response.content.decode()
    assert "password_rules.js" in content
    assert "admin_company_subsidiary_access.js" in content
    assert 'name="company_memberships-0-subsidiary_access"' in content
    assert f'value="{nat_company.pk}"' in content
    assert f'value="{aum.pk}"' in content
    assert "AUM" in content
    box = content.split('class="subsidiary-access', 1)[1].split("</ul>", 1)[0]
    assert f'value="{other.pk}"' not in box
    company_at = content.find("field-company")
    subsidiary_at = content.find("field-subsidiary_access")
    template_at = content.find("field-template_permissions")
    assert 0 <= company_at < subsidiary_at < template_at


@pytest.mark.django_db
def test_user_form_hides_subsidiary_checks_when_company_has_no_children(
    admin_client, btc_company
):
    user = make_user("no_child_ui", email="no_child_ui@example.com")
    make_membership(user, btc_company)
    response = admin_client.get(reverse("admin:auth_user_change", args=[user.pk]))
    content = response.content.decode()
    assert "subsidiary-access is-empty" in content
    assert "password_rules.js" in content


@pytest.mark.django_db
def test_admin_can_grant_and_clear_subsidiary_access(admin_client, nat_company):
    user = make_user("grant_sub", email="grant_sub@example.com")
    membership = make_membership(user, nat_company)
    aum = _aum(nat_company)
    grant = admin_client.post(
        reverse("admin:auth_user_change", args=[user.pk]),
        _user_change_post(
            user,
            membership,
            **{
                "company_memberships-0-subsidiary_access": [
                    str(nat_company.pk),
                    str(aum.pk),
                ]
            },
        ),
    )
    assert grant.status_code == 302, grant.content[:800]
    granted = set(
        UserSubsidiaryAccess.objects.filter(user=user, is_deleted=False).values_list(
            "company_id", flat=True
        )
    )
    assert granted == {nat_company.pk, aum.pk}

    clear = admin_client.post(
        reverse("admin:auth_user_change", args=[user.pk]),
        _user_change_post(user, membership),
    )
    assert clear.status_code == 302, clear.content[:800]
    assert not UserSubsidiaryAccess.objects.filter(user=user, is_deleted=False).exists()
    assert UserSubsidiaryAccess.objects.filter(user=user, is_deleted=True).count() == 2
