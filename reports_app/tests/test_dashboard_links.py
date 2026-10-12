"""Linked dashboards inherit attachment files and cannot drop them."""
from __future__ import annotations

from pathlib import Path

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import RequestFactory

from audit_app.models import CompanyAttachmentSetting, Dashboard, DashboardStatus
from reports_app.dashboard_links import (
    DashboardLinkError,
    effective_source_files,
    link_choices,
    resolve_link_target,
)
from reports_app.services.report_generation import (
    build_attachment_form_slots,
    update_dashboard_review_attachments,
)


def _file(root: Path, rel: str) -> str:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"PK\x03\x04deck")
    return rel.replace("\\", "/")


def _dashboard(company, name, *, status, source_files=None, linked=None, template="IAD"):
    return Dashboard.objects.create(
        name=name,
        report_id=f"rid-link-{name}",
        company=company,
        status=status,
        template_type=template,
        source_files=source_files or {},
        linked_dashboard=linked,
    )


@pytest.mark.django_db
def test_child_inherits_parent_and_grandparent_in_order(tmp_path, settings, btc_company):
    settings.MEDIA_ROOT = tmp_path
    btc_company.ensure_attachment_settings()
    parent_deck = _file(tmp_path, "decks/rid-link-X/deck1_parent.pptx")
    parent_risk = _file(tmp_path, "decks/rid-link-X/high_risk_deck1_risk.pptx")
    mid_deck = _file(tmp_path, "decks/rid-link-Y/deck1_mid.pptx")
    child_deck = _file(tmp_path, "decks/rid-link-R/deck1_child.pptx")

    parent = _dashboard(
        btc_company,
        "X",
        status=DashboardStatus.PUBLISHED,
        source_files={"decks": [parent_deck], "high_risk_decks": [parent_risk]},
    )
    mid = _dashboard(
        btc_company,
        "Y",
        status=DashboardStatus.DRAFT,
        source_files={"decks": [mid_deck]},
        linked=parent,
    )
    child = _dashboard(
        btc_company,
        "R",
        status=DashboardStatus.DRAFT,
        source_files={"decks": [child_deck]},
        linked=mid,
    )

    merged = effective_source_files(child)
    assert merged["decks"] == [parent_deck, mid_deck, child_deck]
    assert merged["high_risk_decks"] == [parent_risk]

    slots = build_attachment_form_slots(child, locale="en", company=btc_company)
    deck = next(slot for slot in slots if slot["kind"] == "deck")
    assert [item["name"] for item in deck["existing_items"]] == [
        "deck1_parent.pptx",
        "deck1_mid.pptx",
        "deck1_child.pptx",
    ]
    assert deck["existing_items"][0]["inherited"] is True
    assert deck["existing_items"][0]["source_dashboard_name"] == "X"
    assert deck["existing_items"][1]["source_dashboard_name"] == "Y"
    assert deck["existing_items"][2]["inherited"] is False
    assert deck["inherited_count"] == 2
    assert deck["own_count"] == 1


@pytest.mark.django_db
def test_review_save_cannot_delete_inherited_file(tmp_path, settings, btc_company):
    settings.MEDIA_ROOT = tmp_path
    btc_company.ensure_attachment_settings()
    parent_deck = _file(tmp_path, "decks/rid-link-Parent/deck1_locked.pptx")
    own_deck = _file(tmp_path, "decks/rid-link-Child/deck1_own.pptx")
    parent = _dashboard(
        btc_company,
        "Parent",
        status=DashboardStatus.PUBLISHED,
        source_files={"decks": [parent_deck]},
    )
    child = _dashboard(
        btc_company,
        "Child",
        status=DashboardStatus.UNDER_REVIEW,
        source_files={"excel": ["x.xlsx"], "decks": [own_deck]},
        linked=parent,
    )

    factory = RequestFactory()
    request = factory.post(
        "/review-attachments/",
        data={
            "linked_dashboard_id": str(parent.pk),
            "remove_deck_item": [parent_deck, own_deck],
        },
    )
    request.session = {"ui_lang": "en"}
    update_dashboard_review_attachments(request, child, company=btc_company)
    child.refresh_from_db()

    assert parent_deck not in (child.source_files.get("decks") or [])
    assert own_deck not in (child.source_files.get("decks") or [])
    assert (tmp_path / parent_deck).is_file()
    assert not (tmp_path / own_deck).is_file()
    assert effective_source_files(child)["decks"] == [parent_deck]
    assert child.linked_dashboard_id == parent.pk


@pytest.mark.django_db
def test_link_rejects_other_company_draft_template_and_cycle(
    tmp_path, settings, btc_company, nat_company
):
    settings.MEDIA_ROOT = tmp_path
    published = _dashboard(btc_company, "Published", status=DashboardStatus.PUBLISHED)
    other = _dashboard(nat_company, "OtherCo", status=DashboardStatus.PUBLISHED)
    draft = _dashboard(btc_company, "DraftOnly", status=DashboardStatus.DRAFT)
    other_template = _dashboard(
        btc_company,
        "Compliance",
        status=DashboardStatus.PUBLISHED,
        template="CD",
    )
    child = _dashboard(btc_company, "ChildCo", status=DashboardStatus.DRAFT, linked=published)
    grandchild = _dashboard(
        btc_company, "Grand", status=DashboardStatus.DRAFT, linked=child
    )

    with pytest.raises(DashboardLinkError) as other_co:
        resolve_link_target(child, str(other.pk), company=btc_company, template_type="IAD", locale="en")
    assert other_co.value.code == "err_link_wrong_company"

    with pytest.raises(DashboardLinkError) as not_published:
        resolve_link_target(child, str(draft.pk), company=btc_company, template_type="IAD", locale="en")
    assert not_published.value.code == "err_link_not_published"

    with pytest.raises(DashboardLinkError) as wrong_template:
        resolve_link_target(
            child, str(other_template.pk), company=btc_company, template_type="IAD", locale="en"
        )
    assert wrong_template.value.code == "err_link_wrong_template"

    with pytest.raises(DashboardLinkError) as cycle:
        resolve_link_target(
            published, str(grandchild.pk), company=btc_company, template_type="IAD", locale="en"
        )
    assert cycle.value.code == "err_link_cycle"

    choices = list(link_choices(btc_company, grandchild).values_list("name", flat=True))
    assert "Published" in choices
    assert "OtherCo" not in choices
    assert "DraftOnly" not in choices
    assert "Grand" not in choices


@pytest.mark.django_db
def test_reviewer_can_set_link_while_pending(tmp_path, settings, btc_company):
    settings.MEDIA_ROOT = tmp_path
    btc_company.ensure_attachment_settings()
    parent_deck = _file(tmp_path, "decks/rid-link-Approved/deck1_a.pptx")
    parent = _dashboard(
        btc_company,
        "Approved",
        status=DashboardStatus.PUBLISHED,
        source_files={"decks": [parent_deck]},
    )
    pending = _dashboard(
        btc_company,
        "Pending",
        status=DashboardStatus.UNDER_REVIEW,
        source_files={"excel": ["x.xlsx"]},
    )
    CompanyAttachmentSetting.objects.filter(
        company=btc_company, attachment_kind="deck"
    ).update(max_files=1)

    factory = RequestFactory()
    request = factory.post(
        "/review-attachments/",
        data={"linked_dashboard_id": str(parent.pk)},
    )
    request.session = {"ui_lang": "ar"}
    update_dashboard_review_attachments(request, pending, company=btc_company)
    pending.refresh_from_db()
    assert pending.linked_dashboard_id == parent.pk
    assert pending.source_files.get("decks") in ([], None)
    assert effective_source_files(pending)["decks"] == [parent_deck]

    extra = SimpleUploadedFile(
        "extra.pptx",
        b"PK\x03\x04extra",
        content_type="application/vnd.openxmlformats-officedocument.presentationml.presentation",
    )
    blocked = factory.post(
        "/review-attachments/",
        data={"linked_dashboard_id": str(parent.pk)},
    )
    blocked.session = {"ui_lang": "en"}
    blocked.FILES.setlist("deck", [extra])
    with pytest.raises(ValueError, match="Too many attachments"):
        update_dashboard_review_attachments(blocked, pending, company=btc_company)
    assert (tmp_path / parent_deck).is_file()


@pytest.mark.django_db
def test_link_templates_parse():
    from django.template.loader import get_template

    get_template("reports_app/_dashboard_link_field.html")
    get_template("reports_app/upload.html")
    get_template("reports_app/dashboard_detail.html")


@pytest.mark.django_db
def test_upload_and_draft_edit_show_link_and_locked_files(
    client, uploader_user, btc_company, tmp_path, settings
):
    pytest.importorskip("docx")
    settings.MEDIA_ROOT = tmp_path
    btc_company.ensure_attachment_settings()
    parent_deck = _file(tmp_path, "decks/rid-link-Shown/deck1_locked.pptx")
    parent = _dashboard(
        btc_company,
        "ShownParent",
        status=DashboardStatus.PUBLISHED,
        source_files={"decks": [parent_deck]},
    )
    child = _dashboard(
        btc_company,
        "ShownChild",
        status=DashboardStatus.DRAFT,
        source_files={},
        linked=parent,
    )
    child.created_by = uploader_user
    child.save(update_fields=["created_by"])

    client.force_login(uploader_user)
    session = client.session
    session["active_company_id"] = btc_company.pk
    session["ui_lang"] = "ar"
    session.save()

    upload = client.get("/upload/?template=IAD")
    assert upload.status_code == 200
    upload_html = upload.content.decode()
    assert 'name="linked_dashboard_id"' in upload_html
    assert "ShownParent" in upload_html
    assert "same company" in upload_html

    edit = client.get(f"/upload/?resubmit={child.pk}")
    assert edit.status_code == 200
    edit_html = edit.content.decode()
    assert "deck1_locked.pptx" in edit_html
    assert "attach-existing__inherited" in edit_html
    assert "Inherited from" in edit_html
    assert f'value="{parent_deck}"' not in edit_html
