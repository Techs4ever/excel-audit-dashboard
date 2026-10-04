"""Tests for audit plan user edits persistence and reviewer attachment management."""
from __future__ import annotations

import json
import re

from django.contrib.auth.models import User
from django.test import Client, TestCase
from django.urls import reverse

from audit_app.models import Company, CompanyMembership, Dashboard, DashboardStatus, UploadSession
from reports_app.dashboard_workflow import (
    can_user_manage_review_attachments,
    can_user_save_dashboard_user_edits,
)
from reports_app.services.report_generation import (
    attachment_specs_for_template,
    build_attachment_form_slots,
    inject_compliance_editor_seeds,
    inject_dashboard_serve_context,
    inject_user_edits_persist_script,
    merge_preserved_user_edits,
    validate_dashboard_user_edits_payload,
)

class AuditPlanUserEditsTests(TestCase):
    def setUp(self):
        self.company, _ = Company.objects.get_or_create(
            code="BTC",
            defaults={"name": "BTC", "excel_company_names": ["BTC"], "use_workflow_v2": True},
        )
        self.company.ensure_attachment_settings()
        self.reviewer = User.objects.create_user(username="plan_reviewer", password="pass12345!")
        CompanyMembership.objects.create(
            company=self.company,
            user=self.reviewer,
            can_review=True,
        )
        session = UploadSession.objects.create(
            source_name="test.xlsx",
            mode="IAD",
            locale="en",
            raw_data_json='{"columns":["a"],"data":[["1"]]}',
        )
        self.dashboard = Dashboard.objects.create(
            name="Plan Draft",
            report_id="plan-draft-001",
            company=self.company,
            created_by=self.reviewer,
            upload_session=session,
            status=DashboardStatus.DRAFT,
        )

    def test_validate_dashboard_user_edits_payload_normalizes_rows(self):
        payload = validate_dashboard_user_edits_payload(
            {
                "v": 1,
                "planRows": [[" Alpha ", "Beta", "", "", "", "", ""]],
                "planCellBg": [["#ff0000", "bad", "", "", "", "", ""]],
                "reviewsNote": "note",
            }
        )
        self.assertEqual(payload["planRows"][0][0], "Alpha")
        self.assertEqual(payload["planCellBg"][0][0], "#ff0000")
        self.assertEqual(payload["planCellBg"][0][1], "#ffffff")
        self.assertEqual(payload["reviewsNote"], "note")
        self.assertEqual(payload.get("obsTrackingRows"), [])

    def test_validate_dashboard_user_edits_payload_obs_tracking_rows(self):
        payload = validate_dashboard_user_edits_payload(
            {
                "v": 1,
                "planRows": [],
                "planCellBg": [],
                "reviewsNote": "",
                "obsTrackingRows": [[" Opening Balance ", "0", "", "", "0"], ["Q1", "0", "2", "1"]],
            }
        )
        self.assertEqual(payload["obsTrackingRows"][0][0], "Opening Balance")
        self.assertEqual(payload["obsTrackingRows"][1][2], "2")
        self.assertEqual(len(payload["obsTrackingRows"][1]), 5)

    def test_validate_dashboard_user_edits_payload_formats_percent_columns(self):
        payload = validate_dashboard_user_edits_payload(
            {
                "v": 1,
                "planRows": [
                    ["Project", "Finance", "Bob", "Open", 0.5, "0.25", "75"],
                ],
                "planCellBg": [],
                "reviewsNote": "",
            }
        )
        self.assertEqual(payload["planRows"][0][4], "50%")
        self.assertEqual(payload["planRows"][0][5], "25%")
        self.assertEqual(payload["planRows"][0][6], "75%")

    def test_multiline_plan_cell_is_preserved(self):
        payload = validate_dashboard_user_edits_payload(
            {
                "v": 1,
                "planRows": [
                    ["Line one\nLine two", "Finance", "Bob", "Open", "50%\nnote", "20%", "10%"],
                ],
                "planCellBg": [],
                "reviewsNote": "",
            }
        )
        self.assertEqual(payload["planRows"][0][0], "Line one\nLine two")
        self.assertEqual(payload["planRows"][0][4], "50%\nnote")

    def test_inject_user_edits_persist_script_inserts_json_block(self):
        html = "<html><body><div>ok</div></body></html>"
        out = inject_user_edits_persist_script(html, '{"v":1,"planRows":[]}')
        self.assertIn('id="audit-dashboard-user-persist"', out)
        self.assertIn('"planRows":[]', out)

    def test_inject_user_edits_persist_script_keeps_cell_newline(self):
        raw = json.dumps(
            {"v": 1, "planRows": [["Line one\nLine two"]]},
            ensure_ascii=False,
        )
        html = "<html><body><div>ok</div></body></html>"
        out = inject_user_edits_persist_script(html, raw)
        match = re.search(
            r'<script id="audit-dashboard-user-persist"[^>]*>(.*?)</script>',
            out,
            flags=re.DOTALL,
        )
        self.assertIsNotNone(match)
        parsed = json.loads(match.group(1))
        self.assertEqual(parsed["planRows"][0][0], "Line one\nLine two")

    def test_inject_dashboard_serve_context_sets_save_flags(self):
        html = (
            "<html><head>"
            "window.__AI_EXCEL_USER_EDITS_SAVE_URL__=null;"
            "window.__AI_EXCEL_CAN_SAVE_USER_EDITS__=false;"
            "</head><body></body></html>"
        )
        out = inject_dashboard_serve_context(
            html,
            mail_url="http://test/api/mail",
            plan_url="http://test/api/plan",
            user_edits_save_url="http://test/save",
            can_save_user_edits=True,
            user_edits_json='{"v":1,"planRows":[["P","A","","","","",""]]}',
        )
        self.assertIn("http://test/save", out)
        self.assertIn("__AI_EXCEL_CAN_SAVE_USER_EDITS__=true", out)
        self.assertIn('"planRows":[["P","A","","","","",""]]', out)

    def test_inject_dashboard_status_marker(self):
        html = '<html><head>window.__AI_EXCEL_DASHBOARD_STATUS__="";</head></html>'
        out = inject_dashboard_serve_context(
            html,
            mail_url="http://test/api/mail",
            plan_url="http://test/api/plan",
            user_edits_save_url="",
            can_save_user_edits=False,
            dashboard_status="published",
        )
        self.assertIn('window.__AI_EXCEL_DASHBOARD_STATUS__="published";', out)

    def test_non_draft_does_not_replace_ambassador_rows(self):
        raw = {
            "v": 1,
            "planRows": [],
            "complianceAmbassadorsTouched": False,
            "complianceAmbassadors": {"rows": [["جديد", "", "", "", "", "", "", "", ""]]},
        }
        merged = merge_preserved_user_edits(
            "{}",
            raw,
            validate_dashboard_user_edits_payload(raw),
        )
        self.assertEqual(merged["complianceAmbassadors"]["rows"], [])
        kept = merge_preserved_user_edits(
            json.dumps(
                {"complianceAmbassadors": {"rows": [["محفوظ", "", "", "", "", "", "", "", ""]]}},
                ensure_ascii=False,
            ),
            raw,
            validate_dashboard_user_edits_payload(raw),
        )
        self.assertEqual(kept["complianceAmbassadors"]["rows"][0][0], "محفوظ")

    def test_compliance_page_that_reads_save_url_still_receives_it(self):
        html = (
            "<html><head></head><body><script>"
            "const url = window.__AI_EXCEL_USER_EDITS_SAVE_URL__ || '';"
            "</script></body></html>"
        )
        out = inject_dashboard_serve_context(
            html,
            mail_url="http://test/api/mail",
            plan_url="http://test/api/plan",
            user_edits_save_url="http://test/save",
            can_save_user_edits=True,
        )
        self.assertIn("window.__AI_EXCEL_USER_EDITS_SAVE_URL__=\"http://test/save\"", out)
        self.assertIn("window.__AI_EXCEL_CAN_SAVE_USER_EDITS__=true", out)

    def test_can_user_save_dashboard_user_edits_until_publish(self):
        self.assertTrue(
            can_user_save_dashboard_user_edits(self.reviewer, self.dashboard, self.company)
        )
        self.dashboard.status = DashboardStatus.PUBLISHED
        self.dashboard.save(update_fields=["status"])
        self.assertFalse(
            can_user_save_dashboard_user_edits(self.reviewer, self.dashboard, self.company)
        )

    def test_dashboard_user_edits_api_persists(self):
        client = Client()
        client.force_login(self.reviewer)
        session = client.session
        session["active_company_id"] = self.company.pk
        session.save()

        url = reverse("dashboard_user_edits", args=[self.dashboard.pk])
        body = {
            "v": 1,
            "planRows": [["Project X", "Finance", "Bob", "Open", "10%", "20%", "30%"]],
            "planCellBg": [],
            "reviewsNote": "saved",
        }
        resp = client.post(
            url,
            data=json.dumps(body),
            content_type="application/json",
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.json()["ok"])
        self.dashboard.refresh_from_db()
        stored = json.loads(self.dashboard.user_edits_json)
        self.assertEqual(stored["planRows"][0][0], "Project X")
        self.assertEqual(stored["reviewsNote"], "saved")

    def test_blank_plan_save_does_not_erase_stored_rows(self):
        self.dashboard.user_edits_json = json.dumps(
            {
                "v": 1,
                "planRows": [["Project X", "Finance", "Bob", "Open", "10%", "20%", "30%"]],
                "planCellBg": [],
                "reviewsNote": "keep",
                "obsTrackingRows": [["Opening Balance", "4", "", "", "4"], ["Q1", "4", "2", "1", "5"]],
            }
        )
        self.dashboard.save(update_fields=["user_edits_json"])
        client = Client()
        client.force_login(self.reviewer)
        session = client.session
        session["active_company_id"] = self.company.pk
        session.save()
        resp = client.post(
            reverse("dashboard_user_edits", args=[self.dashboard.pk]),
            data=json.dumps(
                {
                    "v": 1,
                    "planRows": [["", "", "", "", "", "", ""]],
                    "planCellBg": [],
                    "reviewsNote": "keep",
                    "obsTrackingRows": [["Opening Balance", "0", "", "", "0"]],
                }
            ),
            content_type="application/json",
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )
        self.assertEqual(resp.status_code, 200)
        self.dashboard.refresh_from_db()
        stored = json.loads(self.dashboard.user_edits_json)
        self.assertEqual(stored["planRows"][0][0], "Project X")
        self.assertEqual(stored["obsTrackingRows"][1][2], "2")

    def test_explicit_plan_clear_replaces_stored_rows(self):
        existing = {
            "v": 1,
            "planRows": [["Project X", "Finance", "", "", "", "", ""]],
            "planCellBg": [["#ff0000", "#ffffff", "#ffffff", "#ffffff", "#ffffff", "#ffffff", "#ffffff"]],
            "reviewsNote": "",
            "obsTrackingRows": [],
        }
        normalized = validate_dashboard_user_edits_payload(
            {
                "v": 1,
                "planRows": [["", "", "", "", "", "", ""]],
                "planCellBg": [],
                "reviewsNote": "",
                "planCleared": True,
                "planTouched": True,
            }
        )
        merged = merge_preserved_user_edits(json.dumps(existing), {"planCleared": True, "planTouched": True}, normalized)
        self.assertEqual(merged["planRows"][0][0], "")

    def test_untouched_plan_flag_keeps_stored_rows(self):
        existing = {
            "v": 1,
            "planRows": [["Project X", "Finance", "", "", "", "", ""]],
            "planCellBg": [],
            "reviewsNote": "n",
            "obsTrackingRows": [["Q1", "1", "3", "0", "4"]],
        }
        normalized = validate_dashboard_user_edits_payload(
            {
                "v": 1,
                "planRows": [["Changed", "", "", "", "", "", ""]],
                "planCellBg": [],
                "reviewsNote": "n",
                "obsTrackingRows": [["Q1", "9", "9", "9", "9"]],
                "planTouched": False,
                "obsTrackingTouched": False,
            }
        )
        merged = merge_preserved_user_edits(
            json.dumps(existing),
            {"planTouched": False, "obsTrackingTouched": False},
            normalized,
        )
        self.assertEqual(merged["planRows"][0][0], "Project X")
        self.assertEqual(merged["obsTrackingRows"][0][2], "3")

    def test_can_user_manage_review_attachments_while_pending_or_published(self):
        self.dashboard.status = DashboardStatus.UNDER_REVIEW
        self.dashboard.save(update_fields=["status"])
        self.assertTrue(
            can_user_manage_review_attachments(self.reviewer, self.dashboard, self.company)
        )
        self.dashboard.status = DashboardStatus.PUBLISHED
        self.dashboard.save(update_fields=["status"])
        self.assertTrue(
            can_user_manage_review_attachments(self.reviewer, self.dashboard, self.company)
        )
        self.dashboard.status = DashboardStatus.DRAFT
        self.dashboard.save(update_fields=["status"])
        self.assertFalse(
            can_user_manage_review_attachments(self.reviewer, self.dashboard, self.company)
        )

    def test_compliance_save_does_not_erase_audit_plan_rows(self):
        existing = {
            "v": 1,
            "planRows": [["Project X", "Finance", "", "", "", "", ""]],
            "planCellBg": [],
            "reviewsNote": "keep-note",
            "obsTrackingRows": [["Q1", "1", "3", "0", "4"]],
            "compliancePlan": {"sheetName": "old", "headers": ["A"], "rows": [["1"]], "styles": {}},
            "complianceQuarterly": {"rows": [["الربع الاول", "5", "1", "0", "0", "6"]]},
        }
        raw = {
            "v": 1,
            "planRows": [],
            "planTouched": False,
            "obsTrackingTouched": False,
            "reviewsTouched": False,
            "compliancePlanTouched": True,
            "complianceQuarterlyTouched": False,
            "compliancePlan": {
                "sheetName": "خطة",
                "headers": ["البند"],
                "rows": [["التزام"]],
                "styles": {"0,0": "#fff59d"},
            },
            "complianceQuarterly": {"rows": []},
        }
        merged = merge_preserved_user_edits(
            json.dumps(existing),
            raw,
            validate_dashboard_user_edits_payload(raw),
        )
        self.assertEqual(merged["planRows"][0][0], "Project X")
        self.assertEqual(merged["obsTrackingRows"][0][2], "3")
        self.assertEqual(merged["reviewsNote"], "keep-note")
        self.assertEqual(merged["compliancePlan"]["rows"][0][0], "التزام")
        self.assertEqual(merged["complianceQuarterly"]["rows"][0][1], "5")

    def test_audit_plan_save_does_not_erase_compliance_tables(self):
        existing = {
            "v": 1,
            "planRows": [],
            "planCellBg": [],
            "reviewsNote": "",
            "obsTrackingRows": [],
            "compliancePlan": {"sheetName": "خطة", "headers": ["البند"], "rows": [["التزام"]], "styles": {}},
            "complianceQuarterly": {"rows": [["الربع الاول", "8", "2", "1", "0", "11"]]},
        }
        raw = {
            "v": 1,
            "planRows": [["New plan", "", "", "", "", "", ""]],
            "planTouched": True,
            "obsTrackingRows": [],
        }
        merged = merge_preserved_user_edits(
            json.dumps(existing),
            raw,
            validate_dashboard_user_edits_payload(raw),
        )
        self.assertEqual(merged["planRows"][0][0], "New plan")
        self.assertEqual(merged["compliancePlan"]["rows"][0][0], "التزام")
        self.assertEqual(merged["complianceQuarterly"]["rows"][0][1], "8")

    def test_compliance_seeds_are_injected_from_user_edits(self):
        html = (
            '<script type="application/json" id="compliance-plan-seed">{}</script>'
            '<script type="application/json" id="compliance-quarterly-seed">{}</script>'
        )
        stored = json.dumps(
            {
                "compliancePlan": {"sheetName": "S", "headers": ["H"], "rows": [["v"]], "styles": {}},
                "complianceQuarterly": {"rows": [["الربع الاول", "1", "0", "0", "0", "1"]]},
            },
            ensure_ascii=False,
        )
        out = inject_compliance_editor_seeds(html, stored)
        self.assertIn("S", out)
        self.assertIn("الربع الاول", out)

    def test_ambassadors_rows_are_normalized_and_preserved(self):
        raw = {
            "v": 1,
            "planRows": [],
            "complianceAmbassadorsTouched": True,
            "complianceAmbassadors": {
                "rows": [[" 0550000000 ", "alt@example.com", "بديل", "0500000000", "a@example.com", "أخصائي", "سفير", "المالية", "القطاع"]],
            },
        }
        normalized = validate_dashboard_user_edits_payload(raw)
        self.assertEqual(len(normalized["complianceAmbassadors"]["rows"][0]), 9)
        self.assertEqual(normalized["complianceAmbassadors"]["rows"][0][0], "0550000000")
        self.assertEqual(normalized["complianceAmbassadors"]["rows"][0][6], "سفير")

        existing = {
            "v": 1,
            "planRows": [],
            "complianceQuarterly": {"rows": [["الربع الاول", "5", "1", "0", "0", "6"]]},
            "complianceAmbassadors": {"rows": [["1", "2", "3", "4", "5", "6", "محفوظ", "8", "9"]]},
        }
        quarter_only = {
            "v": 1,
            "planRows": [],
            "complianceQuarterlyTouched": True,
            "complianceAmbassadorsTouched": False,
            "complianceQuarterly": {"rows": [["الربع الاول", "9", "0", "0", "0", "9"]]},
            "complianceAmbassadors": {"rows": []},
        }
        merged = merge_preserved_user_edits(
            json.dumps(existing),
            quarter_only,
            validate_dashboard_user_edits_payload(quarter_only),
        )
        self.assertEqual(merged["complianceQuarterly"]["rows"][0][1], "9")
        self.assertEqual(merged["complianceAmbassadors"]["rows"][0][6], "محفوظ")

        saved = merge_preserved_user_edits(
            json.dumps(existing),
            raw,
            normalized,
        )
        self.assertEqual(saved["complianceAmbassadors"]["rows"][0][6], "سفير")
        self.assertEqual(saved["complianceQuarterly"]["rows"][0][1], "5")

    def test_ambassadors_seed_is_injected_from_user_edits(self):
        html = '<script type="application/json" id="compliance-ambassadors-seed">{}</script>'
        stored = json.dumps(
            {"complianceAmbassadors": {"rows": [["", "", "", "", "", "", "نورة", "", ""]]}},
            ensure_ascii=False,
        )
        out = inject_compliance_editor_seeds(html, stored)
        self.assertIn("نورة", out)

    def test_attachment_slots_follow_dashboard_template(self):
        iad = [spec["kind"] for spec in attachment_specs_for_template("IAD")]
        cd = [spec["kind"] for spec in attachment_specs_for_template("CD")]
        self.assertIn("deck", iad)
        self.assertNotIn("legislation", iad)
        self.assertIn("legislation", cd)
        self.assertIn("complianceDetailed", cd)
        self.assertIn("complianceQuarterly", cd)
        self.assertNotIn("deck", cd)
        slots = build_attachment_form_slots(
            None, locale="ar", company=self.company, template_type="CD"
        )
        kinds = {slot["kind"] for slot in slots}
        self.assertEqual(
            kinds, {"legislation", "complianceDetailed", "complianceQuarterly"}
        )


class ResubmitKeepExcelTests(TestCase):
    def setUp(self):
        self.company, _ = Company.objects.get_or_create(
            code="BTC",
            defaults={"name": "BTC", "excel_company_names": ["BTC"], "use_workflow_v2": True},
        )
        self.company.ensure_attachment_settings()
        self.creator = User.objects.create_user(username="keep_excel_user", password="pass12345!")
        CompanyMembership.objects.create(
            company=self.company,
            user=self.creator,
            can_upload=True,
        )
        session = UploadSession.objects.create(
            source_name="orig.xlsx",
            mode="IAD",
            locale="en",
            raw_data_json='{"columns":["a"],"data":[["1"]],"source_name":"orig.xlsx"}',
        )
        self.dashboard = Dashboard.objects.create(
            name="Keep Excel",
            report_id="keep-excel-001",
            company=self.company,
            created_by=self.creator,
            upload_session=session,
            source_files={"excel": ["orig.xlsx"]},
            status=DashboardStatus.DRAFT,
            template_type="IAD",
        )

    def _post_resubmit_without_file(self, extra=None):
        client = Client()
        client.force_login(self.creator)
        session = client.session
        session["active_company_id"] = self.company.pk
        session.save()
        data = {
            "dashboard_name": "Keep Excel Renamed",
            "icon": "bi-bar-chart-line-fill",
            "template_type": "IAD",
            "resubmit_dashboard_id": str(self.dashboard.pk),
        }
        if extra:
            data.update(extra)
        return client.post(reverse("analyze"), data=data)

    def test_resubmit_without_new_excel_keeps_existing_data(self):
        resp = self._post_resubmit_without_file()
        self.assertEqual(resp.status_code, 302)
        self.dashboard.refresh_from_db()
        self.assertEqual(self.dashboard.name, "Keep Excel Renamed")
        self.assertIsNotNone(self.dashboard.upload_session)
        self.assertIn("orig.xlsx", self.dashboard.source_files.get("excel", []))

    def test_resubmit_with_excel_removed_requires_new_file(self):
        resp = self._post_resubmit_without_file({"remove_excel": "1"})
        self.assertEqual(resp.status_code, 200)
        self.dashboard.refresh_from_db()
        self.assertEqual(self.dashboard.name, "Keep Excel")
