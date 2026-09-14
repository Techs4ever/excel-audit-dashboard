"""Arabic compliance dashboard — Excel column schema and validation."""
from __future__ import annotations

import re
import unicodedata
from datetime import datetime
from typing import Any

import pandas as pd

from audit_app.dashboard_template_codes import TEMPLATE_CODE_CD

TEMPLATE_CODE = TEMPLATE_CODE_CD
BLANK = "(blank)"

# Logical key -> canonical Arabic column name + accepted header aliases
REQUIRED_COLUMNS: dict[str, tuple[str, ...]] = {
    "status": ("حالة الخطة التصحيحية", "الحالة"),
    "department": ("الإدارة المسؤولة",),
    "legislator": ("المشرع",),
    "system_name": ("اسم النظام", "النظام"),
    "authority": ("الهيئة التابعة",),
    "regulation": ("اللائحة",),
    "legal_text": ("النص النظامي", "النص بالكامل"),
    "compliance_status": (
        "حالة الالتزام بالمتطلبات",
        "حالة الالتزام وفقًا لإدارة الالتزام",
        "حالة الالتزام",
    ),
    "control_category": ("فئة الضوابط الرقابية", "تصنيف الخطر"),
}

OPTIONAL_COLUMNS: dict[str, tuple[str, ...]] = {
    "inherent": ("مستوى المخاطر الكامنة", "تصنيف المخاطر الكامنة"),
    "residual": ("تصنيف المخاطر المتبقية", "مستوى المخاطر المتبقية"),
    "year": ("تاريخ خطة الالتزام", "السنوات", "السنة"),
    "assessment_year": (
        "تاريخ نتائج التقييم خلال السنة الحالية",
        "نتائج التقييم خلال السنة الحالية",
    ),
    "target_annual": ("تاريخ التصحيح السنوي المستهدف",),
    "target_quarterly": ("تاريخ التصحيح المستهدف - الربعي",),
    "actual_annual": (
        "تاريخ التصحيح السنوي الفعلي",
        "تاريخ التصحيح الفعلي السنوي",
    ),
    "actual_quarterly": ("تاريخ التصحيح الفعلي - الربعي",),
    "target_date": (
        "تاريخ التصحيح المستهدف",
        "تاريخ التصحيح  المستهدف",
    ),
    "actual_date": ("تاريخ التصحيح الفعلي",),
    "modified_date": (
        "تاريخ التصحيح المعدل",
        "تاريخ التصحيح المستهدف المعدل",
    ),
    "holding_company": ("الشركة القابضة",),
    "subsidiary_company": ("الشركة التابعة",),
    "task_owner": ("مالك المهمة / مالك الإجراء",),
    "responsible_person": ("الشخص المسؤول",),
    "corrective_plan": (
        "الإجراء التصحيحي (في حالة عدم الالتزام او الالتزام الجزئي)",
        "الإجراء التصحيحي (في حالة عدم الالتزام أو الالتزام الجزئي)",
        "الإجراء التصحيحي",
        "الخطة التصحيحية",
        "الإجراء / الخطة التصحيحية",
        "الإجراء",
        "الإجراءات التصحيحية",
        "خطة التصحيح",
    ),
    "mgmt_notes": ("ملاحظات الإدارة",),
    "compliance_notes": (
        "البنود/المتطلبات غير الملتزم بها",
        "ملاحظات الإلتزام",
        "ملاحظات الالتزام",
    ),
    "final_prev": ("حالة الالتزام النهائي بالمتطلبات للسنة السابقة",),
    "final_curr": ("حالة الالتزام النهائي بالمتطلبات للسنة الحالية",),
    "email": ("email", "البريد الإلكتروني"),
    "detailed_report": (
        "التقرير التفصيلي لحالات عدم الالتزام والالتزام الجزئي",
    ),
    "article_number": ("رقم المادة",),
    "noncompliance_risk": ("مخاطر عدم الالتزام",),
}

# Canonical names used in dashboard rows (after normalization)
CANONICAL_NAMES: dict[str, str] = {
    "inherent": "مستوى المخاطر الكامنة",
    "residual": "تصنيف المخاطر المتبقية",
    "status": "حالة الخطة التصحيحية",
    "department": "الإدارة المسؤولة",
    "legislator": "المشرع",
    "system_name": "اسم النظام",
    "authority": "الهيئة التابعة",
    "regulation": "اللائحة",
    "legal_text": "النص النظامي",
    "compliance_status": "حالة الالتزام بالمتطلبات",
    "control_category": "فئة الضوابط الرقابية",
    "year": "تاريخ خطة الالتزام",
    "assessment_year": "نتائج التقييم خلال السنة الحالية",
    "target_annual": "تاريخ التصحيح السنوي المستهدف",
    "target_quarterly": "تاريخ التصحيح المستهدف - الربعي",
    "actual_annual": "تاريخ التصحيح السنوي الفعلي",
    "actual_quarterly": "تاريخ التصحيح الفعلي - الربعي",
    "target_date": "تاريخ التصحيح المستهدف",
    "actual_date": "تاريخ التصحيح الفعلي",
    "modified_date": "تاريخ التصحيح المعدل",
    "holding_company": "الشركة القابضة",
    "subsidiary_company": "الشركة التابعة",
    "task_owner": "مالك المهمة / مالك الإجراء",
    "responsible_person": "الشخص المسؤول",
    "corrective_plan": "الخطة التصحيحية",
    "mgmt_notes": "ملاحظات الإدارة",
    "compliance_notes": "البنود/المتطلبات غير الملتزم بها",
    "final_prev": "حالة الالتزام النهائي بالمتطلبات للسنة السابقة",
    "final_curr": "حالة الالتزام النهائي بالمتطلبات للسنة الحالية",
    "email": "email",
    "detailed_report": "التقرير التفصيلي لحالات عدم الالتزام والالتزام الجزئي",
    "article_number": "رقم المادة",
    "noncompliance_risk": "مخاطر عدم الالتزام",
}

YEAR_BUCKET_COLUMNS = (
    CANONICAL_NAMES["year"],
    CANONICAL_NAMES["target_annual"],
    CANONICAL_NAMES["actual_annual"],
)
QUARTER_BUCKET_COLUMNS = (
    CANONICAL_NAMES["target_quarterly"],
    CANONICAL_NAMES["actual_quarterly"],
)
DISPLAY_DATE_COLUMNS = (
    CANONICAL_NAMES["target_date"],
    CANONICAL_NAMES["actual_date"],
    CANONICAL_NAMES["modified_date"],
)

EXCEL_EXTENSIONS = {".xlsx", ".xls", ".xlsm"}

# Filled across Excel's used range (company name, 0 in الهيئة, …). They must not
# keep template rows that have no compliance record.
_NON_RECORD_LOGICAL_KEYS = frozenset(
    {"department", "authority", "holding_company", "subsidiary_company", "email"}
)
_BLANK_TOKENS = frozenset(
    {"", "nan", "none", "nat", "null", "<na>", "(blank)", "-", "—", "n/a", "na"}
)


def _norm_header(value: Any) -> str:
    s = unicodedata.normalize("NFKC", str(value or "").strip())
    s = s.replace("\u200f", "").replace("\u200e", "").replace("\u00a0", " ")
    return " ".join(s.split()).casefold()


def _build_header_map(columns: list[Any]) -> dict[str, str]:
    """Map normalized header -> original column name."""
    out: dict[str, str] = {}
    for col in columns:
        key = _norm_header(col)
        if key and key not in out:
            out[key] = str(col)
    return out


def resolve_columns(df: pd.DataFrame) -> dict[str, str]:
    """Resolve logical keys to actual DataFrame column names."""
    header_map = _build_header_map(list(df.columns))
    resolved: dict[str, str] = {}
    used: set[str] = set()
    for logical, aliases in {**REQUIRED_COLUMNS, **OPTIONAL_COLUMNS}.items():
        for alias in aliases:
            key = _norm_header(alias)
            actual = header_map.get(key)
            if actual and actual not in used:
                resolved[logical] = actual
                used.add(actual)
                break
    modified_prefix = _norm_header("تاريخ التصحيح المعدل")
    if "modified_date" not in resolved:
        for key, actual in header_map.items():
            if key.startswith(modified_prefix) and actual not in used:
                resolved["modified_date"] = actual
                break
    if "assessment_year" not in resolved:
        for key, actual in header_map.items():
            if actual in used:
                continue
            if "نتائج التقييم" in key and "السنة الحالية" in key:
                resolved["assessment_year"] = actual
                used.add(actual)
                break
    if "final_prev" not in resolved:
        for key, actual in header_map.items():
            if actual in used:
                continue
            if "الالتزام النهائي" in key and "السابقة" in key:
                resolved["final_prev"] = actual
                used.add(actual)
                break
    if "final_curr" not in resolved:
        for key, actual in header_map.items():
            if actual in used:
                continue
            if "الالتزام النهائي" in key and "الحالية" in key:
                resolved["final_curr"] = actual
                used.add(actual)
                break
    if "detailed_report" not in resolved:
        for key, actual in header_map.items():
            if actual in used:
                continue
            if "التقرير التفصيلي" in key and "عدم الالتزام" in key:
                resolved["detailed_report"] = actual
                used.add(actual)
                break
    if "corrective_plan" not in resolved:
        for key, actual in header_map.items():
            if actual in used:
                continue
            if "حالة" in key and "الخطة التصحيحية" in key:
                continue
            if "مالك" in key and "الإجراء" in key:
                continue
            if "الإجراء التصحيحي" in key:
                resolved["corrective_plan"] = actual
                used.add(actual)
                break
    if "corrective_plan" not in resolved:
        for key, actual in header_map.items():
            if actual in used:
                continue
            if "حالة" in key and "الخطة التصحيحية" in key:
                continue
            if "مالك" in key and "الإجراء" in key:
                continue
            if "الخطة التصحيحية" in key or ("الإجراء" in key and "خطة" in key):
                resolved["corrective_plan"] = actual
                used.add(actual)
                break
    return resolved


def _parsed_datetime(value: Any) -> datetime | None:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    if isinstance(value, datetime):
        return value
    s = str(value).strip()
    if not s or s == BLANK:
        return None
    try:
        if "T" in s:
            return datetime.fromisoformat(s.replace("Z", ""))
        if re.fullmatch(r"-?\d+(?:\.\d+)?", s):
            fv = float(s)
            if fv >= 1e12:
                return datetime.utcfromtimestamp(fv / 1000.0)
            if 1e9 <= fv < 1e12:
                return datetime.utcfromtimestamp(fv)
            if 20000 <= fv <= 80000:
                from datetime import timedelta

                return datetime(1899, 12, 30) + timedelta(days=fv)
        if re.match(r"\d{4}-\d{2}-\d{2}", s):
            return datetime.strptime(s[:10], "%Y-%m-%d")
    except (ValueError, OSError, OverflowError):
        return None
    return None


def year_from_date_cell(value: Any) -> str:
    """Extract calendar year from a year number, date, or datetime cell."""
    if value is None:
        return BLANK
    try:
        if pd.isna(value):
            return BLANK
    except (TypeError, ValueError):
        pass
    try:
        as_int = int(value)
        if 1900 <= as_int <= 2100 and float(value) == as_int:
            return str(as_int)
    except (TypeError, ValueError):
        pass
    s = unicodedata.normalize("NFKC", str(value)).strip()
    if not s or s == BLANK:
        return BLANK
    m = re.fullmatch(r"(\d{4})(?:\.0+)?", s)
    if m:
        y = int(m.group(1))
        if 1900 <= y <= 2100:
            return str(y)
    dt = _parsed_datetime(value)
    return str(dt.year) if dt else BLANK


def quarter_from_date_cell(value: Any) -> str:
    """Extract YYYY-Qn from a date, or Qn when the cell is only a quarter token."""
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return BLANK
    s = unicodedata.normalize("NFKC", str(value)).strip()
    if not s or s == BLANK:
        return BLANK
    m = re.fullmatch(r"(\d{4})\s*-?\s*Q\s*([1-4])", s, re.I)
    if m:
        return f"{m.group(1)}-Q{m.group(2)}"
    m = re.fullmatch(r"Q\s*([1-4])\s*-?\s*(\d{4})", s, re.I)
    if m:
        return f"{m.group(2)}-Q{m.group(1)}"
    m = re.fullmatch(r"Q\s*([1-4])", s, re.I)
    if m:
        return f"Q{m.group(1)}"
    m = re.fullmatch(r"الربع\s*([1-4])", s)
    if m:
        return f"Q{m.group(1)}"
    dt = _parsed_datetime(value)
    if not dt:
        return BLANK
    q = (dt.month - 1) // 3 + 1
    return f"{dt.year}-Q{q}"


def display_date_from_cell(value: Any) -> str:
    """Turn an Excel serial, datetime, or ISO cell into YYYY-MM-DD."""
    dt = _parsed_datetime(value)
    if dt:
        return dt.strftime("%Y-%m-%d")
    s = unicodedata.normalize("NFKC", str(value or "")).strip()
    if not s or s == BLANK:
        return BLANK
    m = re.match(r"(\d{4}-\d{2}-\d{2})", s)
    return m.group(1) if m else BLANK


def assessment_quarter_from_cell(value: Any) -> str:
    """Keep Q1–Q4 for نتائج التقييم خلال السنة الحالية (Excel often stores Q1/Q3, not a year)."""
    parsed = quarter_from_date_cell(value)
    if parsed == BLANK:
        s = unicodedata.normalize("NFKC", str(value or "")).strip()
        m = re.search(r"q\s*([1-4])", s, re.I)
        if m:
            return f"Q{m.group(1)}"
        m = re.search(r"الربع\s*([1-4])", s)
        if m:
            return f"Q{m.group(1)}"
        return BLANK
    m = re.fullmatch(r"(?:\d{4}-)?Q([1-4])", parsed, re.I)
    return f"Q{m.group(1)}" if m else parsed


def _year_for_quarter_row(row: dict[str, str], col: str) -> str:
    if col == CANONICAL_NAMES["target_quarterly"]:
        sources = (
            CANONICAL_NAMES["target_annual"],
            CANONICAL_NAMES["target_date"],
            CANONICAL_NAMES["year"],
        )
    else:
        sources = (
            CANONICAL_NAMES["actual_annual"],
            CANONICAL_NAMES["year"],
            CANONICAL_NAMES["target_date"],
        )
    for src in sources:
        y = year_from_date_cell(row.get(src, BLANK))
        if y != BLANK:
            return y
    return BLANK


def enrich_row_year(row: dict[str, str]) -> dict[str, str]:
    """Fill تاريخ خطة الالتزام from the date cell or from تاريخ التصحيح المستهدف."""
    year_col = CANONICAL_NAMES["year"]
    target_col = CANONICAL_NAMES["target_date"]
    existing = row.get(year_col, BLANK)
    if existing and existing != BLANK:
        if re.fullmatch(r"\d{4}", str(existing).strip()):
            return row
        extracted = year_from_date_cell(existing)
        if extracted != BLANK:
            row[year_col] = extracted
        return row
    row[year_col] = year_from_date_cell(
        row.get(target_col) or row.get(CANONICAL_NAMES["target_annual"])
    )
    return row


def enrich_row_date_dims(row: dict[str, str]) -> dict[str, str]:
    """Normalize annual date columns to years and quarterly columns to YYYY-Qn."""
    for col in YEAR_BUCKET_COLUMNS:
        if col == CANONICAL_NAMES["year"]:
            continue
        existing = row.get(col, BLANK)
        if not existing or existing == BLANK:
            if col == CANONICAL_NAMES["target_annual"]:
                existing = row.get(CANONICAL_NAMES["target_date"], BLANK)
            elif col == CANONICAL_NAMES["actual_annual"]:
                existing = row.get(CANONICAL_NAMES.get("actual_date", "تاريخ التصحيح الفعلي"), BLANK)
            if not existing or existing == BLANK:
                row[col] = BLANK
                continue
        parsed = year_from_date_cell(existing)
        if parsed != BLANK:
            row[col] = parsed
            continue
        if col == CANONICAL_NAMES["target_annual"]:
            parsed = year_from_date_cell(row.get(CANONICAL_NAMES["target_date"], BLANK))
        elif col == CANONICAL_NAMES["actual_annual"]:
            parsed = year_from_date_cell(row.get("تاريخ التصحيح الفعلي", BLANK))
        row[col] = parsed
    for col in QUARTER_BUCKET_COLUMNS:
        existing = row.get(col, BLANK)
        if not existing or existing == BLANK:
            row[col] = BLANK
            continue
        if re.fullmatch(r"\d{4}-Q[1-4]", str(existing).strip(), re.I):
            continue
        parsed = quarter_from_date_cell(existing)
        if re.fullmatch(r"Q[1-4]", parsed):
            year = _year_for_quarter_row(row, col)
            row[col] = f"{year}-{parsed}" if year != BLANK else parsed
        else:
            row[col] = parsed
    assessment_col = CANONICAL_NAMES["assessment_year"]
    existing = row.get(assessment_col, BLANK)
    if existing and existing != BLANK:
        parsed = assessment_quarter_from_cell(existing)
        if parsed != BLANK:
            row[assessment_col] = parsed
    for col in DISPLAY_DATE_COLUMNS:
        existing = row.get(col, BLANK)
        if not existing or existing == BLANK:
            continue
        parsed = display_date_from_cell(existing)
        if parsed != BLANK:
            row[col] = parsed
    return row


def normalize_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    """
    Rename columns to canonical Arabic names and drop duplicate alias columns.
    Returns a new DataFrame.
    """
    colmap = resolve_columns(df)
    rename: dict[str, str] = {}
    for logical, src_col in colmap.items():
        canonical = CANONICAL_NAMES.get(logical)
        if canonical and src_col in df.columns and src_col not in rename:
            rename[src_col] = canonical
    out = df.rename(columns=rename)
    # Keep only canonical + any unmapped columns that aren't duplicates
    keep = list(dict.fromkeys(rename.values()))
    extra = [c for c in out.columns if c not in keep and c not in rename]
    return out[[c for c in keep if c in out.columns] + extra]


def is_blank_cell(value: Any) -> bool:
    """True for missing, whitespace, or placeholder tokens that are not real data."""
    if value is None:
        return True
    try:
        if pd.isna(value):
            return True
    except (TypeError, ValueError):
        pass
    if isinstance(value, bool):
        return False
    if isinstance(value, (int, float)) and value == 0:
        return True
    s = unicodedata.normalize("NFKC", str(value)).strip()
    if s in {"0", "0.0"}:
        return True
    return (not s) or s.casefold() in _BLANK_TOKENS


def record_content_columns(df: pd.DataFrame) -> list[str]:
    """Excel columns that mean a real compliance row exists."""
    resolved = resolve_columns(df)
    cols = [src for key, src in resolved.items() if key not in _NON_RECORD_LOGICAL_KEYS]
    return [c for c in cols if c in df.columns]


def dataframe_row_has_record(row: pd.Series, content_cols: list[str]) -> bool:
    for col in content_cols:
        if col in row.index and not is_blank_cell(row[col]):
            return True
    return False


def dict_row_has_record(row: dict[str, str]) -> bool:
    for logical, canonical in CANONICAL_NAMES.items():
        if logical in _NON_RECORD_LOGICAL_KEYS:
            continue
        if not is_blank_cell(row.get(canonical, BLANK)):
            return True
    return False


def drop_empty_rows_keep_schema_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Drop unused Excel template rows, but keep schema header columns even if blank."""
    if df is None or df.empty:
        return df
    known = {_norm_header(a) for aliases in {**REQUIRED_COLUMNS, **OPTIONAL_COLUMNS}.values() for a in aliases}
    known.update(_norm_header(name) for name in CANONICAL_NAMES.values())
    out = df
    content_cols = record_content_columns(out)
    if content_cols:
        keep = out.apply(lambda r: dataframe_row_has_record(r, content_cols), axis=1)
        out = out.loc[keep]
    else:
        keep = out.apply(lambda r: any(not is_blank_cell(v) for v in r.tolist()), axis=1)
        out = out.loc[keep]
    drop_cols = []
    for col in out.columns:
        series = out[col]
        empty = series.map(is_blank_cell)
        if bool(empty.all()) and _norm_header(col) not in known:
            drop_cols.append(col)
    if drop_cols:
        out = out.drop(columns=drop_cols)
    return out.reset_index(drop=True)


def _err(locale: str, ar: str, en: str) -> str:
    return ar if locale == "ar" else en


def validate_schema(df: pd.DataFrame, locale: str = "ar") -> dict[str, str]:
    """
    Validate required columns exist and at least one data row remains.
    Returns resolved logical->column map.
    Raises ValueError with user-facing message on failure.
    """
    if df is None or df.empty:
        raise ValueError(
            _err(locale, "الملف فارغ أو لا يحتوي على بيانات.", "File is empty or has no data.")
        )

    resolved = resolve_columns(df)
    missing = []
    for logical, aliases in REQUIRED_COLUMNS.items():
        if logical not in resolved:
            missing.append(aliases[0])

    if missing:
        joined = "، ".join(missing)
        raise ValueError(
            _err(
                locale,
                f"أعمدة إلزامية ناقصة: {joined}",
                f"Missing required columns: {', '.join(missing)}",
            )
        )

    content_cols = record_content_columns(df)
    if content_cols:
        has_record = bool(df.apply(lambda r: dataframe_row_has_record(r, content_cols), axis=1).any())
    else:
        has_record = bool(df.apply(lambda r: any(not is_blank_cell(v) for v in r.tolist()), axis=1).any())
    if not has_record:
        raise ValueError(
            _err(
                locale,
                "لا توجد صفوف بيانات في الملف.",
                "No data rows found in the file.",
            )
        )

    return resolved


def rows_from_dataframe(df: pd.DataFrame) -> list[dict[str, str]]:
    """Convert normalized DataFrame to list of row dicts with BLANK for empty cells."""
    normalized = normalize_dataframe(df)
    rows: list[dict[str, str]] = []
    for _, series in normalized.iterrows():
        row: dict[str, str] = {}
        for col in normalized.columns:
            val = series[col]
            if pd.isna(val) or str(val).strip() == "":
                row[str(col)] = BLANK
            else:
                row[str(col)] = str(val).strip()
        enrich_row_year(row)
        enrich_row_date_dims(row)
        if dict_row_has_record(row):
            rows.append(row)
    return rows
