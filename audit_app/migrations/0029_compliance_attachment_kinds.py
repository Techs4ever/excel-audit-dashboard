"""Add Compliance dashboard attachment kinds."""
from __future__ import annotations

from django.db import migrations, models


NEW_KINDS = (
    ("legislation", "التشريعات و الانظمة و القوانين"),
    ("complianceDetailed", "تقرير ادارة الالتزام التفصيلي"),
    ("complianceQuarterly", "تقرير ادارة الالتزام الربعي"),
)

ATTACHMENT_KIND_CHOICES = [
    ("deck", "Company wise Audit committee report"),
    ("highRisk", "High Risk Observations & Emerging Risks"),
    ("tgaViolations", "TGA Violations Report"),
    ("missingVehicle", "Missing Vehicle Report"),
    ("internalAuditQuarterly", "Internal Audit Quarterly Report"),
    ("specialAssignment", "Special Assignment Report"),
    ("accApprovedMoM", "ACC Aproved MoM"),
    ("internalAuditDetailed", "Internal Audit Detailed Reports"),
    *NEW_KINDS,
]


def seed_compliance_attachment_settings(apps, schema_editor):
    Company = apps.get_model("audit_app", "Company")
    CompanyAttachmentSetting = apps.get_model("audit_app", "CompanyAttachmentSetting")
    for company in Company.objects.filter(company_kind="main"):
        for kind, _label in NEW_KINDS:
            CompanyAttachmentSetting.objects.get_or_create(
                company=company,
                attachment_kind=kind,
                defaults={"is_enabled": True},
            )


class Migration(migrations.Migration):

    dependencies = [
        ("audit_app", "0028_membership_template_access"),
    ]

    operations = [
        migrations.AlterField(
            model_name="companyattachmentsetting",
            name="attachment_kind",
            field=models.CharField(
                choices=ATTACHMENT_KIND_CHOICES,
                max_length=32,
                verbose_name="Attachment type",
            ),
        ),
        migrations.RunPython(seed_compliance_attachment_settings, migrations.RunPython.noop),
    ]
