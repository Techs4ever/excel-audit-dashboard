"""Tests for Arabic compliance dashboard schema and engine."""
from __future__ import annotations

import pandas as pd
import pytest

from arabic_compliance_dashboard.engine import build_summary, compute_aging
from arabic_compliance_dashboard.schema import (
    drop_empty_rows_keep_schema_columns,
    normalize_dataframe,
    resolve_columns,
    rows_from_dataframe,
    validate_schema,
)


def _sample_df() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "تصنيف المخاطر الكامنة": "مرتفع",
                "تصنيف المخاطر المتبقية": "متوسط",
                "الحالة": "مفتوح ( ضمن تاريخ التصحيح)",
                "الإدارة المسؤولة": "إدارة IT",
                "المشرع": "وزارة التجارة",
                "النظام": "نظام تجاري",
                "الهيئة التابعة": "0",
                "اللائحة": "لائحة",
                "النص بالكامل": "نص نظامي تجريبي",
                "حالة الالتزام": "ملتزم جزئي",
                "فئة الضوابط الرقابية": "سياسات",
                "السنوات": "2026",
                "تاريخ التصحيح المستهدف": "2026-01-01",
            }
        ]
    )


def test_resolve_columns_aliases():
    df = _sample_df()
    resolved = resolve_columns(df)
    assert "system_name" in resolved
    assert "legal_text" in resolved
    assert "year" in resolved


def test_validate_schema_missing_column():
    df = _sample_df().drop(columns=["الحالة"])
    with pytest.raises(ValueError, match="حالة الخطة التصحيحية|الحالة|Missing"):
        validate_schema(df, locale="ar")


def test_empty_required_status_column_is_kept():
    df = _sample_df()
    df["الحالة"] = None
    cleaned = drop_empty_rows_keep_schema_columns(df)
    assert "الحالة" in cleaned.columns
    resolved = validate_schema(cleaned, locale="ar")
    assert "status" in resolved


def test_unused_excel_template_rows_are_dropped():
    real = _sample_df().iloc[0].to_dict()
    empty = {key: "" for key in real}
    empty["الشركة التابعة"] = "شركة"
    empty["الشركة القابضة"] = "قابضة"
    empty["الإدارة المسؤولة"] = "إدارة IT"
    empty["الهيئة التابعة"] = "0"
    df = pd.DataFrame([real, empty, empty, {**empty, "النص بالكامل": "   "}])
    cleaned = drop_empty_rows_keep_schema_columns(df)
    assert len(cleaned) == 1
    rows = rows_from_dataframe(cleaned)
    assert len(rows) == 1
    assert rows[0]["النص النظامي"] == "نص نظامي تجريبي"


def test_validate_schema_without_risk_columns():
    df = _sample_df().drop(columns=["تصنيف المخاطر الكامنة", "تصنيف المخاطر المتبقية"])
    resolved = validate_schema(df, locale="ar")
    assert "inherent" not in resolved
    assert "residual" not in resolved
    assert "status" in resolved


def test_normalize_and_rows():
    df = normalize_dataframe(_sample_df())
    assert "اسم النظام" in df.columns
    assert "النص النظامي" in df.columns
    assert "حالة الالتزام بالمتطلبات" in df.columns
    assert "تاريخ خطة الالتزام" in df.columns
    assert "مستوى المخاطر الكامنة" in df.columns
    assert "فئة الضوابط الرقابية" in df.columns
    rows = rows_from_dataframe(df)
    assert len(rows) == 1
    assert rows[0]["النص النظامي"] == "نص نظامي تجريبي"
    assert rows[0]["حالة الالتزام بالمتطلبات"] == "ملتزم جزئي"
    assert rows[0]["تاريخ خطة الالتزام"] == "2026"


def test_year_inferred_from_target_date_when_year_column_missing():
    df = pd.DataFrame(
        [
            {
                "الحالة": "مفتوح",
                "الإدارة المسؤولة": "إدارة IT",
                "المشرع": "وزارة التجارة",
                "اسم النظام": "نظام",
                "الهيئة التابعة": "0",
                "اللائحة": "لائحة",
                "النص النظامي": "نص",
                "حالة الالتزام": "غيرملتزم",
                "فئة الضوابط الرقابية": "سياسات",
                "تاريخ التصحيح المستهدف": "2026-03-15",
            },
            {
                "الحالة": "مفتوح",
                "الإدارة المسؤولة": "إدارة IT",
                "المشرع": "وزارة التجارة",
                "اسم النظام": "نظام",
                "الهيئة التابعة": "0",
                "اللائحة": "لائحة",
                "النص النظامي": "نص 2",
                "حالة الالتزام": "غيرملتزم",
                "فئة الضوابط الرقابية": "سياسات",
                "تاريخ التصحيح المستهدف": "",
            },
        ]
    )
    rows = rows_from_dataframe(df)
    assert rows[0]["تاريخ خطة الالتزام"] == "2026"
    assert rows[1]["تاريخ خطة الالتزام"] == "(blank)"
    assert rows[0]["حالة الالتزام بالمتطلبات"] == "غيرملتزم"


def test_year_keeps_explicit_excel_value():
    rows = rows_from_dataframe(normalize_dataframe(_sample_df()))
    assert rows[0]["تاريخ خطة الالتزام"] == "2026"


def test_build_summary_inherent_reads_level_column_not_residual():
    from arabic_compliance_dashboard.engine import COL_INHERENT, COL_RESIDUAL, PARAM_TO_COL

    df = pd.DataFrame(
        [
            {
                "الحالة": "مفتوح",
                "الإدارة المسؤولة": "إدارة IT",
                "المشرع": "وزارة التجارة",
                "اسم النظام": "نظام",
                "الهيئة التابعة": "0",
                "اللائحة": "لائحة",
                "النص النظامي": "نص",
                "حالة الالتزام وفقًا لإدارة الالتزام": "ملتزم",
                "تصنيف الخطر": "سياسات",
                "مستوى المخاطر الكامنة": "مرتفع",
                "تصنيف المخاطر المتبقية": "منخفض",
            },
            {
                "الحالة": "مفتوح",
                "الإدارة المسؤولة": "إدارة IT",
                "المشرع": "وزارة التجارة",
                "اسم النظام": "نظام",
                "الهيئة التابعة": "0",
                "اللائحة": "لائحة",
                "النص النظامي": "نص 2",
                "حالة الالتزام وفقًا لإدارة الالتزام": "ملتزم",
                "تصنيف الخطر": "سياسات",
                "مستوى المخاطر الكامنة": "متوسط",
                "تصنيف المخاطر المتبقية": "منخفض",
            },
            {
                "الحالة": "مفتوح",
                "الإدارة المسؤولة": "إدارة IT",
                "المشرع": "وزارة التجارة",
                "اسم النظام": "نظام",
                "الهيئة التابعة": "0",
                "اللائحة": "لائحة",
                "النص النظامي": "نص 3",
                "حالة الالتزام وفقًا لإدارة الالتزام": "ملتزم",
                "تصنيف الخطر": "سياسات",
                "مستوى المخاطر الكامنة": "مرتفع جداً",
                "تصنيف المخاطر المتبقية": "منخفض",
            },
        ]
    )
    rows = rows_from_dataframe(normalize_dataframe(df))
    selected = {col: [] for col in PARAM_TO_COL.values()}
    groups = {item["key"]: item["count"] for item in build_summary(rows, selected)["groups"][COL_INHERENT]}
    assert groups["مرتفع"] == 1
    assert groups["متوسط"] == 1
    assert groups["مرتفع جداً"] == 1
    residual = {item["key"]: item["count"] for item in build_summary(rows, selected)["groups"][COL_RESIDUAL]}
    assert residual["منخفض"] == 3


def test_build_summary_filter():
    from arabic_compliance_dashboard.engine import PARAM_TO_COL

    df = normalize_dataframe(_sample_df())
    rows = rows_from_dataframe(df)
    selected = {col: [] for col in PARAM_TO_COL.values()}
    summary = build_summary(rows, selected)
    assert summary["total"] == 1
    assert "حالة الخطة التصحيحية" in summary["groups"]


def test_build_record_list_uses_legal_text_and_department():
    from arabic_compliance_dashboard.engine import PARAM_TO_COL, build_record_list

    df = normalize_dataframe(_sample_df())
    rows = rows_from_dataframe(df)
    selected = {col: [] for col in PARAM_TO_COL.values()}
    out = build_record_list(rows, selected)
    assert out["total"] == 1
    assert out["records"][0]["observation"] == "نص نظامي تجريبي"
    assert out["records"][0]["department"] == "إدارة IT"
    assert out["records"][0]["rating"] == "مرتفع"
    assert out["records"][0]["quarter"] == "Q1"


def test_record_list_prefers_compliance_mgmt_column():
    from arabic_compliance_dashboard.engine import PARAM_TO_COL, build_record_list

    df = pd.DataFrame(
        [
            {
                "الحالة": "مفتوح",
                "الإدارة المسؤولة": "إدارة IT",
                "المشرع": "وزارة التجارة",
                "اسم النظام": "نظام",
                "الهيئة التابعة": "0",
                "اللائحة": "لائحة",
                "النص النظامي": "نص",
                "حالة الالتزام بالمتطلبات": "غير ملتزم",
                "حالة الالتزام وفقًا لإدارة الالتزام": "ملتزم جزئي",
                "فئة الضوابط الرقابية": "سياسات",
                "تاريخ خطة الالتزام": "2026",
            }
        ]
    )
    rows = rows_from_dataframe(df)
    selected = {col: [] for col in PARAM_TO_COL.values()}
    out = build_record_list(rows, selected)
    assert out["records"][0]["compliance_mgmt"] == "ملتزم جزئي"


def test_record_list_quarter_follows_target_column():
    from arabic_compliance_dashboard.engine import PARAM_TO_COL, build_record_list

    df = pd.DataFrame(
        [
            {
                "الحالة": "مفتوح",
                "الإدارة المسؤولة": "إدارة IT",
                "المشرع": "وزارة التجارة",
                "اسم النظام": "نظام",
                "الهيئة التابعة": "0",
                "اللائحة": "لائحة",
                "النص النظامي": "نص Q1",
                "حالة الالتزام": "غيرملتزم",
                "فئة الضوابط الرقابية": "تشغيلية",
                "السنوات": "2026",
                "تاريخ التصحيح السنوي المستهدف": "2026",
                "تاريخ التصحيح المستهدف - الربعي": "Q1",
            },
            {
                "الحالة": "مفتوح",
                "الإدارة المسؤولة": "المالية",
                "المشرع": "وزارة التجارة",
                "اسم النظام": "نظام",
                "الهيئة التابعة": "0",
                "اللائحة": "لائحة",
                "النص النظامي": "نص Q3",
                "حالة الالتزام": "غيرملتزم",
                "فئة الضوابط الرقابية": "تشغيلية",
                "السنوات": "2026",
                "تاريخ التصحيح السنوي المستهدف": "2026",
                "تاريخ التصحيح المستهدف - الربعي": "Q3",
            },
        ]
    )
    rows = rows_from_dataframe(normalize_dataframe(df))
    selected = {col: [] for col in PARAM_TO_COL.values()}
    selected[PARAM_TO_COL["year"]] = ["2026"]
    out = build_record_list(rows, selected)
    quarters = {item["observation"]: item["quarter"] for item in out["records"]}
    assert quarters["نص Q1"] == "Q1"
    assert quarters["نص Q3"] == "Q3"


def test_compute_aging_open_status():
    from arabic_compliance_dashboard.engine import (
        COL_RESIDUAL,
        COL_STATUS,
        COL_TARGET,
        PARAM_TO_COL,
    )

    df = normalize_dataframe(_sample_df())
    rows = rows_from_dataframe(df)
    selected = {col: [] for col in PARAM_TO_COL.values()}
    out = compute_aging(rows, selected, "2026-06-01", "target")
    assert "error" not in out
    lt_6m = next(r for r in out["time_rows"] if r["id"] == "lt_6m")
    assert lt_6m["total"] == 1
    assert out["grand_total"] == 1


def test_compute_aging_past_status_buckets():
    from arabic_compliance_dashboard.engine import (
        COL_RESIDUAL,
        COL_STATUS,
        COL_TARGET,
        PARAM_TO_COL,
    )

    rows = [
        {
            COL_STATUS: "مفتوح ( تجاوز تاريخ التصحيح)",
            COL_RESIDUAL: "متوسط",
            COL_TARGET: "2026-01-01",
        }
    ]
    selected = {col: [] for col in PARAM_TO_COL.values()}
    out = compute_aging(rows, selected, "2026-06-01", "target")
    lt_6m = next(r for r in out["time_rows"] if r["id"] == "lt_6m")
    assert lt_6m["cells"]["medium"] == 1
    assert out["grand_total"] == 1


def test_compute_aging_uses_target_date_not_modified():
    from arabic_compliance_dashboard.engine import (
        COL_MODIFIED,
        COL_RESIDUAL,
        COL_STATUS,
        COL_TARGET,
        PARAM_TO_COL,
    )

    rows = [
        {
            COL_STATUS: "مفتوحة  تجاوزت الجدول الزمني",
            COL_RESIDUAL: "مرتفع",
            COL_TARGET: "2024-01-01",
            COL_MODIFIED: "2026-05-01",
        }
    ]
    selected = {col: [] for col in PARAM_TO_COL.values()}
    out = compute_aging(rows, selected, "2026-06-01", "modified")
    ge_1y = next(r for r in out["time_rows"] if r["id"] == "ge_1y")
    assert ge_1y["cells"]["high"] == 1
    assert out["date_field"] == COL_TARGET
    y2 = next(r for r in out["over_year_rows"] if r["id"] == "y2_3")
    assert y2["cells"]["high"] == 1


def test_aging_record_list_filters_to_cell():
    from arabic_compliance_dashboard.engine import (
        COL_INHERENT,
        COL_LEGAL,
        COL_STATUS,
        COL_TARGET,
        PARAM_TO_COL,
        build_record_list,
    )

    rows = [
        {
            COL_STATUS: "مفتوحة  تجاوزت الجدول الزمني",
            COL_INHERENT: "مرتفع",
            COL_TARGET: "2024-01-01",
            COL_LEGAL: "نص أ",
        },
        {
            COL_STATUS: "مفتوحة  تجاوزت الجدول الزمني",
            COL_INHERENT: "متوسط",
            COL_TARGET: "2026-01-01",
            COL_LEGAL: "نص ب",
        },
    ]
    selected = {col: [] for col in PARAM_TO_COL.values()}
    out = build_record_list(
        rows,
        selected,
        aging_time="ge_1y",
        aging_risk="high",
        reference_raw="2026-06-01",
    )
    assert out["total"] == 1
    assert out["records"][0]["legal_text"] == "نص أ"


def test_compute_aging_uses_inherent_risk_when_residual_missing():
    from arabic_compliance_dashboard.engine import (
        COL_INHERENT,
        COL_STATUS,
        COL_TARGET,
        PARAM_TO_COL,
    )

    rows = [
        {
            COL_STATUS: "مفتوح ( ضمن تاريخ التصحيح)",
            COL_INHERENT: "عالي",
            COL_TARGET: "2026-12-01",
        }
    ]
    selected = {col: [] for col in PARAM_TO_COL.values()}
    out = compute_aging(rows, selected, "2026-06-01", "target")
    not_due = next(r for r in out["time_rows"] if r["id"] == "not_due")
    assert not_due["cells"]["high"] == 1


def test_compute_aging_reads_double_space_target_header_and_file_status():
    from arabic_compliance_dashboard.engine import PARAM_TO_COL

    rows = [
        {
            "حالة الخطة التصحيحية": "مفتوحة  ضمن الجدول الزمني",
            "تصنيف المخاطر المتبقية": "متوسط",
            "تاريخ التصحيح  المستهدف": "2026-03-31 00:00:00",
            "تاريخ التصحيح السنوي المستهدف": "2026",
        },
        {
            "حالة الخطة التصحيحية": "مغلق",
            "تصنيف المخاطر المتبقية": "منخفض",
            "تاريخ التصحيح المستهدف": "2020-01-01",
        },
    ]
    selected = {col: [] for col in PARAM_TO_COL.values()}
    out = compute_aging(rows, selected, "2026-06-01", "target")
    lt_6m = next(r for r in out["time_rows"] if r["id"] == "lt_6m")
    assert lt_6m["cells"]["medium"] == 1
    assert out["grand_total"] == 1
    assert out["skipped_other_status"] == 1
    assert out["date_field"] == "تاريخ التصحيح المستهدف"


def test_compute_aging_ignores_annual_year_column():
    from arabic_compliance_dashboard.engine import COL_INHERENT, COL_STATUS, PARAM_TO_COL

    rows = [
        {
            COL_STATUS: "مفتوحة  تجاوزت الجدول الزمني",
            COL_INHERENT: "مرتفع",
            "تاريخ التصحيح السنوي المستهدف": "2026",
            "تاريخ التصحيح المستهدف": "2027-01-15",
        }
    ]
    selected = {col: [] for col in PARAM_TO_COL.values()}
    out = compute_aging(rows, selected, "2026-06-01", "target")
    not_due = next(r for r in out["time_rows"] if r["id"] == "not_due")
    assert not_due["cells"]["high"] == 1


def test_aging_days_vs_selected_reference():
    from arabic_compliance_dashboard.engine import COL_TARGET, aging_days_vs_reference

    row = {COL_TARGET: "2026-03-31"}
    assert aging_days_vs_reference(row, "2026-06-01") == 62
    assert aging_days_vs_reference(row, "2026-03-31") == 0
    assert aging_days_vs_reference(row, "2026-03-01") == -30
    assert aging_days_vs_reference({}, "2026-06-01") is None


def test_resolve_columns_accepts_mosot_al_khatr_aliases():
    df = _sample_df().rename(
        columns={
            "تصنيف المخاطر الكامنة": "مستوى المخاطر الكامنة",
            "تصنيف المخاطر المتبقية": "مستوى المخاطر المتبقية",
        }
    )
    resolved = resolve_columns(df)
    assert resolved["inherent"] == "مستوى المخاطر الكامنة"
    assert resolved["residual"] == "مستوى المخاطر المتبقية"


def test_inherent_and_residual_keep_distinct_excel_headers():
    df = pd.DataFrame(
        [
            {
                "الحالة": "مفتوح",
                "الإدارة المسؤولة": "إدارة IT",
                "المشرع": "وزارة التجارة",
                "اسم النظام": "نظام",
                "الهيئة التابعة": "0",
                "اللائحة": "لائحة",
                "النص النظامي": "نص",
                "حالة الالتزام وفقًا لإدارة الالتزام": "ملتزم",
                "تصنيف الخطر": "سياسات",
                "مستوى المخاطر الكامنة": "مرتفع",
                "تصنيف المخاطر المتبقية": "منخفض",
            }
        ]
    )
    resolved = resolve_columns(df)
    assert resolved["inherent"] == "مستوى المخاطر الكامنة"
    assert resolved["residual"] == "تصنيف المخاطر المتبقية"
    rows = rows_from_dataframe(normalize_dataframe(df))
    assert rows[0]["مستوى المخاطر الكامنة"] == "مرتفع"
    assert rows[0]["تصنيف المخاطر المتبقية"] == "منخفض"


def test_control_category_uses_control_family_not_risk_class():
    from arabic_compliance_dashboard.engine import PARAM_TO_COL

    df = pd.DataFrame(
        [
            {
                "الحالة": "مفتوح",
                "الإدارة المسؤولة": "إدارة IT",
                "المشرع": "وزارة التجارة",
                "اسم النظام": "نظام",
                "الهيئة التابعة": "0",
                "اللائحة": "لائحة",
                "النص النظامي": "نص",
                "حالة الالتزام وفقًا لإدارة الالتزام": "ملتزم",
                "تصنيف الخطر": "نظامي",
                "فئة الضوابط الرقابية": "تشغيلية",
                "مستوى المخاطر الكامنة": "مرتفع",
                "تصنيف المخاطر المتبقية": "منخفض",
            },
            {
                "الحالة": "مغلق",
                "الإدارة المسؤولة": "المالية",
                "المشرع": "وزارة التجارة",
                "اسم النظام": "نظام",
                "الهيئة التابعة": "0",
                "اللائحة": "لائحة",
                "النص النظامي": "نص 2",
                "حالة الالتزام وفقًا لإدارة الالتزام": "ملتزم",
                "تصنيف الخطر": "مالي",
                "فئة الضوابط الرقابية": "السياسات والإجراءات",
                "مستوى المخاطر الكامنة": "متوسط",
                "تصنيف المخاطر المتبقية": "منخفض",
            },
        ]
    )
    resolved = resolve_columns(df)
    assert resolved["control_category"] == "فئة الضوابط الرقابية"
    rows = rows_from_dataframe(normalize_dataframe(df))
    assert rows[0]["فئة الضوابط الرقابية"] == "تشغيلية"
    assert rows[1]["فئة الضوابط الرقابية"] == "السياسات والإجراءات"
    selected = {col: [] for col in PARAM_TO_COL.values()}
    groups = {
        item["key"]: item["count"]
        for item in build_summary(rows, selected)["groups"]["فئة الضوابط الرقابية"]
    }
    assert groups["تشغيلية"] == 1
    assert groups["السياسات والإجراءات"] == 1
    assert "نظامي" not in groups
    assert "مالي" not in groups


def test_new_canonical_headers_map_without_collision():
    df = pd.DataFrame(
        [
            {
                "الحالة": "مفتوح",
                "الإدارة المسؤولة": "إدارة IT",
                "المشرع": "وزارة التجارة",
                "اسم النظام": "نظام",
                "الهيئة التابعة": "0",
                "اللائحة": "لائحة",
                "النص النظامي": "نص",
                "حالة الالتزام وفقًا لإدارة الالتزام": "ملتزم",
                "تصنيف الخطر": "سياسات",
                "تاريخ خطة الالتزام": "2026",
                "مستوى المخاطر الكامنة": "منخفض",
                "تصنيف المخاطر الكامنة": "مرتفع",
                "تاريخ التصحيح السنوي المستهدف": "2026-03-15",
                "تاريخ التصحيح السنوي الفعلي": "2026-04-01",
            }
        ]
    )
    resolved = resolve_columns(df)
    assert resolved["compliance_status"] == "حالة الالتزام وفقًا لإدارة الالتزام"
    assert resolved["year"] == "تاريخ خطة الالتزام"
    assert resolved["inherent"] == "مستوى المخاطر الكامنة"
    assert "residual" not in resolved
    assert resolved["control_category"] == "تصنيف الخطر"
    assert resolved["target_annual"] == "تاريخ التصحيح السنوي المستهدف"
    assert resolved["actual_annual"] == "تاريخ التصحيح السنوي الفعلي"
    rows = rows_from_dataframe(df)
    assert rows[0]["تاريخ خطة الالتزام"] == "2026"
    assert rows[0]["حالة الالتزام بالمتطلبات"] == "ملتزم"
    assert rows[0]["مستوى المخاطر الكامنة"] == "منخفض"
    assert rows[0]["فئة الضوابط الرقابية"] == "سياسات"


def test_legacy_compliance_header_is_not_year():
    df = _sample_df()
    resolved = resolve_columns(df)
    assert resolved["compliance_status"] == "حالة الالتزام"
    assert resolved["year"] == "السنوات"
    assert "year" in resolved
    rows = rows_from_dataframe(df)
    assert rows[0]["حالة الالتزام بالمتطلبات"] == "ملتزم جزئي"
    assert rows[0]["تاريخ خطة الالتزام"] == "2026"


def test_quarterly_date_aliases():
    df = _sample_df().drop(
        columns=["تاريخ التصحيح المستهدف"]
    ).rename(
        columns={
            "فئة الضوابط الرقابية": "تصنيف الخطر",
        }
    )
    df["تاريخ التصحيح المستهدف - الربعي"] = "2026-06-01"
    df["تاريخ التصحيح الفعلي - الربعي"] = "2026-07-01"
    resolved = resolve_columns(df)
    assert resolved["target_quarterly"] == "تاريخ التصحيح المستهدف - الربعي"
    assert resolved["actual_quarterly"] == "تاريخ التصحيح الفعلي - الربعي"
    assert resolved["control_category"] == "تصنيف الخطر"
    rows = rows_from_dataframe(df)
    assert rows[0]["فئة الضوابط الرقابية"] == "سياسات"
    assert rows[0]["تاريخ التصحيح المستهدف - الربعي"] == "2026-Q2"
    assert rows[0]["تاريخ التصحيح الفعلي - الربعي"] == "2026-Q3"


def test_quarterly_q_tokens_join_annual_year():
    df = _sample_df().drop(columns=["تاريخ التصحيح المستهدف"])
    df["تاريخ التصحيح السنوي المستهدف"] = "2026"
    df["تاريخ التصحيح السنوي الفعلي"] = "2027"
    df["تاريخ التصحيح المستهدف - الربعي"] = "Q1"
    df["تاريخ التصحيح الفعلي - الربعي"] = "Q3"
    rows = rows_from_dataframe(df)
    assert rows[0]["تاريخ التصحيح المستهدف - الربعي"] == "2026-Q1"
    assert rows[0]["تاريخ التصحيح الفعلي - الربعي"] == "2027-Q3"


def test_annual_date_columns_bucket_by_year():
    df = _sample_df().drop(columns=["تاريخ التصحيح المستهدف"])
    df["تاريخ التصحيح السنوي المستهدف"] = "2026-03-15"
    df["تاريخ التصحيح السنوي الفعلي"] = "2027-01-21"
    resolved = resolve_columns(df)
    assert resolved["target_annual"] == "تاريخ التصحيح السنوي المستهدف"
    assert resolved["actual_annual"] == "تاريخ التصحيح السنوي الفعلي"
    rows = rows_from_dataframe(df)
    assert rows[0]["تاريخ التصحيح السنوي المستهدف"] == "2026"
    assert rows[0]["تاريخ التصحيح السنوي الفعلي"] == "2027"


def test_annual_year_integers_from_excel_stay_years():
    df = _sample_df().drop(columns=["تاريخ التصحيح المستهدف"])
    df["تاريخ التصحيح السنوي المستهدف"] = 2026
    df["تاريخ التصحيح السنوي الفعلي"] = 2028
    rows = rows_from_dataframe(df)
    assert rows[0]["تاريخ التصحيح السنوي المستهدف"] == "2026"
    assert rows[0]["تاريخ التصحيح السنوي الفعلي"] == "2028"


def test_legal_details_modal_fields():
    from arabic_compliance_dashboard.engine import legal_details_from_rows

    rows = [
        {
            "النص النظامي": "نص تجريبي",
            "المشرع": "وزارة التجارة",
            "الحالة": "مفتوح",
            "email": "danyajouan1@gmail.com",
            "تاريخ التصحيح المستهدف": "1800489600000.0",
            "ملاحظات الالتزام": "بند غير ملتزم",
        }
    ]
    rec = legal_details_from_rows(rows, "نص تجريبي")
    labels = [f["label"] for f in rec["fields"]]
    assert labels[0] == "المشرع"
    assert rec["fields"][0]["value"] == "وزارة التجارة"
    assert "البريد الإلكتروني (email)" not in labels
    assert "البنود/المتطلبات غير الملتزم بها" in labels
    notes = next(f for f in rec["fields"] if f["label"] == "البنود/المتطلبات غير الملتزم بها")
    assert notes["value"] == "بند غير ملتزم"
    target = next(f for f in rec["fields"] if f["label"] == "تاريخ التصحيح المستهدف")
    assert target["value"] == "2027-01-21"
    assert rec["recipient_email"] == "danyajouan1@gmail.com"


def test_assessment_year_excel_column_maps_and_buckets_by_year():
    df = _sample_df()
    df["تاريخ نتائج التقييم خلال السنة الحالية"] = "2025-06-18"
    resolved = resolve_columns(df)
    assert resolved["assessment_year"] == "تاريخ نتائج التقييم خلال السنة الحالية"
    rows = rows_from_dataframe(df)
    assert rows[0]["نتائج التقييم خلال السنة الحالية"] == "Q2"
    from arabic_compliance_dashboard.engine import PARAM_TO_COL, build_summary

    selected = {col: [] for col in PARAM_TO_COL.values()}
    summary = build_summary(rows, selected)
    labels = [item["label"] for item in summary["groups"]["نتائج التقييم خلال السنة الحالية"]]
    assert "Q2" in labels


def test_assessment_quarter_tokens_q1_q3_are_read():
    base = _sample_df().iloc[0].to_dict()
    wrapped = "تاريخ نتائج\nالتقييم خلال\nالسنة الحالية"
    df = pd.DataFrame(
        [
            {**base, wrapped: "Q1"},
            {**base, wrapped: "Q3"},
        ]
    )
    resolved = resolve_columns(df)
    assert resolved["assessment_year"] == wrapped
    rows = rows_from_dataframe(df)
    values = [r["نتائج التقييم خلال السنة الحالية"] for r in rows]
    assert values == ["Q1", "Q3"]


def test_final_compliance_change_from_compliant_previous_year():
    from arabic_compliance_dashboard.engine import PARAM_TO_COL, build_record_list

    prev = "حالة الالتزام النهائي بالمتطلبات للسنة السابقة"
    curr = "حالة الالتزام النهائي بالمتطلبات للسنة الحالية"
    df = pd.DataFrame(
        [
            {**_sample_df().iloc[0].to_dict(), prev: "ملتزم", curr: "غير ملتزم"},
            {**_sample_df().iloc[0].to_dict(), prev: "ملتزم", curr: "ملتزم جزئي"},
            {**_sample_df().iloc[0].to_dict(), prev: "ملتزم", curr: "ملتزم"},
            {**_sample_df().iloc[0].to_dict(), prev: "غير ملتزم", curr: "ملتزم"},
        ]
    )
    resolved = resolve_columns(df)
    assert resolved["final_prev"] == prev
    assert resolved["final_curr"] == curr
    rows = rows_from_dataframe(df)
    selected = {col: [] for col in PARAM_TO_COL.values()}
    out = build_record_list(rows, selected, final_status_change=True)
    assert out["total"] == 2
    currents = {r["final_curr"] for r in out["records"]}
    assert currents == {"غير ملتزم", "ملتزم جزئي"}


def test_corrective_plan_reads_noncompliance_action_header():
    from arabic_compliance_dashboard.engine import assessment_form_from_row

    col = "الإجراء التصحيحي (في حالة عدم الالتزام او الالتزام الجزئي)"
    df = pd.DataFrame(
        [
            {
                **{k: v for k, v in _sample_df().iloc[0].to_dict().items() if k != "الخطة التصحيحية"},
                col: "إغلاق الفجوة الرقابية",
            }
        ]
    )
    resolved = resolve_columns(df)
    assert resolved["corrective_plan"] == col
    rows = rows_from_dataframe(df)
    form = assessment_form_from_row(rows[0])
    assert form["corrective_plan"] == "إغلاق الفجوة الرقابية"


def test_corrective_plan_prefers_noncompliance_action_over_plan_column():
    from arabic_compliance_dashboard.engine import assessment_form_from_row

    col = "الإجراء التصحيحي (في حالة عدم الالتزام أو الالتزام الجزئي)"
    df = pd.DataFrame(
        [
            {
                **_sample_df().iloc[0].to_dict(),
                "الخطة التصحيحية": "خطة قديمة",
                col: "إجراء التصحيح المعتمد",
            }
        ]
    )
    resolved = resolve_columns(df)
    assert resolved["corrective_plan"] == col


def test_corrective_plan_reads_action_slash_header():
    from arabic_compliance_dashboard.engine import assessment_form_from_row

    df = pd.DataFrame(
        [
            {
                **_sample_df().iloc[0].to_dict(),
                "الإجراء / الخطة التصحيحية": "تحديث السياسة واعتمادها",
            }
        ]
    )
    resolved = resolve_columns(df)
    assert resolved["corrective_plan"] == "الإجراء / الخطة التصحيحية"
    rows = rows_from_dataframe(df)
    form = assessment_form_from_row(rows[0])
    assert form["corrective_plan"] == "تحديث السياسة واعتمادها"


def test_assessment_new_report_filters_new_rows_and_builds_form():
    from arabic_compliance_dashboard.engine import PARAM_TO_COL, build_assessment_forms, build_record_list
    from arabic_compliance_dashboard.word_export import build_assessment_forms_docx
    from zipfile import ZipFile
    from io import BytesIO

    col = "التقرير التفصيلي لحالات عدم الالتزام والالتزام الجزئي"
    base = _sample_df().iloc[0].to_dict()
    df = pd.DataFrame(
        [
            {
                **base,
                col: "new",
                "رقم المادة": "12",
                "مخاطر عدم الالتزام": "مخاطرة تشغيلية",
                "البنود/المتطلبات غير الملتزم بها": "بند 1",
                "الخطة التصحيحية": "خطة",
            },
            {**base, col: "old"},
            {**base, col: ""},
        ]
    )
    resolved = resolve_columns(df)
    assert resolved["detailed_report"] == col
    rows = rows_from_dataframe(df)
    selected = {c: [] for c in PARAM_TO_COL.values()}
    listed = build_record_list(rows, selected, assessment_new=True)
    assert listed["total"] == 1
    assert listed["records"][0]["form"]["article_no"] == "12"
    assert listed["records"][0]["form"]["legislator"] == "وزارة التجارة"
    pack = build_assessment_forms(rows, selected)
    assert pack["total"] == 1
    raw = build_assessment_forms_docx(pack["forms"])
    assert raw[:2] == b"PK"
    xml = ZipFile(BytesIO(raw)).read("word/document.xml").decode("utf-8")
    assert "اسم المشرع" in xml
    assert "وزارة التجارة" in xml
    assert "التقرير التفصيلي لحالات عدم الالتزام والالتزام الجزئي" in xml
    assert "أولاً: البيانات الأساسية والإطار التنظيمي" in xml
    assert "حالة الخطة التصحيحية" not in xml


def test_annual_tracking_docx_contains_register_columns():
    from arabic_compliance_dashboard.word_export import build_annual_tracking_docx
    from zipfile import ZipFile
    from io import BytesIO

    raw = build_annual_tracking_docx(
        [
            {
                "legislator": "وزارة التجارة",
                "article_no": "12",
                "observation": "نص نظامي",
                "system_name": "نظام",
                "rating": "مرتفع",
                "department": "إدارة IT",
                "final_prev": "ملتزم",
                "final_curr": "غير ملتزم",
            }
        ]
    )
    assert raw[:2] == b"PK"
    xml = ZipFile(BytesIO(raw)).read("word/document.xml").decode("utf-8")
    assert "تقرير تتبع حالة الالتزام السنوي" in xml
    assert "المشرع" in xml
    assert "رقم المادة" in xml
    assert "وزارة التجارة" in xml


def test_annual_tracking_docx_embeds_logo():
    from io import BytesIO
    from zipfile import ZipFile

    from PIL import Image

    from arabic_compliance_dashboard.word_export import build_annual_tracking_docx

    buf = BytesIO()
    Image.new("RGB", (80, 40), (31, 78, 121)).save(buf, format="PNG")
    raw = build_annual_tracking_docx(
        [
            {
                "legislator": "وزارة",
                "article_no": "1",
                "observation": "نص",
                "rating": "مرتفع",
                "department": "IT",
                "final_prev": "ملتزم",
                "final_curr": "غير ملتزم",
            }
        ],
        logo_bytes=buf.getvalue(),
    )
    names = ZipFile(BytesIO(raw)).namelist()
    assert any(n.startswith("word/media/") for n in names)


def test_assessment_list_docx_contains_legislator_and_article():
    from arabic_compliance_dashboard.word_export import build_assessment_list_docx
    from zipfile import ZipFile
    from io import BytesIO

    raw = build_assessment_list_docx(
        [
            {
                "legislator": "مجلس الضمان",
                "article_no": "5",
                "observation": "نص تقييم",
                "system_name": "نظام الضمان",
                "rating": "مرتفع",
                "department": "إدارة التأمين",
            }
        ]
    )
    xml = ZipFile(BytesIO(raw)).read("word/document.xml").decode("utf-8")
    assert "نتائج تقييم خلال السنة الحالية" in xml
    assert "المشرع" in xml
    assert "رقم المادة" in xml
    assert "مجلس الضمان" in xml
    assert "السنة السابقة" not in xml


def test_assessment_list_docx_embeds_logo():
    from io import BytesIO
    from zipfile import ZipFile

    from PIL import Image

    from arabic_compliance_dashboard.word_export import build_assessment_list_docx

    buf = BytesIO()
    Image.new("RGB", (80, 40), (31, 78, 121)).save(buf, format="PNG")
    raw = build_assessment_list_docx(
        [{"legislator": "وزارة", "article_no": "1", "observation": "نص", "rating": "مرتفع", "department": "IT"}],
        logo_bytes=buf.getvalue(),
    )
    names = ZipFile(BytesIO(raw)).namelist()
    assert any(n.startswith("word/media/") for n in names)


def test_assessment_forms_docx_embeds_logo():
    from io import BytesIO
    from zipfile import ZipFile

    from PIL import Image

    from arabic_compliance_dashboard.word_export import build_assessment_forms_docx

    buf = BytesIO()
    Image.new("RGB", (80, 40), (31, 78, 121)).save(buf, format="PNG")
    raw = build_assessment_forms_docx(
        [{"legislator": "وزارة", "article_no": "1", "observation": "نص"}],
        logo_bytes=buf.getvalue(),
    )
    names = ZipFile(BytesIO(raw)).namelist()
    assert any(n.startswith("word/media/") for n in names)


def test_aging_matrix_docx_contains_period_and_risk_headers():
    from io import BytesIO
    from zipfile import ZipFile

    from arabic_compliance_dashboard.engine import COL_RESIDUAL, COL_STATUS, COL_TARGET, PARAM_TO_COL, compute_aging
    from arabic_compliance_dashboard.word_export import build_aging_matrix_docx

    rows = [
        {
            COL_STATUS: "مفتوح",
            COL_RESIDUAL: "متوسط",
            COL_TARGET: "2026-01-01",
        }
    ]
    selected = {col: [] for col in PARAM_TO_COL.values()}
    payload = compute_aging(rows, selected, "2026-06-01", "target")
    raw = build_aging_matrix_docx(payload)
    xml = ZipFile(BytesIO(raw)).read("word/document.xml").decode("utf-8")
    assert "ملخص التقادم" in xml
    assert "الفترة الزمنية" in xml
    assert "مرتفع جداً" in xml
    assert "المجموع" in xml
    assert "لم يحن بعد" in xml


def test_aging_matrix_docx_embeds_logo():
    from io import BytesIO
    from zipfile import ZipFile

    from PIL import Image

    from arabic_compliance_dashboard.word_export import build_aging_matrix_docx

    buf = BytesIO()
    Image.new("RGB", (80, 40), (31, 78, 121)).save(buf, format="PNG")
    raw = build_aging_matrix_docx(
        {
            "reference": "2026-06-01",
            "risk_columns": [{"id": "medium", "label": "متوسط", "color": "#c9a227", "text_color": "#1e293b"}],
            "time_rows": [{"id": "lt_6m", "label": "أقل من 6 أشهر", "cells": {"medium": 1}, "total": 1}],
            "over_year_rows": [],
            "column_totals": {"medium": 1},
            "grand_total": 1,
        },
        logo_bytes=buf.getvalue(),
    )
    names = ZipFile(BytesIO(raw)).namelist()
    assert any(n.startswith("word/media/") for n in names)


def test_plan_status_report_groups_department_schedule_and_risk():
    from arabic_compliance_dashboard.engine import (
        COL_DEPT,
        COL_LEGAL,
        COL_RESIDUAL,
        COL_STATUS,
        COL_TARGET,
        PARAM_TO_COL,
        compute_plan_status_report,
    )

    rows = [
        {
            COL_DEPT: "إدارة التأمين",
            COL_LEGAL: "نص أ",
            COL_STATUS: "مفتوحة ضمن الجدول الزمني",
            COL_RESIDUAL: "مرتفع",
            COL_TARGET: "2026-12-01",
        },
        {
            COL_DEPT: "إدارة التأمين",
            COL_LEGAL: "نص ب",
            COL_STATUS: "مفتوحة تجاوزت الجدول الزمني",
            COL_RESIDUAL: "متوسط",
            COL_TARGET: "2026-01-01",
        },
        {
            COL_DEPT: "إدارة تكنولوجيا المعلومات",
            COL_LEGAL: "نص ج",
            COL_STATUS: "مغلق",
            COL_RESIDUAL: "منخفض",
            COL_TARGET: "2026-01-01",
        },
        {
            COL_DEPT: "إدارة التأمين",
            COL_LEGAL: "نص أ",
            COL_STATUS: "مفتوحة ضمن الجدول الزمني",
            COL_RESIDUAL: "مرتفع جدا",
            COL_TARGET: "2026-11-01",
        },
    ]
    selected = {col: [] for col in PARAM_TO_COL.values()}
    out = compute_plan_status_report(rows, selected, "2026-06-01")
    by_dept = {d["id"]: d for d in out["departments"]}
    assert "إدارة التأمين" in by_dept
    assert "إدارة تكنولوجيا المعلومات" not in by_dept
    insurance = by_dept["إدارة التأمين"]
    assert insurance["legal_text_count"] == 2
    assert insurance["within"]["high"] == 1
    assert insurance["within"]["very_high"] == 1
    assert insurance["within_total"] == 2
    assert insurance["overdue"]["medium"] == 1
    assert insurance["overdue_total"] == 1


def test_plan_status_docx_contains_headers():
    from io import BytesIO
    from zipfile import ZipFile

    from arabic_compliance_dashboard.engine import (
        COL_DEPT,
        COL_LEGAL,
        COL_RESIDUAL,
        COL_STATUS,
        PARAM_TO_COL,
        compute_plan_status_report,
    )
    from arabic_compliance_dashboard.word_export import build_plan_status_docx

    rows = [
        {
            COL_DEPT: "إدارة التأمين",
            COL_LEGAL: "نص",
            COL_STATUS: "مفتوحة ضمن الجدول الزمني",
            COL_RESIDUAL: "منخفض",
        }
    ]
    selected = {col: [] for col in PARAM_TO_COL.values()}
    payload = compute_plan_status_report(rows, selected, "2026-06-01")
    xml = ZipFile(BytesIO(build_plan_status_docx(payload))).read("word/document.xml").decode("utf-8")
    assert "حالة خطط المعالجة" in xml
    assert "الادارة او الجهة المعنية" in xml
    assert "عدد النصوص النظامية" in xml
    assert "مفتوحة ضمن الجدول الزمني" in xml
    assert "مفتوحة تجاوزت الجدول الزمني" in xml
    assert "إدارة التأمين" in xml


def test_program_status_report_counts_compliance_by_department():
    from arabic_compliance_dashboard.engine import (
        COL_DEPT,
        COL_LEGAL,
        PARAM_TO_COL,
        compute_program_status_report,
    )

    rows = [
        {
            COL_DEPT: "إدارة التأمين",
            COL_LEGAL: "نص أ",
            "حالة الالتزام بالمتطلبات": "ملتزم",
        },
        {
            COL_DEPT: "إدارة التأمين",
            COL_LEGAL: "نص ب",
            "حالة الالتزام وفقًا لإدارة الالتزام": "غير ملتزم",
        },
        {
            COL_DEPT: "إدارة التأمين",
            COL_LEGAL: "نص ج",
            "حالة الالتزام وفقًا لإدارة الالتزام": "ملتزم جزئي",
        },
        {
            COL_DEPT: "إدارة تكنولوجيا المعلومات",
            COL_LEGAL: "نص د",
            "حالة الالتزام بالمتطلبات": "ملتزم",
        },
    ]
    selected = {col: [] for col in PARAM_TO_COL.values()}
    out = compute_program_status_report(rows, selected)
    by_dept = {d["id"]: d for d in out["departments"]}
    insurance = by_dept["إدارة التأمين"]
    assert insurance["legal_text_count"] == 3
    assert insurance["compliant"] == 1
    assert insurance["noncompliant"] == 1
    assert insurance["partial"] == 1
    assert by_dept["إدارة تكنولوجيا المعلومات"]["compliant"] == 1
    assert out["overall"]["id"] == "red"
    assert out["totals"]["compliant"] == 2


def test_program_status_docx_contains_headers():
    from io import BytesIO
    from zipfile import ZipFile

    from arabic_compliance_dashboard.engine import COL_DEPT, COL_LEGAL, PARAM_TO_COL, compute_program_status_report
    from arabic_compliance_dashboard.word_export import build_program_status_docx

    rows = [
        {
            COL_DEPT: "إدارة التأمين",
            COL_LEGAL: "نص",
            "حالة الالتزام بالمتطلبات": "ملتزم",
        }
    ]
    payload = compute_program_status_report(rows, {col: [] for col in PARAM_TO_COL.values()})
    xml = ZipFile(BytesIO(build_program_status_docx(payload))).read("word/document.xml").decode("utf-8")
    assert "الحالة العامة لبرنامج الالتزام" in xml
    assert "أخضر" in xml
    assert "عدد المتطلبات الملتزم بها" in xml
    assert "إدارة التأمين" in xml


def test_legal_text_docx_contains_text_and_fields():
    from io import BytesIO
    from zipfile import ZipFile

    from arabic_compliance_dashboard.word_export import build_legal_text_docx

    raw = build_legal_text_docx(
        "يتحمل صاحب العمل المسؤولية",
        [
            {"label": "المشرع", "value": "مجلس الوزراء"},
            {"label": "مستوى المخاطر الكامنة", "value": "متوسط"},
            {"label": "الإدارة", "value": "إدارة تكنولوجيا المعلومات"},
        ],
    )
    xml = ZipFile(BytesIO(raw)).read("word/document.xml").decode("utf-8")
    assert "النص النظامي" in xml
    assert "يتحمل صاحب العمل المسؤولية" in xml
    assert "مجلس الوزراء" in xml
    assert "إدارة تكنولوجيا المعلومات" in xml


def test_legal_text_docx_embeds_logo():
    from io import BytesIO
    from zipfile import ZipFile

    from PIL import Image

    from arabic_compliance_dashboard.word_export import build_legal_text_docx

    buf = BytesIO()
    Image.new("RGB", (80, 40), (31, 78, 121)).save(buf, format="PNG")
    raw = build_legal_text_docx("نص", [{"label": "المشرع", "value": "وزارة"}], logo_bytes=buf.getvalue())
    names = ZipFile(BytesIO(raw)).namelist()
    assert any(n.startswith("word/media/") for n in names)


def test_plan_status_report_groups_department_schedule_and_risk():
    from arabic_compliance_dashboard.engine import (
        COL_DEPT,
        COL_LEGAL,
        COL_RESIDUAL,
        COL_STATUS,
        COL_TARGET,
        PARAM_TO_COL,
        compute_plan_status_report,
    )

    rows = [
        {
            COL_DEPT: "إدارة التأمين",
            COL_LEGAL: "نص أ",
            COL_STATUS: "مفتوحة ضمن الجدول الزمني",
            COL_RESIDUAL: "مرتفع",
            COL_TARGET: "2026-12-01",
        },
        {
            COL_DEPT: "إدارة التأمين",
            COL_LEGAL: "نص ب",
            COL_STATUS: "مفتوحة تجاوزت الجدول الزمني",
            COL_RESIDUAL: "متوسط",
            COL_TARGET: "2026-01-01",
        },
        {
            COL_DEPT: "إدارة تكنولوجيا المعلومات",
            COL_LEGAL: "نص ج",
            COL_STATUS: "مغلق",
            COL_RESIDUAL: "منخفض",
            COL_TARGET: "2026-01-01",
        },
        {
            COL_DEPT: "إدارة التأمين",
            COL_LEGAL: "نص أ",
            COL_STATUS: "مفتوحة ضمن الجدول الزمني",
            COL_RESIDUAL: "مرتفع جدا",
            COL_TARGET: "2026-11-01",
        },
    ]
    selected = {col: [] for col in PARAM_TO_COL.values()}
    out = compute_plan_status_report(rows, selected, "2026-06-01")
    by_dept = {d["id"]: d for d in out["departments"]}
    assert "إدارة التأمين" in by_dept
    assert "إدارة تكنولوجيا المعلومات" not in by_dept
    insurance = by_dept["إدارة التأمين"]
    assert insurance["legal_text_count"] == 2
    assert insurance["within"]["high"] == 1
    assert insurance["within"]["very_high"] == 1
    assert insurance["within_total"] == 2
    assert insurance["overdue"]["medium"] == 1
    assert insurance["overdue_total"] == 1


def test_plan_status_docx_contains_headers():
    from io import BytesIO
    from zipfile import ZipFile

    from arabic_compliance_dashboard.engine import (
        COL_DEPT,
        COL_LEGAL,
        COL_RESIDUAL,
        COL_STATUS,
        PARAM_TO_COL,
        compute_plan_status_report,
    )
    from arabic_compliance_dashboard.word_export import build_plan_status_docx

    rows = [
        {
            COL_DEPT: "إدارة التأمين",
            COL_LEGAL: "نص",
            COL_STATUS: "مفتوحة ضمن الجدول الزمني",
            COL_RESIDUAL: "منخفض",
        }
    ]
    selected = {col: [] for col in PARAM_TO_COL.values()}
    payload = compute_plan_status_report(rows, selected, "2026-06-01")
    xml = ZipFile(BytesIO(build_plan_status_docx(payload))).read("word/document.xml").decode("utf-8")
    assert "حالة خطط المعالجة" in xml
    assert "الادارة او الجهة المعنية" in xml
    assert "عدد النصوص النظامية" in xml
    assert "مفتوحة ضمن الجدول الزمني" in xml
    assert "مفتوحة تجاوزت الجدول الزمني" in xml
    assert "إدارة التأمين" in xml


def test_excel_serial_target_date_becomes_calendar_date():
    from arabic_compliance_dashboard.engine import assessment_form_from_row
    from arabic_compliance_dashboard.schema import display_date_from_cell

    assert display_date_from_cell("46112.0").startswith("2026-")
    df = pd.DataFrame(
        [
            {
                **_sample_df().iloc[0].to_dict(),
                "تاريخ التصحيح المستهدف": 46112.0,
            }
        ]
    )
    rows = rows_from_dataframe(df)
    assert rows[0]["تاريخ التصحيح المستهدف"] == display_date_from_cell("46112.0")
    assert "." not in rows[0]["تاريخ التصحيح المستهدف"]
    form = assessment_form_from_row(rows[0])
    assert form["target_date"] == rows[0]["تاريخ التصحيح المستهدف"]
