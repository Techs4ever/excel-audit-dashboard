"""Subsidiary grants and dashboard company-filter scoping."""
from __future__ import annotations

import json

from django.db.models import Q

from arabic_compliance_dashboard.schema import CANONICAL_NAMES
from audit_app.company_access import (
    active_main_companies,
    active_subsidiaries_of,
    has_company_perm,
    resolve_tenant_company,
)
from audit_app.department_access import (
    _PAYLOAD_MARKER,
    _PREVIEW_TABLE_CLASS,
    _PreviewTableParser,
    _parse_json_constant,
    _preview_header_key,
    _render_preview_table,
)
from audit_app.models import Company, UserSubsidiaryAccess

_FULL_DATA_PERMS = ("review", "assign_viewers", "hide")
_SUB_HEADER_KEYS = {
    "subcompany",
    "sub company",
    "subsidiary",
    "subsidiary company",
    "الشركة التابعة",
    "الشركه التابعه",
}
_SNAPSHOT_MARKER = 'id="snapshot-pack">'


def normalize_subsidiary_token(value) -> str:
    return " ".join(str(value or "").replace("\u00a0", " ").split()).casefold()


def company_scope_tokens(company: Company) -> list[str]:
    """Names that identify this company in an Excel subcompany column."""
    raw = [company.code, company.name, *company.accepted_excel_names()]
    tokens: list[str] = []
    seen: set[str] = set()
    for item in raw:
        text = " ".join(str(item or "").replace("\u00a0", " ").split())
        key = text.casefold()
        if not text or key in seen:
            continue
        seen.add(key)
        tokens.append(text)
    return tokens


def membership_subsidiary_choices(company_id: int | None) -> list[Company]:
    """Parent company plus its subsidiaries, or nothing when it has no children."""
    if not company_id:
        return []
    parent = active_main_companies().filter(pk=company_id).first()
    if parent is None:
        return []
    children = list(active_subsidiaries_of(parent).order_by("code"))
    if not children:
        return []
    return [parent, *children]


def subsidiary_catalog_by_parent() -> dict[str, list[dict]]:
    catalog: dict[str, list[dict]] = {}
    for parent in active_main_companies().order_by("code"):
        choices = membership_subsidiary_choices(parent.pk)
        if not choices:
            continue
        catalog[str(parent.pk)] = [
            {"id": company.pk, "label": str(company)} for company in choices
        ]
    return catalog


def subsidiary_scope_tokens_for_dashboard(user, dashboard) -> list[str] | None:
    """Excel subcompany names this viewer may see.

    ``None`` means the company filter stays unrestricted.
    A list applies when the user is linked to one or more companies in the
    tenant (the parent itself and/or its subsidiaries). The dashboard creator,
    a superuser, and a member who reviews, assigns viewers, or hides that
    template still see every company.
    """
    if not getattr(user, "is_authenticated", False):
        return None
    if user.is_superuser:
        return None
    if getattr(dashboard, "created_by_id", None) == user.pk:
        return None
    company = resolve_tenant_company(getattr(dashboard, "company", None))
    template_code = getattr(dashboard, "template_type", None) or None
    if company is not None:
        for perm in _FULL_DATA_PERMS:
            if has_company_perm(user, company, perm, template_code):
                return None
    if company is None:
        return None
    accesses = UserSubsidiaryAccess.objects.filter(
        user=user,
        is_deleted=False,
        company__is_deleted=False,
        company__is_active=True,
    ).filter(Q(company_id=company.pk) | Q(company__parent_id=company.pk)).select_related(
        "company"
    )
    tokens: list[str] = []
    seen: set[str] = set()
    for access in accesses:
        for token in company_scope_tokens(access.company):
            key = normalize_subsidiary_token(token)
            if not key or key in seen:
                continue
            seen.add(key)
            tokens.append(token)
    if not tokens:
        return None
    return tokens


def _allowed_keys(allowed_tokens: list[str]) -> set[str]:
    return {
        normalize_subsidiary_token(token)
        for token in allowed_tokens
        if normalize_subsidiary_token(token)
    }


def filter_rows_by_subsidiary_scope(
    rows: list,
    allowed_tokens: list[str] | None,
    *,
    column_key: str | None = None,
) -> list:
    """Drop rows whose subsidiary column is outside the granted companies."""
    if not allowed_tokens or not isinstance(rows, list):
        return rows
    key = column_key or CANONICAL_NAMES["subsidiary_company"]
    if not any(isinstance(row, dict) and key in row for row in rows):
        return rows
    allowed = _allowed_keys(allowed_tokens)
    if not allowed:
        return rows
    return [
        row
        for row in rows
        if isinstance(row, dict) and normalize_subsidiary_token(row.get(key)) in allowed
    ]


def restrict_audit_observation_subsidiaries(payload: dict, allowed_tokens: list[str]) -> bool:
    """Drop audit rows and subcompany options outside ``allowed_tokens``."""
    observation = payload.get("audit_observation")
    if not isinstance(observation, dict):
        return False
    allowed = _allowed_keys(allowed_tokens)
    if not allowed:
        return False
    dims = observation.get("filter_dims")
    rows = observation.get("rows")
    has_dim = isinstance(dims, list) and any(
        isinstance(dim, dict) and dim.get("key") == "sco" for dim in dims
    )
    has_rows = isinstance(rows, list) and any(
        isinstance(row, dict) and "sco" in row for row in rows
    )
    if not has_dim and not has_rows:
        return False
    if isinstance(rows, list):
        observation["rows"] = [
            row
            for row in rows
            if isinstance(row, dict)
            and normalize_subsidiary_token(row.get("sco")) in allowed
        ]
    if isinstance(dims, list):
        for dim in dims:
            if not isinstance(dim, dict) or dim.get("key") != "sco":
                continue
            values = dim.get("values")
            if not isinstance(values, list):
                continue
            dim["values"] = [
                value
                for value in values
                if normalize_subsidiary_token(value) in allowed
            ]
    return True


def restrict_snapshot_pack(pack: dict, allowed_tokens: list[str]) -> bool:
    """Drop compliance snapshot rows outside the granted subsidiaries."""
    if not isinstance(pack, dict):
        return False
    rows = pack.get("rows")
    if not isinstance(rows, list):
        return False
    sub_key = CANONICAL_NAMES["subsidiary_company"]
    if not any(isinstance(row, dict) and sub_key in row for row in rows):
        return False
    kept = filter_rows_by_subsidiary_scope(rows, allowed_tokens, column_key=sub_key)
    pack["rows"] = kept
    details = pack.get("legal_details")
    if isinstance(details, dict):
        legal_key = CANONICAL_NAMES["legal_text"]
        keep = {
            row.get(legal_key)
            for row in kept
            if isinstance(row, dict) and row.get(legal_key)
        }
        pack["legal_details"] = {
            key: value for key, value in details.items() if key in keep
        }
    return True


def _rewrite_embedded_payload(html_text: str, allowed_tokens: list[str]) -> str:
    marker_at = html_text.find(_PAYLOAD_MARKER)
    if marker_at < 0:
        return html_text
    start = marker_at + len(_PAYLOAD_MARKER)
    decoder = json.JSONDecoder(parse_constant=_parse_json_constant)
    try:
        payload, end = decoder.raw_decode(html_text, start)
    except (json.JSONDecodeError, ValueError):
        return html_text
    if not isinstance(payload, dict):
        return html_text
    if not restrict_audit_observation_subsidiaries(payload, allowed_tokens):
        return html_text
    rendered = json.dumps(payload, ensure_ascii=False, allow_nan=True).replace(
        "<", "\\u003c"
    )
    return html_text[:start] + rendered + html_text[end:]


def _rewrite_snapshot_pack(html_text: str, allowed_tokens: list[str]) -> str:
    marker_at = html_text.find(_SNAPSHOT_MARKER)
    if marker_at < 0:
        return html_text
    start = marker_at + len(_SNAPSHOT_MARKER)
    try:
        pack, end = json.JSONDecoder().raw_decode(html_text, start)
    except (json.JSONDecodeError, ValueError):
        return html_text
    if not restrict_snapshot_pack(pack, allowed_tokens):
        return html_text
    rendered = json.dumps(pack, ensure_ascii=False).replace("<", "\\u003c")
    return html_text[:start] + rendered + html_text[end:]


def _is_preview_subcompany_header(label: str) -> bool:
    key = _preview_header_key(label)
    if not key or key in {"company", "الشركة", "الشركة القابضة"}:
        return False
    return key in _SUB_HEADER_KEYS


def restrict_preview_subcompany_tables(html_text: str, allowed_tokens: list[str]) -> str:
    """Drop preview-table rows and subcompany choices outside the granted companies."""
    allowed = _allowed_keys(allowed_tokens)
    if not allowed or _PREVIEW_TABLE_CLASS not in html_text:
        return html_text
    cursor = 0
    parts: list[str] = []
    while True:
        marker = html_text.find(_PREVIEW_TABLE_CLASS, cursor)
        if marker < 0:
            parts.append(html_text[cursor:])
            break
        start = html_text.rfind("<table", cursor, marker)
        end = html_text.find("</table>", marker)
        if start < 0 or end < 0:
            parts.append(html_text[cursor:])
            break
        end += len("</table>")
        parts.append(html_text[cursor:start])
        fragment = html_text[start:end]
        parser = _PreviewTableParser()
        parser.feed(fragment)
        sub_idx = next(
            (
                idx
                for idx, column in enumerate(parser.columns)
                if _is_preview_subcompany_header(column["label"])
            ),
            None,
        )
        rows = parser.rows
        if sub_idx is not None and parser.columns:
            rows = [
                row
                for row in rows
                if sub_idx < len(row)
                and normalize_subsidiary_token(row[sub_idx]) in allowed
            ]
            parts.append(_render_preview_table(parser.columns, rows))
        else:
            parts.append(fragment)
        cursor = end
    return "".join(parts)


def apply_subsidiary_scope_to_html(html_text: str, allowed_tokens: list[str] | None) -> str:
    """Rewrite served dashboard HTML so other subsidiaries are absent."""
    if not allowed_tokens or not html_text:
        return html_text
    scoped = _rewrite_embedded_payload(html_text, allowed_tokens)
    scoped = _rewrite_snapshot_pack(scoped, allowed_tokens)
    return restrict_preview_subcompany_tables(scoped, allowed_tokens)
