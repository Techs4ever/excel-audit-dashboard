"""Inherit attachment files by linking a dashboard to a published one.

A child dashboard shows its parent's attachments, then its own, in that order.
The parent may itself be linked, so the sequence is oldest ancestor first.
Inherited files stay on the parent record and cannot be deleted from the child.
"""

from __future__ import annotations

from django.utils.translation import get_language

from audit_app.models import Dashboard, DashboardStatus
from dashboard_locale import normalize_locale, tr

_MAX_CHAIN = 25

_ERROR_KEYS = {
    "err_link_invalid",
    "err_link_not_found",
    "err_link_deleted",
    "err_link_wrong_company",
    "err_link_wrong_template",
    "err_link_not_published",
    "err_link_cycle",
}


class DashboardLinkError(Exception):
    def __init__(self, code: str):
        self.code = code if code in _ERROR_KEYS else "err_link_invalid"
        super().__init__(self.code)

    def message_for_locale(self, locale: str | None) -> str:
        loc = normalize_locale(locale or get_language() or "en")
        return tr(loc, self.code)


def _attachment_source_keys() -> list[str]:
    from reports_app.services.report_generation import ATTACHMENT_SPECS

    return [spec["source_key"] for spec in ATTACHMENT_SPECS]


def _raw_paths(source: dict | None, key: str) -> list[str]:
    if not isinstance(source, dict):
        return []
    raw = source.get(key) or []
    if isinstance(raw, str):
        raw = [raw]
    paths: list[str] = []
    for item in raw:
        token = str(item).strip().replace("\\", "/")
        if token:
            paths.append(token)
    return paths


def _existing_paths(source: dict | None, key: str) -> list[str]:
    from reports_app.services.report_generation import _existing_media_paths

    return _existing_media_paths(_raw_paths(source, key))


def ancestor_dashboards(dashboard: Dashboard | None) -> list[Dashboard]:
    """Oldest ancestor first, then the direct parent.

    Soft-deleted dashboards are skipped, but the walk continues through them
    so a grandchild still inherits a living grandparent.
    """
    if dashboard is None:
        return []
    nearest: list[Dashboard] = []
    seen: set[int] = set()
    if dashboard.pk:
        seen.add(dashboard.pk)
    current_id = dashboard.linked_dashboard_id
    steps = 0
    while current_id and steps < _MAX_CHAIN:
        if current_id in seen:
            break
        seen.add(current_id)
        current = (
            Dashboard.objects.filter(pk=current_id)
            .only(
                "id",
                "name",
                "is_deleted",
                "source_files",
                "linked_dashboard_id",
                "company_id",
                "template_type",
                "status",
            )
            .first()
        )
        if current is None:
            break
        if not current.is_deleted:
            nearest.append(current)
        current_id = current.linked_dashboard_id
        steps += 1
    nearest.reverse()
    return nearest


def descendant_ids(dashboard: Dashboard | None) -> set[int]:
    if dashboard is None or not dashboard.pk:
        return set()
    found: set[int] = set()
    frontier = [dashboard.pk]
    for _ in range(_MAX_CHAIN):
        kids = list(
            Dashboard.objects.filter(linked_dashboard_id__in=frontier).values_list(
                "pk", flat=True
            )
        )
        kids = [pk for pk in kids if pk not in found and pk != dashboard.pk]
        if not kids:
            break
        found.update(kids)
        frontier = kids
    return found


def _merged_pairs(dashboards: list[Dashboard]) -> dict[str, list[tuple[str, Dashboard]]]:
    keys = _attachment_source_keys()
    merged: dict[str, list[tuple[str, Dashboard]]] = {key: [] for key in keys}
    seen: dict[str, set[str]] = {key: set() for key in keys}
    for dash in dashboards:
        source = dash.source_files if isinstance(dash.source_files, dict) else {}
        for key in keys:
            for path in _existing_paths(source, key):
                if path in seen[key]:
                    continue
                seen[key].add(path)
                merged[key].append((path, dash))
    return merged


def inherited_attachment_items(dashboard: Dashboard | None) -> dict[str, list[dict]]:
    """Per source key, inherited files oldest-ancestor first."""
    items: dict[str, list[dict]] = {}
    for key, pairs in _merged_pairs(ancestor_dashboards(dashboard)).items():
        items[key] = [
            {
                "path": path,
                "name": path.rsplit("/", 1)[-1],
                "inherited": True,
                "source_dashboard_id": owner.pk,
                "source_dashboard_name": owner.name,
            }
            for path, owner in pairs
        ]
    return items


def inherited_paths_from_parent(parent: Dashboard | None) -> dict[str, list[str]]:
    """Files a child would inherit by linking to ``parent`` (parent chain + parent)."""
    if parent is None:
        return {key: [] for key in _attachment_source_keys()}
    owners = ancestor_dashboards(parent) + [parent]
    return {
        key: [path for path, _owner in pairs]
        for key, pairs in _merged_pairs(owners).items()
    }


def effective_source_files(dashboard: Dashboard) -> dict:
    """Own source files with inherited attachment lists prepended, oldest first."""
    own = dashboard.source_files if isinstance(dashboard.source_files, dict) else {}
    inherited = inherited_attachment_items(dashboard)
    merged: dict = {}
    for key, items in inherited.items():
        paths = [item["path"] for item in items]
        seen = set(paths)
        for path in _existing_paths(own, key):
            if path not in seen:
                paths.append(path)
                seen.add(path)
        merged[key] = paths
    for key, value in own.items():
        if key not in merged:
            merged[key] = value
    return merged


def link_would_cycle(dashboard: Dashboard | None, target: Dashboard) -> bool:
    if dashboard is not None and dashboard.pk and target.pk == dashboard.pk:
        return True
    if dashboard is None or not dashboard.pk:
        return False
    if target.pk in descendant_ids(dashboard):
        return True
    current_id = target.linked_dashboard_id
    seen = {target.pk}
    for _ in range(_MAX_CHAIN):
        if not current_id or current_id in seen:
            break
        if dashboard.pk and current_id == dashboard.pk:
            return True
        seen.add(current_id)
        current_id = (
            Dashboard.objects.filter(pk=current_id)
            .values_list("linked_dashboard_id", flat=True)
            .first()
        )
    return False


def validate_link_target(
    dashboard: Dashboard | None,
    target: Dashboard | None,
    *,
    company,
    template_type: str,
    allow_current: bool = False,
) -> None:
    """Raise DashboardLinkError when ``target`` cannot be linked."""
    if target is None:
        raise DashboardLinkError("err_link_not_found")
    if target.is_deleted:
        raise DashboardLinkError("err_link_deleted")
    expected_company_id = None
    if dashboard is not None and dashboard.company_id:
        expected_company_id = dashboard.company_id
    elif company is not None:
        expected_company_id = company.id
    if not expected_company_id or target.company_id != expected_company_id:
        raise DashboardLinkError("err_link_wrong_company")
    if target.template_type != template_type:
        raise DashboardLinkError("err_link_wrong_template")
    if link_would_cycle(dashboard, target):
        raise DashboardLinkError("err_link_cycle")
    same_as_saved = False
    if allow_current and dashboard is not None and dashboard.pk:
        saved_id = (
            Dashboard.objects.filter(pk=dashboard.pk)
            .values_list("linked_dashboard_id", flat=True)
            .first()
        )
        same_as_saved = saved_id == target.pk
    if not same_as_saved and target.status != DashboardStatus.PUBLISHED:
        raise DashboardLinkError("err_link_not_published")


def resolve_link_target(
    dashboard: Dashboard | None,
    raw_id: str | None,
    *,
    company,
    template_type: str,
    locale: str | None,
    allow_current: bool = True,
) -> Dashboard | None:
    """Return the dashboard to link, or None when the choice is cleared."""
    raw = str(raw_id or "").strip()
    if not raw:
        return None
    if not raw.isdigit():
        raise DashboardLinkError("err_link_invalid")
    target = Dashboard.objects.filter(pk=int(raw)).first()
    validate_link_target(
        dashboard,
        target,
        company=company,
        template_type=template_type,
        allow_current=allow_current,
    )
    return target


def link_parent_for_request(
    request,
    dashboard: Dashboard | None,
    *,
    company,
    template_type: str,
) -> Dashboard | None:
    """Parent selected on this save, or the dashboard's current parent."""
    locale = normalize_locale(getattr(request, "session", {}).get("ui_lang", "en"))
    if "linked_dashboard_id" in request.POST:
        try:
            return resolve_link_target(
                dashboard,
                request.POST.get("linked_dashboard_id"),
                company=company,
                template_type=template_type,
                locale=locale,
                allow_current=True,
            )
        except DashboardLinkError as exc:
            raise ValueError(exc.message_for_locale(locale)) from exc
    if dashboard is not None and dashboard.linked_dashboard_id:
        parent = dashboard.linked_dashboard
        if parent is not None and not parent.is_deleted:
            return parent
    return None


def link_choices(company, dashboard: Dashboard | None = None):
    """Published dashboards of this company that can be selected as a parent."""
    if company is None:
        return Dashboard.objects.none()
    qs = Dashboard.objects.filter(
        company=company,
        status=DashboardStatus.PUBLISHED,
        is_deleted=False,
    )
    if dashboard is not None and dashboard.pk:
        blocked = descendant_ids(dashboard)
        blocked.add(dashboard.pk)
        qs = qs.exclude(pk__in=blocked)
        parent_id = dashboard.linked_dashboard_id
        if parent_id and parent_id not in blocked:
            qs = (
                qs
                | Dashboard.objects.filter(
                    pk=parent_id,
                    company=company,
                    is_deleted=False,
                )
            ).distinct()
    return qs.order_by("name", "id")


def iter_descendant_dashboards(dashboard: Dashboard):
    seen = {dashboard.pk}
    frontier = [dashboard.pk]
    for _ in range(_MAX_CHAIN):
        children = list(Dashboard.objects.filter(linked_dashboard_id__in=frontier))
        nxt = []
        for child in children:
            if child.pk in seen:
                continue
            seen.add(child.pk)
            nxt.append(child.pk)
            yield child
        if not nxt:
            break
        frontier = nxt
