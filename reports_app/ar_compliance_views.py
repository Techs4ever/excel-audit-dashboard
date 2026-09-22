"""API views for Arabic compliance dashboard (scoped per Dashboard pk)."""
from __future__ import annotations

import json
import re

from django.contrib.auth.decorators import login_required
from django.http import HttpResponse, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_http_methods

from ai_excel_dashboard import _valid_obs_email, load_smtp_config, send_audit_observation_email_smtp
from arabic_compliance_dashboard.data import (
    dataframe_from_dashboard,
    is_ar_compliance_template,
    load_rows_from_dashboard,
    main_brand_logo_pack,
    resolve_brand_logo_company,
)
from arabic_compliance_dashboard.engine import (
    ASSESSMENT_FORM_LIMIT,
    build_assessment_forms,
    build_audit_plan_panel,
    build_record_list,
    build_summary,
    compute_aging,
    compute_plan_status_report,
    legal_details_from_rows,
    parse_query_params,
    selected_from_params,
)
from arabic_compliance_dashboard.word_export import (
    build_aging_matrix_docx,
    build_annual_tracking_docx,
    build_assessment_forms_docx,
    build_assessment_list_docx,
    build_legal_text_docx,
    build_plan_status_docx,
    decode_logo_data_uri,
)
from arabic_compliance_dashboard.generator import export_snapshot_html
from reports_app.dashboard_workflow import (
    activate_company_for_dashboard,
    has_dashboard_list_perm,
    load_dashboard_cross_company,
)


def _resolve_ar_dashboard(request, pk: int):
    dashboard = load_dashboard_cross_company(request.user, pk)
    if not dashboard or not is_ar_compliance_template(dashboard.template_type):
        return None, JsonResponse({"error": "not_found"}, status=404)
    if not activate_company_for_dashboard(request, dashboard):
        return None, JsonResponse({"error": "forbidden"}, status=403)
    active = getattr(request, "active_company", None) or dashboard.company
    if not has_dashboard_list_perm(request.user, active):
        return None, JsonResponse({"error": "forbidden"}, status=403)
    return dashboard, None


def _rows_for(dashboard):
    return load_rows_from_dashboard(dashboard)


def _dashboard_logo_bytes(dashboard) -> bytes | None:
    company = getattr(dashboard, "company", None)
    if not company:
        return None
    logos, default_code = main_brand_logo_pack(company)
    uri = (logos or {}).get(default_code or "") if logos else None
    if not uri and logos:
        uri = next(iter(logos.values()), None)
    blob = decode_logo_data_uri(uri)
    if blob:
        return blob
    from audit_app.company_access import tenant_root

    root = tenant_root(company)
    logo_field = getattr(company, "logo", None) or getattr(root, "logo", None)
    if not logo_field:
        return None
    try:
        return logo_field.open("rb").read()
    except Exception:
        return None


@login_required
@require_GET
def ar_api_summary(request, pk: int):
    dashboard, err = _resolve_ar_dashboard(request, pk)
    if err:
        return err
    rows = _rows_for(dashboard)
    selected = selected_from_params(parse_query_params(request.GET))
    return JsonResponse(build_summary(rows, selected))


@login_required
@require_GET
def ar_api_records(request, pk: int):
    dashboard, err = _resolve_ar_dashboard(request, pk)
    if err:
        return err
    rows = _rows_for(dashboard)
    selected = selected_from_params(parse_query_params(request.GET))
    return JsonResponse(
        build_record_list(
            rows,
            selected,
            aging_time=(request.GET.get("aging_time") or "").strip() or None,
            aging_risk=(request.GET.get("aging_risk") or "").strip() or None,
            reference_raw=(request.GET.get("reference") or "").strip() or None,
            final_status_change=(request.GET.get("final_status_change") or "").strip() in {"1", "true", "yes"},
            assessment_new=(request.GET.get("assessment_new") or "").strip() in {"1", "true", "yes"},
            plan_dept=(request.GET.get("plan_dept") if "plan_dept" in request.GET else None),
            plan_bucket=(request.GET.get("plan_bucket") or "").strip() or None,
            plan_risk=(request.GET.get("plan_risk") or "").strip() or None,
        )
    )


@login_required
@require_GET
def ar_api_aging_summary(request, pk: int):
    dashboard, err = _resolve_ar_dashboard(request, pk)
    if err:
        return err
    ref = (request.GET.get("reference") or "").strip()
    if not ref:
        return JsonResponse({"error": "Missing reference date"}, status=400)
    date_source = (request.GET.get("aging_date_source") or "target").lower()
    rows = _rows_for(dashboard)
    selected = selected_from_params(parse_query_params(request.GET))
    out = compute_aging(
        rows,
        selected,
        ref,
        "modified" if date_source == "modified" else "target",
    )
    if out.get("error"):
        return JsonResponse({"error": out["error"]}, status=400)
    return JsonResponse(out)


@login_required
@require_GET
def ar_api_export_aging_docx(request, pk: int):
    dashboard, err = _resolve_ar_dashboard(request, pk)
    if err:
        return err
    ref = (request.GET.get("reference") or "").strip()
    if not ref:
        return JsonResponse({"error": "Missing reference date"}, status=400)
    date_source = (request.GET.get("aging_date_source") or "target").lower()
    rows = _rows_for(dashboard)
    selected = selected_from_params(parse_query_params(request.GET))
    out = compute_aging(
        rows,
        selected,
        ref,
        "modified" if date_source == "modified" else "target",
    )
    if out.get("error"):
        return JsonResponse({"error": out["error"]}, status=400)
    expand = (request.GET.get("expand_over_year") or "").strip().lower() in {"1", "true", "yes"}
    raw = build_aging_matrix_docx(
        out,
        expand_over_year=expand,
        logo_bytes=_dashboard_logo_bytes(dashboard),
    )
    resp = HttpResponse(
        raw,
        content_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    )
    resp["Content-Disposition"] = 'attachment; filename="aging-summary.docx"'
    return resp


@login_required
@require_GET
def ar_api_plan_status_summary(request, pk: int):
    dashboard, err = _resolve_ar_dashboard(request, pk)
    if err:
        return err
    ref = (request.GET.get("reference") or "").strip()
    rows = _rows_for(dashboard)
    selected = selected_from_params(parse_query_params(request.GET))
    return JsonResponse(compute_plan_status_report(rows, selected, ref))


@login_required
@require_GET
def ar_api_export_plan_status_docx(request, pk: int):
    dashboard, err = _resolve_ar_dashboard(request, pk)
    if err:
        return err
    ref = (request.GET.get("reference") or "").strip()
    rows = _rows_for(dashboard)
    selected = selected_from_params(parse_query_params(request.GET))
    payload = compute_plan_status_report(rows, selected, ref)
    raw = build_plan_status_docx(payload, logo_bytes=_dashboard_logo_bytes(dashboard))
    resp = HttpResponse(
        raw,
        content_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    )
    resp["Content-Disposition"] = 'attachment; filename="plan-corrective-status.docx"'
    return resp


@login_required
@require_http_methods(["GET", "POST"])
def ar_api_legal_text_details(request, pk: int):
    dashboard, err = _resolve_ar_dashboard(request, pk)
    if err:
        return err
    text = (request.GET.get("text") or "").strip()
    if not text and request.method == "POST":
        try:
            body = json.loads(request.body.decode("utf-8"))
            text = str(body.get("text") or "").strip()
        except Exception:
            text = ""
    if not text:
        return JsonResponse({"error": "Not found"}, status=404)
    rows = _rows_for(dashboard)
    rec = legal_details_from_rows(rows, text)
    if not rec:
        return JsonResponse({"error": "Not found"}, status=404)
    return JsonResponse(rec)


@login_required
@require_GET
def ar_api_legal_text_row_images(request, pk: int):
    dashboard, err = _resolve_ar_dashboard(request, pk)
    if err:
        return err
    return JsonResponse({"images": []})


@login_required
@require_http_methods(["POST", "OPTIONS"])
def ar_api_send_legal_text_email(request, pk: int):
    if request.method == "OPTIONS":
        return JsonResponse({}, status=204)
    dashboard, err = _resolve_ar_dashboard(request, pk)
    if err:
        return err
    try:
        data = json.loads(request.body.decode("utf-8"))
    except Exception:
        return JsonResponse({"error": "bad_json"}, status=400)
    text = str(data.get("text") or "").strip()
    to_addr = str(data.get("to") or "").strip()
    if not to_addr:
        rows = _rows_for(dashboard)
        rec = legal_details_from_rows(rows, text)
        to_addr = (rec or {}).get("recipient_email") or ""
    if not _valid_obs_email(to_addr):
        return JsonResponse({"error": "bad_email"}, status=400)
    if not text:
        return JsonResponse({"error": "bad_text"}, status=400)
    cfg = load_smtp_config()
    if not cfg:
        return JsonResponse({"error": "smtp_not_configured"}, status=503)
    try:
        send_audit_observation_email_smtp(cfg, to_addr=to_addr, observation=text)
    except Exception as exc:
        return JsonResponse({"error": str(exc)[:500]}, status=500)
    return JsonResponse({"ok": True, "to": to_addr})


@csrf_exempt
@login_required
@require_http_methods(["POST", "OPTIONS"])
def ar_api_export_legal_text_docx(request, pk: int):
    if request.method == "OPTIONS":
        return JsonResponse({}, status=204)
    dashboard, err = _resolve_ar_dashboard(request, pk)
    if err:
        return err
    try:
        data = json.loads(request.body.decode("utf-8"))
    except Exception:
        return JsonResponse({"error": "bad_json"}, status=400)
    text = str(data.get("text") or "").strip()
    if not text:
        return JsonResponse({"error": "missing_text"}, status=400)
    fields = data.get("fields") or []
    if not fields:
        rows = _rows_for(dashboard)
        rec = legal_details_from_rows(rows, text)
        fields = (rec or {}).get("fields") or []
    raw = build_legal_text_docx(text, fields, logo_bytes=_dashboard_logo_bytes(dashboard))
    safe = re.sub(r"[^\w\-]+", "_", text[:40]) or "legal-text"
    resp = HttpResponse(
        raw,
        content_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    )
    resp["Content-Disposition"] = f'attachment; filename="{safe}.docx"'
    return resp


ar_api_export_legal_text_pptx = ar_api_export_legal_text_docx


@login_required
@require_GET
def ar_api_assessment_forms(request, pk: int):
    dashboard, err = _resolve_ar_dashboard(request, pk)
    if err:
        return err
    rows = _rows_for(dashboard)
    selected = selected_from_params(parse_query_params(request.GET))
    return JsonResponse(build_assessment_forms(rows, selected))


@login_required
@require_GET
def ar_api_export_assessment_forms_docx(request, pk: int):
    dashboard, err = _resolve_ar_dashboard(request, pk)
    if err:
        return err
    rows = _rows_for(dashboard)
    selected = selected_from_params(parse_query_params(request.GET))
    forms = build_assessment_forms(rows, selected).get("forms") or []
    raw = build_assessment_forms_docx(forms, logo_bytes=_dashboard_logo_bytes(dashboard))
    resp = HttpResponse(
        raw,
        content_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    )
    resp["Content-Disposition"] = 'attachment; filename="assessment-current-year.docx"'
    return resp


@login_required
@require_GET
def ar_api_export_assessment_list_docx(request, pk: int):
    dashboard, err = _resolve_ar_dashboard(request, pk)
    if err:
        return err
    rows = _rows_for(dashboard)
    selected = selected_from_params(parse_query_params(request.GET))
    records = build_record_list(
        rows,
        selected,
        assessment_new=True,
        limit=ASSESSMENT_FORM_LIMIT,
    ).get("records") or []
    raw = build_assessment_list_docx(records, logo_bytes=_dashboard_logo_bytes(dashboard))
    resp = HttpResponse(
        raw,
        content_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    )
    resp["Content-Disposition"] = 'attachment; filename="assessment-current-year-list.docx"'
    return resp


@login_required
@require_GET
def ar_api_export_annual_tracking_docx(request, pk: int):
    dashboard, err = _resolve_ar_dashboard(request, pk)
    if err:
        return err
    rows = _rows_for(dashboard)
    selected = selected_from_params(parse_query_params(request.GET))
    records = build_record_list(
        rows,
        selected,
        final_status_change=True,
        limit=ASSESSMENT_FORM_LIMIT,
    ).get("records") or []
    raw = build_annual_tracking_docx(records, logo_bytes=_dashboard_logo_bytes(dashboard))
    resp = HttpResponse(
        raw,
        content_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    )
    resp["Content-Disposition"] = 'attachment; filename="annual-compliance-tracking.docx"'
    return resp


@login_required
@require_GET
def ar_api_export_dashboard_html(request, pk: int):
    dashboard, err = _resolve_ar_dashboard(request, pk)
    if err:
        return err
    df = dataframe_from_dashboard(dashboard)
    brand_logos, default_brand_code = main_brand_logo_pack(dashboard.company)
    html_out = export_snapshot_html(
        df,
        dashboard_id=dashboard.pk,
        brand_logos=brand_logos,
        default_brand_code=default_brand_code,
    )
    resp = HttpResponse(html_out, content_type="text/html; charset=utf-8")
    resp["Content-Disposition"] = 'attachment; filename="dashboard-export.html"'
    return resp


@login_required
@require_GET
def ar_api_brand_logo(request, pk: int):
    dashboard, err = _resolve_ar_dashboard(request, pk)
    if err:
        return err

    company = dashboard.company
    if not company:
        return HttpResponse(status=204)

    from audit_app.company_access import tenant_root

    code = (request.GET.get("code") or "").strip()
    target = resolve_brand_logo_company(company, code or None)
    root = tenant_root(company)
    logo_field = target.logo if getattr(target, "logo", None) else root.logo
    if not logo_field:
        return HttpResponse(status=204)
    try:
        import mimetypes

        mime = mimetypes.guess_type(logo_field.name)[0] or "image/png"
        return HttpResponse(logo_field.open("rb").read(), content_type=mime)
    except Exception:
        return HttpResponse(status=204)


@login_required
@require_GET
def ar_api_audit_plan_panel(request, pk: int):
    dashboard, err = _resolve_ar_dashboard(request, pk)
    if err:
        return err
    rows = _rows_for(dashboard)
    selected = selected_from_params(parse_query_params(request.GET))
    return JsonResponse(build_audit_plan_panel(rows, selected))
