"""Header logo is embedded for the main tenant company regardless of subsidiary filters."""
from __future__ import annotations

import pandas as pd

from arabic_compliance_dashboard.generator import generate_ar_compliance_report


def _minimal_df() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "تصنيف المخاطر الكامنة": "عالي",
                "تصنيف المخاطر المتبقية": "متوسط",
                "الحالة": "مفتوح",
                "الإدارة المسؤولة": "الامتثال",
                "المشرع": "وزارة التجارة",
                "اسم النظام": "نظام الشركات",
                "الهيئة التابعة": "هيئة",
                "اللائحة": "لائحة",
                "النص النظامي": "نص",
                "حالة الالتزام": "ملتزم",
                "فئة الضوابط الرقابية": "رقابي",
                "الشركة التابعة": "aum",
            }
        ]
    )


def test_generate_report_embeds_main_header_logo():
    logo_uri = "data:image/png;base64,TESTLOGO"
    sub_uri = "data:image/png;base64,SUBLOGO"
    html = generate_ar_compliance_report(
        _minimal_df(),
        dashboard_id=1,
        brand_logos={"nat": logo_uri, "aum": sub_uri},
        default_brand_code="nat",
    )
    assert f'<img id="headerLogo" class="logo" alt="" src="{logo_uri}">' in html
    assert '"default_brand_code": "nat"' in html
    assert '"aum": "data:image/png;base64,SUBLOGO"' in html


def test_export_snapshot_html_is_self_contained_interactive():
    html = generate_ar_compliance_report(
        _minimal_df(),
        dashboard_id=9,
        embed_snapshot=True,
        api_base="",
        brand_logos={"nat": "data:image/png;base64,TESTLOGO"},
        default_brand_code="nat",
    )
    assert 'id="downloadInteractiveHtmlBtn"' in html
    assert 'id="snapshot-pack"' in html
    assert '"isLive": false' in html
    assert "نص" in html
    assert "legal_details" in html
    assert "recordListModal" in html
    assert "agingToggle" in html
    assert "agingDownloadWordBtn" in html
    assert "compliancePlanToggle" in html
    assert "finalStatusToggle" in html
    assert "assessmentNewToggle" in html
    assert "assessmentGenerateBtn" in html
    assert "annualTrackingWordBtn" in html
    assert "legalModalDownloadWord" in html
    assert "export-legal-text-docx" in html
    assert "export-assessment-list-docx" in html
    assert "recordListShowLegislatorCols" in html
    assert "assessmentFormsModal" in html
    assert "filePreviewPanel" in html
    assert "fileStudioToggle" in html
    assert "planStatusToggle" in html
    assert "planStatusWordBtn" in html
    assert "حالة خطط المعالجة" in html
    assert "export-plan-status-docx" in html
    assert "programStatusToggle" in html
    assert "programStatusWordBtn" in html
    assert "الحالة العامة للبرنامج" in html
    assert "export-program-status-docx" in html
    assert "fileStudioModal" in html
    assert "تنزيل Excel" in html
    assert "initFileColumnStudio" in html
    assert "initUploadedFilePreview" in html
    assert "معاينة الملف المرفوع" in html
    from arabic_compliance_dashboard.generator import export_snapshot_html

    exported = export_snapshot_html(_minimal_df(), dashboard_id=9)
    assert '"isLive": false' in exported
    assert '"apiBase": ""' in exported
