"""Department grants and dashboard Department-filter scoping."""
from __future__ import annotations

import html
import json
import re
from html.parser import HTMLParser

from audit_app.company_access import has_company_perm, resolve_tenant_company
from audit_app.models import UserDepartmentAccess

_FULL_DATA_PERMS = ("review", "assign_viewers", "hide")
_PAYLOAD_MARKER = "const payload = "
_PREVIEW_BLANK = "__preview_blank__"
_PREVIEW_TABLE_CLASS = "preview-filter-table"
_DEPT_HEADER_KEYS = {
    "department",
    "dept",
    "business unit",
    "unit",
    "القسم",
    "الإدارة",
    "الادارة",
}


def normalize_department_token(value) -> str:
    return " ".join(str(value or "").replace("\u00a0", " ").split()).casefold()


def _parse_json_constant(token: str) -> float:
    return float(token)


def department_scope_tokens_for_dashboard(user, dashboard) -> list[str] | None:
    """Excel department names this viewer may see.

    ``None`` means the Department filter stays unrestricted.
    A list applies when the user is linked to one or more departments.
    The dashboard creator, a superuser, and a member who reviews, assigns
    viewers, or hides that template still see every department. Permission
    to upload other dashboards does not widen this one.
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
    accesses = UserDepartmentAccess.objects.filter(
        user=user,
        is_deleted=False,
        department__is_deleted=False,
        department__is_active=True,
    ).select_related("department")
    tokens: list[str] = []
    seen: set[str] = set()
    for access in accesses:
        for token in access.department.match_tokens():
            key = normalize_department_token(token)
            if not key or key in seen:
                continue
            seen.add(key)
            tokens.append(token)
    if not tokens:
        return None
    return tokens


def restrict_audit_observation_payload(payload: dict, allowed_tokens: list[str]) -> bool:
    """Drop audit rows and Department options outside ``allowed_tokens``."""
    observation = payload.get("audit_observation")
    if not isinstance(observation, dict):
        return False
    allowed = {
        normalize_department_token(token)
        for token in allowed_tokens
        if normalize_department_token(token)
    }
    if not allowed:
        return False
    rows = observation.get("rows")
    if isinstance(rows, list):
        observation["rows"] = [
            row
            for row in rows
            if isinstance(row, dict)
            and normalize_department_token(row.get("d")) in allowed
        ]
    dims = observation.get("filter_dims")
    if isinstance(dims, list):
        for dim in dims:
            if not isinstance(dim, dict) or dim.get("key") != "d":
                continue
            values = dim.get("values")
            if not isinstance(values, list):
                continue
            dim["values"] = [
                value
                for value in values
                if normalize_department_token(value) in allowed
            ]
    return True


def _preview_header_key(label: str) -> str:
    text = " ".join(str(label or "").replace("\u00a0", " ").split()).casefold()
    text = re.sub(r"[_/\-]+", " ", text)
    return " ".join(text.split())


def _is_preview_department_header(label: str) -> bool:
    key = _preview_header_key(label)
    if not key or "audit cycle" in key:
        return False
    return key in _DEPT_HEADER_KEYS


def _allowed_department_keys(allowed_tokens: list[str]) -> set[str]:
    return {
        normalize_department_token(token)
        for token in allowed_tokens
        if normalize_department_token(token)
    }


class _PreviewTableParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.columns: list[dict] = []
        self.rows: list[list[str]] = []
        self._in_tbody = False
        self._in_th = False
        self._in_label = False
        self._in_option = False
        self._in_td = False
        self._label_parts: list[str] = []
        self._option_parts: list[str] = []
        self._cell_parts: list[str] = []
        self._current_col: dict | None = None
        self._current_row: list[str] | None = None
        self._option_value = ""

    def handle_starttag(self, tag, attrs):
        attr = dict(attrs)
        if tag == "th":
            self._in_th = True
            self._current_col = {
                "label": "",
                "mode": "search",
                "placeholder": "Search",
                "all_label": "All",
                "blank_label": "(blank)",
                "options": [],
            }
        elif tag == "span" and "preview-col-label" in (attr.get("class") or ""):
            self._in_label = True
            self._label_parts = []
        elif tag == "select" and self._current_col is not None:
            self._current_col["mode"] = "select"
        elif tag == "option" and self._current_col is not None:
            self._in_option = True
            self._option_parts = []
            self._option_value = attr.get("value") or ""
        elif tag == "input" and self._current_col is not None:
            self._current_col["mode"] = "search"
            if attr.get("placeholder"):
                self._current_col["placeholder"] = attr["placeholder"]
        elif tag == "tbody":
            self._in_tbody = True
        elif tag == "tr" and self._in_tbody:
            self._current_row = []
        elif tag == "td":
            self._in_td = True
            self._cell_parts = []

    def handle_endtag(self, tag):
        if tag == "span" and self._in_label and self._current_col is not None:
            self._current_col["label"] = "".join(self._label_parts).strip()
            self._in_label = False
        elif tag == "option" and self._in_option and self._current_col is not None:
            label = "".join(self._option_parts).strip()
            base = re.sub(r"\s*\(\d+\)\s*$", "", label).strip()
            if self._option_value == "":
                self._current_col["all_label"] = base or self._current_col["all_label"]
            elif self._option_value == _PREVIEW_BLANK:
                self._current_col["blank_label"] = base or self._current_col["blank_label"]
            self._current_col["options"].append((self._option_value, base))
            self._in_option = False
        elif tag == "th" and self._current_col is not None:
            self.columns.append(self._current_col)
            self._current_col = None
            self._in_th = False
        elif tag == "td" and self._current_row is not None:
            self._current_row.append("".join(self._cell_parts).strip())
            self._in_td = False
        elif tag == "tbody":
            self._in_tbody = False
        elif tag == "tr" and self._current_row is not None:
            if any(cell != "" for cell in self._current_row) or self._current_row:
                self.rows.append(self._current_row)
            self._current_row = None

    def handle_data(self, data):
        if self._in_label:
            self._label_parts.append(data)
        elif self._in_option:
            self._option_parts.append(data)
        elif self._in_td:
            self._cell_parts.append(data)


def _render_preview_select(column: dict, rows: list[list[str]], col_idx: int) -> str:
    counts: dict[str, int] = {}
    blank_count = 0
    for row in rows:
        cell = row[col_idx] if col_idx < len(row) else ""
        if cell == "":
            blank_count += 1
            continue
        counts[cell] = counts.get(cell, 0) + 1
    label = html.escape(column["label"], quote=True)
    options = [
        f'<option value="">{html.escape(column["all_label"])} ({len(rows)})</option>'
    ]
    if blank_count:
        options.append(
            f'<option value="{_PREVIEW_BLANK}">'
            f'{html.escape(column["blank_label"])} ({blank_count})</option>'
        )
    for text in sorted(counts, key=lambda item: item.casefold()):
        options.append(
            f'<option value="{html.escape(text, quote=True)}">'
            f"{html.escape(text)} ({counts[text]})</option>"
        )
    return (
        "<th>"
        f'<span class="preview-col-label">{html.escape(column["label"])}</span>'
        f'<select class="preview-col-filter preview-col-filter--select" '
        f'data-col-idx="{col_idx}" data-filter-mode="select" aria-label="{label}">'
        f'{"".join(options)}</select>'
        "</th>"
    )


def _render_preview_search(column: dict, col_idx: int) -> str:
    label = html.escape(column["label"], quote=True)
    placeholder = html.escape(column.get("placeholder") or "Search", quote=True)
    return (
        "<th>"
        f'<span class="preview-col-label">{html.escape(column["label"])}</span>'
        f'<input type="search" class="preview-col-filter preview-col-filter--search" '
        f'data-col-idx="{col_idx}" data-filter-mode="search" placeholder="{placeholder}" '
        f'aria-label="{label} {placeholder}" />'
        "</th>"
    )


def _render_preview_table(columns: list[dict], rows: list[list[str]]) -> str:
    heads = []
    for idx, column in enumerate(columns):
        if column["mode"] == "select":
            heads.append(_render_preview_select(column, rows, idx))
        else:
            heads.append(_render_preview_search(column, idx))
    body = []
    for row in rows:
        cells = "".join(
            f"<td>{html.escape(row[idx] if idx < len(row) else '')}</td>"
            for idx in range(len(columns))
        )
        body.append(f"<tr>{cells}</tr>")
    return (
        "<table class='preview-filter-table'><thead><tr>"
        f"{''.join(heads)}</tr></thead><tbody>{''.join(body)}</tbody></table>"
    )


def restrict_preview_filter_tables(html_text: str, allowed_tokens: list[str]) -> str:
    """Drop preview-table rows and Department choices outside the granted departments."""
    allowed = _allowed_department_keys(allowed_tokens)
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
        dept_idx = next(
            (
                idx
                for idx, column in enumerate(parser.columns)
                if _is_preview_department_header(column["label"])
            ),
            None,
        )
        rows = parser.rows
        if dept_idx is not None and parser.columns:
            rows = [
                row
                for row in rows
                if dept_idx < len(row)
                and normalize_department_token(row[dept_idx]) in allowed
            ]
            parts.append(_render_preview_table(parser.columns, rows))
        else:
            parts.append(fragment)
        cursor = end
    return "".join(parts)


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
    if not restrict_audit_observation_payload(payload, allowed_tokens):
        return html_text
    rendered = json.dumps(payload, ensure_ascii=False, allow_nan=True).replace(
        "<", "\\u003c"
    )
    return html_text[:start] + rendered + html_text[end:]


def apply_department_scope_to_html(html_text: str, allowed_tokens: list[str] | None) -> str:
    """Rewrite served dashboard HTML so other departments are absent."""
    if not allowed_tokens or not html_text:
        return html_text
    scoped = _rewrite_embedded_payload(html_text, allowed_tokens)
    return restrict_preview_filter_tables(scoped, allowed_tokens)
