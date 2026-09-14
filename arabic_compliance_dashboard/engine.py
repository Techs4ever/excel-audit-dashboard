"""Arabic compliance dashboard — filter/summary/aging engine (Python port of JS logic)."""
from __future__ import annotations

import re
import unicodedata
from datetime import date, datetime, timedelta
from typing import Any

from .schema import (
    BLANK,
    CANONICAL_NAMES,
    QUARTER_BUCKET_COLUMNS,
    YEAR_BUCKET_COLUMNS,
    quarter_from_date_cell,
)

COL_YEAR = CANONICAL_NAMES["year"]
COL_TARGET = CANONICAL_NAMES["target_date"]
COL_MODIFIED = CANONICAL_NAMES["modified_date"]
COL_STATUS = CANONICAL_NAMES["status"]
COL_RESIDUAL = CANONICAL_NAMES["residual"]
COL_INHERENT = CANONICAL_NAMES["inherent"]
COL_LEGAL = CANONICAL_NAMES["legal_text"]
COL_DEPT = CANONICAL_NAMES["department"]
COL_SYSTEM = CANONICAL_NAMES["system_name"]
COL_LEGISLATOR = CANONICAL_NAMES["legislator"]
COL_FINAL_PREV = CANONICAL_NAMES["final_prev"]
COL_FINAL_CURR = CANONICAL_NAMES["final_curr"]
COL_DETAILED_REPORT = CANONICAL_NAMES["detailed_report"]
COL_ARTICLE = CANONICAL_NAMES["article_number"]
COL_NONCOMPLIANCE_RISK = CANONICAL_NAMES["noncompliance_risk"]
RECORD_LIST_LIMIT = 400
ASSESSMENT_FORM_LIMIT = 2000

PARAM_TO_COL: dict[str, str] = {
    "inherent": CANONICAL_NAMES["inherent"],
    "residual": COL_RESIDUAL,
    "status": COL_STATUS,
    "year": COL_YEAR,
    "assessment_year": CANONICAL_NAMES["assessment_year"],
    "target_annual": CANONICAL_NAMES["target_annual"],
    "target_quarterly": CANONICAL_NAMES["target_quarterly"],
    "actual_annual": CANONICAL_NAMES["actual_annual"],
    "actual_quarterly": CANONICAL_NAMES["actual_quarterly"],
    "department": CANONICAL_NAMES["department"],
    "legislator": CANONICAL_NAMES["legislator"],
    "system_name": CANONICAL_NAMES["system_name"],
    "authority": CANONICAL_NAMES["authority"],
    "regulation": CANONICAL_NAMES["regulation"],
    "legal_text": COL_LEGAL,
    "compliance_status": CANONICAL_NAMES["compliance_status"],
    "control_category": CANONICAL_NAMES["control_category"],
    "subsidiary_company": CANONICAL_NAMES["subsidiary_company"],
    "holding_company": CANONICAL_NAMES["holding_company"],
}

GROUP_DIMS = list(PARAM_TO_COL.values())

DETAIL_FIELDS: list[tuple[str, str]] = [
    (CANONICAL_NAMES["legislator"], CANONICAL_NAMES["legislator"]),
    (COL_STATUS, COL_STATUS),
    (COL_INHERENT, COL_INHERENT),
    (COL_RESIDUAL, COL_RESIDUAL),
    (CANONICAL_NAMES["control_category"], CANONICAL_NAMES["control_category"]),
    (CANONICAL_NAMES["assessment_year"], CANONICAL_NAMES["assessment_year"]),
    (COL_TARGET, COL_TARGET),
    (CANONICAL_NAMES["task_owner"], CANONICAL_NAMES["task_owner"]),
    (CANONICAL_NAMES["responsible_person"], CANONICAL_NAMES["responsible_person"]),
    (CANONICAL_NAMES["corrective_plan"], CANONICAL_NAMES["corrective_plan"]),
    (CANONICAL_NAMES["compliance_notes"], CANONICAL_NAMES["compliance_notes"]),
]

AGING_CONFIG: dict[str, Any] = {
    "risk_columns": [
        {"id": "very_high", "label": "مرتفع جداً", "color": "#8f1d2c", "text_color": "#ffffff"},
        {"id": "high", "label": "مرتفع", "color": "#c24141", "text_color": "#ffffff"},
        {"id": "medium", "label": "متوسط", "color": "#c9a227", "text_color": "#1e293b"},
        {"id": "low", "label": "منخفض", "color": "#3d7a5a", "text_color": "#ffffff"},
        {"id": "very_low", "label": "متدني الانخفاض", "color": "#5a8f6e", "text_color": "#ffffff"},
        {"id": "other", "label": "أخرى", "color": "#7b8794", "text_color": "#ffffff"},
    ],
    "time_rows": [
        {"id": "not_due", "label": "لم يحن بعد"},
        {"id": "lt_6m", "label": "أقل من 6 أشهر"},
        {"id": "lt_1y", "label": "6 أشهر – سنة"},
        {"id": "ge_1y", "label": "أكثر من سنة"},
    ],
    "over_year_rows": [
        {"id": "y1_2", "label": "من سنة إلى سنتين"},
        {"id": "y2_3", "label": "من سنتين إلى 3 سنوات"},
        {"id": "y3_4", "label": "من 3 سنوات إلى 4 سنوات"},
        {"id": "y4_5", "label": "من 4 سنوات إلى 5 سنوات"},
        {"id": "y5p", "label": "أكثر من 5 سنوات"},
    ],
}

AUDIT_COLUMNS = [
    CANONICAL_NAMES["department"],
    CANONICAL_NAMES["legislator"],
    CANONICAL_NAMES["system_name"],
    CANONICAL_NAMES["authority"],
    CANONICAL_NAMES["regulation"],
]


def norm_nfkc(s: Any) -> str:
    return unicodedata.normalize("NFKC", str(s or ""))


def row_value(row: dict[str, str], col: str) -> str:
    v = row.get(col)
    if v is None or v == "":
        return BLANK
    return str(v)


def _detail_aliases(col: str) -> list[str]:
    aliases = [col]
    if col == CANONICAL_NAMES["assessment_year"]:
        aliases.extend(
            [
                "تاريخ نتائج التقييم خلال السنة الحالية",
                CANONICAL_NAMES["assessment_year"],
            ]
        )
    if col == CANONICAL_NAMES["compliance_notes"]:
        aliases.extend(["ملاحظات الإلتزام", "ملاحظات الالتزام"])
    if col in (CANONICAL_NAMES["mgmt_notes"], "ملاحظات الإدارة.1"):
        aliases.extend(["ملاحظات الإدارة.1", CANONICAL_NAMES["mgmt_notes"]])
    out: list[str] = []
    for a in aliases:
        if a not in out:
            out.append(a)
    return out


def format_display_date(value: str) -> str:
    """Turn epoch / ISO / Excel-serial date cells into YYYY-MM-DD for the detail modal."""
    s = str(value or "").strip()
    if not s or s == BLANK:
        return ""
    try:
        if re.fullmatch(r"-?\d+(?:\.\d+)?", s):
            fv = float(s)
            if fv >= 1e12:
                return datetime.utcfromtimestamp(fv / 1000.0).strftime("%Y-%m-%d")
            if 1e9 <= fv < 1e12:
                return datetime.utcfromtimestamp(fv).strftime("%Y-%m-%d")
            if 20000 <= fv <= 80000:
                return (datetime(1899, 12, 30) + timedelta(days=fv)).strftime("%Y-%m-%d")
        if "T" in s:
            return datetime.fromisoformat(s.replace("Z", "")).strftime("%Y-%m-%d")
        if re.match(r"\d{4}-\d{2}-\d{2}", s):
            return s[:10]
    except (ValueError, OSError, OverflowError):
        return s
    return s


def detail_field_value(row: dict[str, str], col: str) -> str:
    raw = BLANK
    for alias in _detail_aliases(col):
        raw = row_value(row, alias)
        if raw != BLANK:
            break
    if raw == BLANK:
        return ""
    if col in (COL_TARGET, COL_MODIFIED):
        return format_display_date(raw) or raw
    return raw


def selected_from_params(params: dict[str, list[str]]) -> dict[str, list[str]]:
    out: dict[str, list[str]] = {}
    for param, col in PARAM_TO_COL.items():
        vals = params.get(param, [])
        out[col] = [str(v).strip() for v in vals if str(v).strip()]
    return out


def apply_filters(
    rows: list[dict[str, str]],
    selected: dict[str, list[str]],
    skip_col: str | None = None,
) -> list[dict[str, str]]:
    def match(row: dict[str, str]) -> bool:
        for col, vals in selected.items():
            if col == skip_col or not vals:
                continue
            if row_value(row, col) not in vals:
                return False
        return True

    return [r for r in rows if match(r)]


_QUARTER_TOKEN_RE = re.compile(r"Q\s*([1-4])", re.I)


def quarter_token(value: Any) -> str:
    """Normalize a cell to Q1–Q4, or empty when no quarter is present."""
    m = _QUARTER_TOKEN_RE.search(norm_nfkc(value))
    return f"Q{m.group(1)}" if m else ""


def record_list_quarter(row: dict[str, str], selected: dict[str, list[str]]) -> str:
    """Pick Q1–Q4 from the quarterly column that matches the current year filter."""
    actual_active = bool(
        selected.get(CANONICAL_NAMES["actual_annual"])
        or selected.get(CANONICAL_NAMES["actual_quarterly"])
    )
    target_active = bool(
        selected.get(CANONICAL_NAMES["target_annual"])
        or selected.get(CANONICAL_NAMES["target_quarterly"])
        or selected.get(CANONICAL_NAMES["year"])
    )
    cols: list[str] = []
    if actual_active and not target_active:
        cols.append(CANONICAL_NAMES["actual_quarterly"])
    else:
        cols.append(CANONICAL_NAMES["target_quarterly"])
        cols.append(CANONICAL_NAMES["actual_quarterly"])
    for col in cols:
        q = quarter_token(row_value(row, col))
        if q:
            return q
    date_cols = [
        CANONICAL_NAMES["target_date"],
        CANONICAL_NAMES.get("actual_date", "تاريخ التصحيح الفعلي"),
        CANONICAL_NAMES["modified_date"],
    ]
    for col in date_cols:
        q = quarter_token(quarter_from_date_cell(row_value(row, col)))
        if q:
            return q
    return ""


def is_fully_compliant_label(value: Any) -> bool:
    """True for ملتزم, false for غير ملتزم / ملتزم جزئي / blank."""
    t = re.sub(r"\s+", " ", unicodedata.normalize("NFKC", str(value or "")).strip())
    if not t or t == BLANK:
        return False
    compact = t.replace(" ", "")
    if "غيرملتزم" in compact or re.search(r"غير\s*ملتزم", t):
        return False
    if "جزئي" in t:
        return False
    return "ملتزم" in t


def final_compliance_regressed(row: dict[str, str]) -> bool:
    """Previous year was ملتزم and current year is anything else."""
    prev = row_value(row, COL_FINAL_PREV)
    curr = row_value(row, COL_FINAL_CURR)
    return is_fully_compliant_label(prev) and not is_fully_compliant_label(curr)


def _header_matches_all(header: str, needles: tuple[str, ...]) -> bool:
    key = unicodedata.normalize("NFKC", str(header or "")).casefold()
    return all(n in key for n in needles)


def row_value_by_header_needles(row: dict[str, str], needles: tuple[str, ...]) -> str:
    for key in row:
        if _header_matches_all(key, needles):
            raw = row_value(row, key)
            if raw != BLANK:
                return raw
    return BLANK


def is_new_detailed_assessment(row: dict[str, str]) -> bool:
    """True when التقرير التفصيلي… is the token new."""
    raw = row_value(row, COL_DETAILED_REPORT)
    if raw == BLANK:
        raw = row_value_by_header_needles(row, ("التقرير التفصيلي", "عدم الالتزام"))
    token = unicodedata.normalize("NFKC", str(raw or "")).strip().casefold()
    return token == "new"


def _form_cell(value: str) -> str:
    if not value or value == BLANK:
        return ""
    return str(value).strip()


def compliance_mgmt_status_from_row(row: dict[str, str]) -> str:
    """Prefer حالة الالتزام وفقًا لإدارة الالتزام; otherwise the mapped compliance status."""
    raw = row_value_by_header_needles(row, ("حالة الالتزام", "إدارة الالتزام"))
    if raw == BLANK:
        raw = row_value(row, CANONICAL_NAMES["compliance_status"])
    return "" if raw == BLANK else raw


def article_number_from_row(row: dict[str, str]) -> str:
    article = row_value(row, COL_ARTICLE)
    if article == BLANK:
        article = row_value_by_header_needles(row, ("رقم المادة",))
    return "" if article == BLANK else article


def corrective_plan_from_row(row: dict[str, str]) -> str:
    plan = row_value_by_header_needles(row, ("الإجراء التصحيحي",))
    if plan == BLANK:
        plan = row_value(row, CANONICAL_NAMES["corrective_plan"])
    if plan != BLANK:
        return _form_cell(plan)
    for key in row:
        nk = unicodedata.normalize("NFKC", str(key or ""))
        if "حالة" in nk and "الخطة التصحيحية" in nk:
            continue
        if "مالك" in nk:
            continue
        if "الإجراء التصحيحي" in nk or "الخطة التصحيحية" in nk or ("الإجراء" in nk and "خطة" in nk) or nk.strip() == "الإجراء":
            raw = row_value(row, key)
            if raw != BLANK:
                return _form_cell(raw)
    return ""


def assessment_form_from_row(row: dict[str, str]) -> dict[str, str]:
    """Map a register row onto the official non-compliance form fields."""
    legal = row_value(row, COL_LEGAL)
    inherent = row_value(row, COL_INHERENT)
    article = article_number_from_row(row)
    risk_note = row_value(row, COL_NONCOMPLIANCE_RISK)
    if risk_note == BLANK:
        risk_note = row_value_by_header_needles(row, ("مخاطر عدم الالتزام",))
    target = detail_field_value(row, COL_TARGET)
    return {
        "legislator": _form_cell(row_value(row, COL_LEGISLATOR)),
        "system_name": _form_cell(row_value(row, COL_SYSTEM)),
        "authority": _form_cell(row_value(row, CANONICAL_NAMES["authority"])),
        "regulation": _form_cell(row_value(row, CANONICAL_NAMES["regulation"])),
        "inherent": _form_cell(inherent),
        "compliance_status": _form_cell(row_value(row, CANONICAL_NAMES["compliance_status"])),
        "article_no": _form_cell(article),
        "legal_text": _form_cell(legal),
        "noncompliant_items": _form_cell(row_value(row, CANONICAL_NAMES["compliance_notes"])),
        "noncompliance_risk": _form_cell(risk_note),
        "corrective_plan": corrective_plan_from_row(row),
        "department": _form_cell(row_value(row, COL_DEPT)),
        "target_date": _form_cell(target),
        "plan_status": _form_cell(row_value(row, COL_STATUS)),
    }


def filter_assessment_new_rows(
    rows: list[dict[str, str]],
    selected: dict[str, list[str]],
) -> list[dict[str, str]]:
    filtered = apply_filters(rows, selected, None)
    return [r for r in filtered if is_new_detailed_assessment(r)]


def build_assessment_forms(
    rows: list[dict[str, str]],
    selected: dict[str, list[str]],
) -> dict[str, Any]:
    filtered = filter_assessment_new_rows(rows, selected)
    forms = [assessment_form_from_row(r) for r in filtered[:ASSESSMENT_FORM_LIMIT]]
    return {
        "total": len(filtered),
        "truncated": len(filtered) > ASSESSMENT_FORM_LIMIT,
        "forms": forms,
    }


def build_record_list(
    rows: list[dict[str, str]],
    selected: dict[str, list[str]],
    *,
    aging_time: str | None = None,
    aging_risk: str | None = None,
    reference_raw: str | None = None,
    final_status_change: bool = False,
    assessment_new: bool = False,
    limit: int | None = None,
) -> dict[str, Any]:
    """Filtered register rows for the second-click drill-down sheet."""
    filtered = apply_filters(rows, selected, None)
    if aging_time or aging_risk:
        ref = parse_date_at_noon(reference_raw or "")
        if not ref:
            filtered = []
        else:
            time_id = aging_time or "all"
            filtered = [r for r in filtered if aging_row_matches(r, ref, time_id, aging_risk)]
    if final_status_change:
        filtered = [r for r in filtered if final_compliance_regressed(r)]
    if assessment_new:
        filtered = [r for r in filtered if is_new_detailed_assessment(r)]
    cap = limit if limit is not None else (ASSESSMENT_FORM_LIMIT if assessment_new else RECORD_LIST_LIMIT)
    records: list[dict[str, Any]] = []
    for row in filtered[:cap]:
        legal = row_value(row, COL_LEGAL)
        system = row_value(row, COL_SYSTEM)
        rating = row_value(row, COL_INHERENT)
        if rating == BLANK:
            rating = row_value(row, COL_RESIDUAL)
        observation = legal if legal != BLANK else system
        dept = row_value(row, COL_DEPT)
        legislator = row_value(row, COL_LEGISLATOR)
        status = row_value(row, COL_STATUS)
        prev = row_value(row, COL_FINAL_PREV)
        curr = row_value(row, COL_FINAL_CURR)
        rec: dict[str, Any] = {
            "observation": observation if observation != BLANK else "—",
            "legal_text": "" if legal == BLANK else legal,
            "system_name": "" if system == BLANK else system,
            "rating": "" if rating == BLANK else rating,
            "department": "" if dept == BLANK else dept,
            "legislator": "" if legislator == BLANK else legislator,
            "article_no": article_number_from_row(row),
            "status": "" if status == BLANK else status,
            "compliance_mgmt": compliance_mgmt_status_from_row(row),
            "quarter": record_list_quarter(row, selected),
            "final_prev": "" if prev == BLANK else prev,
            "final_curr": "" if curr == BLANK else curr,
        }
        if assessment_new:
            rec["form"] = assessment_form_from_row(row)
        records.append(rec)
    return {
        "total": len(filtered),
        "truncated": len(filtered) > cap,
        "records": records,
    }


def sort_group(key: str, values: list[str]) -> list[str]:
    if key == CANONICAL_NAMES["assessment_year"]:
        quarters = sorted(
            [v for v in values if re.fullmatch(r"Q[1-4]", v, re.I)],
            key=lambda x: int(x[-1]),
        )
        rest = sorted(
            [v for v in values if v != BLANK and not re.fullmatch(r"Q[1-4]", v, re.I)],
            key=lambda x: x,
        )
        ordered = [*quarters, *rest]
        if BLANK in values:
            return [BLANK, *ordered]
        return ordered
    if key in YEAR_BUCKET_COLUMNS or key in QUARTER_BUCKET_COLUMNS:
        numeric = sorted([v for v in values if re.fullmatch(r"\d+", v)], key=int)
        quarters = sorted(
            [v for v in values if re.fullmatch(r"\d{4}-Q[1-4]", v, re.I)],
            key=lambda x: (int(x[:4]), int(x[-1])),
        )
        rest = sorted(
            [
                v
                for v in values
                if v != BLANK
                and not re.fullmatch(r"\d+", v)
                and not re.fullmatch(r"\d{4}-Q[1-4]", v, re.I)
            ],
            key=lambda x: x,
        )
        ordered = [*numeric, *quarters, *rest]
        if BLANK in values:
            return [BLANK, *ordered]
        return ordered
    return sorted(values, key=lambda x: x)


def build_summary(
    rows: list[dict[str, str]], selected: dict[str, list[str]]
) -> dict[str, Any]:
    fully = apply_filters(rows, selected, None)
    available_dims = [dim for dim in GROUP_DIMS if any(dim in r for r in rows)]
    groups: dict[str, list[dict[str, Any]]] = {}
    for dim in available_dims:
        counts: dict[str, int] = {}
        for r in apply_filters(rows, selected, dim):
            k = row_value(r, dim)
            counts[k] = counts.get(k, 0) + 1
        ordered = sort_group(dim, list(counts.keys()))
        groups[dim] = [
            {"key": k, "label": k, "count": counts[k]} for k in ordered
        ]
    company_columns = {
        "holding": CANONICAL_NAMES["holding_company"] in available_dims,
        "subsidiary": CANONICAL_NAMES["subsidiary_company"] in available_dims,
    }
    return {
        "total": len(fully),
        "selected": selected,
        "groups": groups,
        "company_columns": company_columns,
    }


def pick_best_legal_row(matches: list[dict[str, str]]) -> dict[str, str] | None:
    if not matches:
        return None
    with_mail = [r for r in matches if row_value(r, "email") != BLANK]
    pool = with_mail or matches
    best = pool[0]
    best_score = -1
    for r in pool:
        score = sum(1 for col, _ in DETAIL_FIELDS if detail_field_value(r, col))
        if score > best_score:
            best_score = score
            best = r
    return best


def legal_details_from_rows(
    rows: list[dict[str, str]], text: str
) -> dict[str, Any] | None:
    matches = [r for r in rows if row_value(r, COL_LEGAL) == text]
    row = pick_best_legal_row(matches)
    if not row:
        return None
    fields = [
        {"label": label, "value": detail_field_value(row, col)}
        for col, label in DETAIL_FIELDS
    ]
    em = row_value(row, "email")
    recipient = em if em != BLANK else ""
    excel_row = rows.index(row) + 2 if row in rows else 0
    return {
        "legal_text": text,
        "excel_row": excel_row,
        "picked_row_index": 0,
        "recipient_email": recipient,
        "fields": fields,
        "images": [],
    }


def is_within_correction_status(status_text: str) -> bool:
    t = norm_nfkc(status_text).replace("\u00a0", " ")
    t = re.sub(r"\s+", " ", t)
    if "مفتوح" not in t:
        return False
    return "ضمن" in t and "تاريخ" in t and "التصحيح" in t


def is_past_correction_status(status_text: str) -> bool:
    t = norm_nfkc(status_text).replace("\u00a0", " ")
    t = re.sub(r"\s+", " ", t)
    if "مفتوح" not in t:
        return False
    return "تجاوز" in t and "تاريخ" in t and "التصحيح" in t


def is_open_status_for_aging(status_text: str) -> bool:
    return is_within_correction_status(status_text) or is_past_correction_status(status_text)


def aging_row_risk_text(row: dict[str, str]) -> str:
    residual = row_value(row, COL_RESIDUAL)
    if residual != BLANK:
        return residual
    return row_value(row, COL_INHERENT)


def aging_risk_key(residual_norm: str) -> str | None:
    if residual_norm == BLANK:
        return None
    t = norm_nfkc(residual_norm).replace("\u00a0", " ").strip()
    t = re.sub(r"\s+", " ", t)
    for bad, good in [
        ("مرنفع", "مرتفع"),
        ("مرتفغ", "مرتفع"),
        ("مرتفاع", "مرتفع"),
        ("مرنفغ", "مرتفع"),
        ("مرتفغ جدا", "مرتفع جدا"),
        ("عاليه", "عالية"),
    ]:
        t = t.replace(bad, good)
    if "متدني" in t and re.search(r"انخفاض|انخفاظ|انخغاض|انخفاق", t):
        return "very_low"
    if ("جدا" in t or "جداً" in t or "جدآ" in t) and (
        "مرتفع" in t or "مرفع" in t or "عالي" in t or "عالية" in t
    ):
        return "very_high"
    if "متوسط" in t:
        return "medium"
    if "منخفض" in t and "متدني" not in t:
        return "low"
    if "مرتفع" in t or "مرفع" in t:
        return "high"
    if re.fullmatch(r"عالي(?:ة)?", t) or re.search(r"(^|\s)عالي(?:ة)?($|\s)", t):
        return "high"
    return None


def parse_date_at_noon(dstr: str) -> date | None:
    if not dstr or dstr == BLANK:
        return None
    s = str(dstr).strip()
    try:
        if "T" in s:
            return datetime.fromisoformat(s.replace("Z", "")).date()
        if re.fullmatch(r"-?\d+(?:\.\d+)?", s):
            fv = float(s)
            if fv >= 1e12:
                return datetime.utcfromtimestamp(fv / 1000.0).date()
            if 1e9 <= fv < 1e12:
                return datetime.utcfromtimestamp(fv).date()
            if 20000 <= fv <= 80000:
                return (datetime(1899, 12, 30) + timedelta(days=fv)).date()
        if re.match(r"\d{4}-\d{2}-\d{2}", s):
            return datetime.strptime(s[:10], "%Y-%m-%d").date()
        return datetime.strptime(s[:10], "%Y-%m-%d").date()
    except (ValueError, OSError, OverflowError):
        return None


def is_closed_status_for_aging(status_text: str) -> bool:
    t = norm_nfkc(status_text).replace("\u00a0", " ")
    t = re.sub(r"\s+", " ", t)
    return "مغلق" in t or "مقفل" in t


def aging_target_date(row: dict[str, str]) -> date | None:
    """Read تاريخ التصحيح المستهدف, including the extra-space Excel header."""
    wanted = " ".join(COL_TARGET.split())
    keys = [COL_TARGET, "تاريخ التصحيح  المستهدف"]
    for key in list(row.keys()):
        if " ".join(str(key).split()) == wanted and key not in keys:
            keys.append(key)
    for col in keys:
        parsed = parse_date_at_noon(row_value(row, col))
        if parsed:
            return parsed
    return None


def aging_days_vs_reference(row: dict[str, str], reference_raw: str) -> int | None:
    """Days from target correction date to the selected reference date (positive = overdue)."""
    cdt = aging_target_date(row)
    ref = parse_date_at_noon(reference_raw)
    if not cdt or not ref:
        return None
    return (ref - cdt).days


def aging_overdue_bucket(compare: date, reference: date) -> str | None:
    parent, _child = aging_overdue_detail(compare, reference)
    return parent


def aging_overdue_detail(compare: date, reference: date) -> tuple[str | None, str | None]:
    """Parent bucket plus optional over-one-year child (y1_2 … y5p)."""
    overdue_days = (reference - compare).days
    if overdue_days < 183:
        return "lt_6m", None
    if overdue_days < 365:
        return "lt_1y", None
    if overdue_days < 730:
        return "ge_1y", "y1_2"
    if overdue_days < 1095:
        return "ge_1y", "y2_3"
    if overdue_days < 1460:
        return "ge_1y", "y3_4"
    if overdue_days < 1825:
        return "ge_1y", "y4_5"
    return "ge_1y", "y5p"


def aging_classify_row(row: dict[str, str], ref: date) -> tuple[str | None, str | None, str] | None:
    """Return (parent_time, child_time, risk) or None when the row is skipped."""
    st = row_value(row, COL_STATUS)
    rkey = aging_risk_key(aging_row_risk_text(row)) or "other"
    if is_closed_status_for_aging(st):
        return None
    cdt = aging_target_date(row)
    if not cdt:
        return None
    if cdt >= ref:
        return "not_due", None, rkey
    parent, child = aging_overdue_detail(cdt, ref)
    if not parent:
        return None
    return parent, child, rkey


def aging_row_matches(
    row: dict[str, str],
    ref: date,
    time_id: str | None,
    risk_id: str | None,
) -> bool:
    classified = aging_classify_row(row, ref)
    if not classified:
        return False
    parent, child, rkey = classified
    want_time = str(time_id or "").strip()
    want_risk = str(risk_id or "").strip()
    if want_risk and rkey != want_risk:
        return False
    if not want_time or want_time in {"all", "*"}:
        return True
    if want_time == parent:
        return True
    if child and want_time == child:
        return True
    return False


def compute_aging(
    rows: list[dict[str, str]],
    selected: dict[str, list[str]],
    reference_raw: str,
    date_source: str = "target",
) -> dict[str, Any]:
    ref = parse_date_at_noon(reference_raw)
    if not ref:
        return {"error": "Invalid reference date"}
    date_col = COL_TARGET
    cfg = AGING_CONFIG
    risk_keys = [x["id"] for x in cfg["risk_columns"]]
    over_year_defs = cfg.get("over_year_rows") or []
    matrix: dict[str, dict[str, int]] = {
        tr["id"]: {rk: 0 for rk in risk_keys} for tr in cfg["time_rows"]
    }
    over_matrix: dict[str, dict[str, int]] = {
        tr["id"]: {rk: 0 for rk in risk_keys} for tr in over_year_defs
    }
    skipped_other = 0
    unknown_time = 0
    for row in apply_filters(rows, selected, None):
        st = row_value(row, COL_STATUS)
        if is_closed_status_for_aging(st):
            skipped_other += 1
            continue
        cdt = aging_target_date(row)
        if not cdt:
            unknown_time += 1
            continue
        classified = aging_classify_row(row, ref)
        if not classified:
            unknown_time += 1
            continue
        parent, child, rkey = classified
        if parent not in matrix:
            unknown_time += 1
            continue
        matrix[parent][rkey] = matrix[parent].get(rkey, 0) + 1
        if child and child in over_matrix:
            over_matrix[child][rkey] = over_matrix[child].get(rkey, 0) + 1

    time_rows = []
    for tr in cfg["time_rows"]:
        cells = matrix.get(tr["id"], {})
        total = sum(cells.get(k, 0) for k in risk_keys)
        time_rows.append({"id": tr["id"], "label": tr["label"], "cells": cells, "total": total})

    over_year_rows = []
    for tr in over_year_defs:
        cells = over_matrix.get(tr["id"], {})
        total = sum(cells.get(k, 0) for k in risk_keys)
        over_year_rows.append({"id": tr["id"], "label": tr["label"], "cells": cells, "total": total})

    column_totals = {k: 0 for k in risk_keys}
    for tr in time_rows:
        for k in risk_keys:
            column_totals[k] += tr["cells"].get(k, 0)
    grand_total = sum(column_totals.values())

    return {
        "reference": reference_raw[:10] if reference_raw else "",
        "date_field": date_col,
        "date_source": "target",
        "risk_columns": cfg["risk_columns"],
        "time_rows": time_rows,
        "over_year_rows": over_year_rows,
        "column_totals": column_totals,
        "grand_total": grand_total,
        "status_filter": "open_only",
        "skipped_other_status": skipped_other,
        "skipped_unknown_time": unknown_time,
    }


def build_audit_plan_panel(
    rows: list[dict[str, str]], selected: dict[str, list[str]]
) -> dict[str, Any]:
    filtered = apply_filters(rows, selected, None)
    columns = []
    for col in AUDIT_COLUMNS:
        counts: dict[str, int] = {}
        non_null = 0
        for r in filtered:
            v = row_value(r, col)
            counts[v] = counts.get(v, 0) + 1
            if v != BLANK:
                non_null += 1
        ordered = sorted(counts.items(), key=lambda x: -x[1])
        columns.append(
            {
                "name": col,
                "entries": [{"label": k, "count": c} for k, c in ordered[:80]],
                "truncated": len(ordered) > 80,
                "distinct": len(ordered),
                "non_null": non_null,
            }
        )
    return {"total_rows": len(filtered), "columns": columns}


def build_snapshot_pack(
    rows: list[dict[str, str]],
    *,
    brand_logos: dict[str, str] | None = None,
    default_brand_code: str | None = None,
    legal_details: dict[str, Any] | None = None,
    row_images: dict[str, list] | None = None,
) -> dict[str, Any]:
    return {
        "rows": rows,
        "aging_config": AGING_CONFIG,
        "audit_columns": AUDIT_COLUMNS,
        "brand_logos": brand_logos or {},
        "default_brand_code": default_brand_code,
        "legal_details": legal_details or {},
        "row_images": row_images or {},
    }


def parse_query_params(query_dict) -> dict[str, list[str]]:
    """Parse Django QueryDict into param lists for selected_from_params."""
    params: dict[str, list[str]] = {}
    for key in PARAM_TO_COL:
        params[key] = query_dict.getlist(key)
    return params
