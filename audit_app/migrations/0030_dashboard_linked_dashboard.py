"""Link a dashboard to a published dashboard so attachments are inherited."""

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("audit_app", "0029_compliance_attachment_kinds"),
    ]

    operations = [
        migrations.AddField(
            model_name="dashboard",
            name="linked_dashboard",
            field=models.ForeignKey(
                blank=True,
                help_text=(
                    "Inherit attachment files from this published dashboard. "
                    "Must be the same company and template. The chain includes that dashboard's own link."
                ),
                null=True,
                on_delete=models.SET_NULL,
                related_name="linked_from_dashboards",
                to="audit_app.dashboard",
                verbose_name="Linked published dashboard",
            ),
        ),
    ]
