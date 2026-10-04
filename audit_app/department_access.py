"""Department grants and dashboard Department-filter scoping."""
from __future__ import annotations

import json

from audit_app.company_access import has_company_perm, resolve_tenant_company
from audit_app.models import UserDepartmentAccess

_FULL_DATA_PERMS = ("review", "assign_viewers", "hide")
_PAYLOAD_MARKER = "const payload = "


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


def apply_department_scope_to_html(html: str, allowed_tokens: list[str] | None) -> str:
    """Rewrite the embedded dashboard payload so other departments are absent."""
    if not allowed_tokens or not html:
        return html
    marker_at = html.find(_PAYLOAD_MARKER)
    if marker_at < 0:
        return html
    start = marker_at + len(_PAYLOAD_MARKER)
    decoder = json.JSONDecoder(parse_constant=_parse_json_constant)
    try:
        payload, end = decoder.raw_decode(html, start)
    except (json.JSONDecodeError, ValueError):
        return html
    if not isinstance(payload, dict):
        return html
    if not restrict_audit_observation_payload(payload, allowed_tokens):
        return html
    rendered = json.dumps(payload, ensure_ascii=False, allow_nan=True).replace(
        "<", "\\u003c"
    )
    return html[:start] + rendered + html[end:]
