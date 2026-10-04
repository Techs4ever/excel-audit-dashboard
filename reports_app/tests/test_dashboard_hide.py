"""Hidden dashboards are invisible except to the per-template hide permission."""
from __future__ import annotations

from django.contrib.auth.models import User
from django.test import Client, TestCase

from audit_app.dashboard_template_codes import TEMPLATE_CODE_CD, TEMPLATE_CODE_IAD
from audit_app.models import (
    MEMBERSHIP_PERM_FIELDS,
    Company,
    Dashboard,
    DashboardStatus,
    apply_membership_template_accesses,
    known_template_codes,
)
from dashboard_locale import tr
from reports_app.dashboard_workflow import (
    dashboards_queryset_for_user,
    user_can_see_dashboard,
)
from tests.factories import make_membership, make_user


def _grant_hide(user, company, template_code: str) -> None:
    membership = user.company_memberships.get(company=company, is_deleted=False)
    access = {}
    for code in known_template_codes():
        flags = {field: False for field in MEMBERSHIP_PERM_FIELDS}
        if code == template_code:
            flags["can_hide_dashboards"] = True
        access[code] = flags
    apply_membership_template_accesses(membership, access)


class DashboardHideTests(TestCase):
    def setUp(self):
        self.company, _ = Company.objects.get_or_create(
            code="BTC",
            defaults={"name": "BTC", "excel_company_names": ["BTC"]},
        )
        self.creator = make_user("hide_creator")
        make_membership(self.creator, self.company, can_upload=True)
        self.hider = make_user("hide_holder")
        make_membership(self.hider, self.company)
        _grant_hide(self.hider, self.company, TEMPLATE_CODE_IAD)
        self.dashboard = Dashboard.objects.create(
            name="Visible Plan",
            report_id="rid-hide-visible",
            company=self.company,
            created_by=self.creator,
            status=DashboardStatus.PUBLISHED,
            template_type=TEMPLATE_CODE_IAD,
        )
        self.compliance = Dashboard.objects.create(
            name="Compliance Plan",
            report_id="rid-hide-compliance",
            company=self.company,
            created_by=self.creator,
            status=DashboardStatus.PUBLISHED,
            template_type=TEMPLATE_CODE_CD,
        )

    def _client(self, user: User) -> Client:
        client = Client()
        client.force_login(user)
        client.post("/select-company/", {"company_id": self.company.pk})
        return client

    def test_attachment_label_renamed(self):
        self.assertEqual(
            tr("en", "audit_deck_attach_toggle_label"),
            "Audit, Risk, and Compliance Committee Report",
        )
        self.assertIn("المخاطر", tr("ar", "audit_deck_attach_toggle_label"))

    def test_hidden_dashboard_is_invisible_to_creator(self):
        self.dashboard.is_hidden = True
        self.dashboard.save(update_fields=["is_hidden"])
        ids = set(
            dashboards_queryset_for_user(self.creator, self.company).values_list(
                "pk", flat=True
            )
        )
        self.assertNotIn(self.dashboard.pk, ids)
        self.assertFalse(
            user_can_see_dashboard(self.creator, self.dashboard, self.company)
        )
        client = self._client(self.creator)
        detail = client.get(f"/dashboards/{self.dashboard.pk}/")
        serve = client.get(f"/dashboards/{self.dashboard.pk}/serve/")
        self.assertEqual(detail.status_code, 404)
        self.assertEqual(serve.status_code, 404)

    def test_hide_permission_can_see_and_restore(self):
        self.dashboard.is_hidden = True
        self.dashboard.save(update_fields=["is_hidden"])
        self.assertTrue(user_can_see_dashboard(self.hider, self.dashboard, self.company))
        client = self._client(self.hider)
        listed = client.get(f"/?template={TEMPLATE_CODE_IAD}")
        self.assertNotContains(listed, "Visible Plan")
        self.assertContains(listed, "dashboard-filter-chip--danger")
        hidden = client.get(f"/?template={TEMPLATE_CODE_IAD}&filter=hidden")
        self.assertContains(hidden, "Visible Plan")
        self.assertContains(hidden, "js-hide-dashboard-form")
        response = client.post(
            f"/dashboards/{self.dashboard.pk}/visibility/",
            {"hidden": "0", "next": "list"},
        )
        self.assertEqual(response.status_code, 302)
        self.dashboard.refresh_from_db()
        self.assertFalse(self.dashboard.is_hidden)
        self.assertTrue(
            user_can_see_dashboard(self.creator, self.dashboard, self.company)
        )

    def test_creator_cannot_hide_without_permission(self):
        client = self._client(self.creator)
        response = client.post(
            f"/dashboards/{self.dashboard.pk}/visibility/",
            {"hidden": "1", "next": "list"},
        )
        self.assertEqual(response.status_code, 302)
        self.dashboard.refresh_from_db()
        self.assertFalse(self.dashboard.is_hidden)

    def test_hide_permission_is_per_template(self):
        self.compliance.is_hidden = True
        self.compliance.save(update_fields=["is_hidden"])
        self.assertFalse(
            user_can_see_dashboard(self.hider, self.compliance, self.company)
        )
        ids = set(
            dashboards_queryset_for_user(self.hider, self.company).values_list(
                "pk", flat=True
            )
        )
        self.assertNotIn(self.compliance.pk, ids)
        self.assertIn(self.dashboard.pk, ids)

    def test_list_page_drops_search_and_shows_full_name(self):
        self.dashboard.name = "Internal Audit Dashboard With A Very Long Title That Must Stay Fully Visible"
        self.dashboard.save(update_fields=["name"])
        client = self._client(self.creator)
        response = client.get(f"/?template={TEMPLATE_CODE_IAD}")
        html = response.content.decode()
        self.assertNotIn('id="dbSearch"', html)
        self.assertIn('class="db-card-name"', html)
        self.assertNotIn("db-card-name text-truncate", html)
        self.assertIn(self.dashboard.name, html)

    def test_membership_form_shows_hide_on_each_template(self):
        from audit_app.admin_forms import CompanyMembershipForm

        membership = self.hider.company_memberships.get(company=self.company)
        form = CompanyMembershipForm(instance=membership)
        html = str(form["template_permissions"])
        self.assertGreaterEqual(html.count("can_hide_dashboards"), 2)
        self.assertIn("Hide dashboards", html)
        self.assertIn(TEMPLATE_CODE_IAD, html)
        self.assertIn(TEMPLATE_CODE_CD, html)
