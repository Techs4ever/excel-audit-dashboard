"""Hide-dashboard permission per template, and dashboard hidden flag."""

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("audit_app", "0030_dashboard_linked_dashboard"),
    ]

    operations = [
        migrations.AddField(
            model_name="companymembership",
            name="can_hide_dashboards",
            field=models.BooleanField(
                default=False,
                help_text=(
                    "Hide every dashboard of this template from all users, including the creator. "
                    "Only members with this permission can show it again."
                ),
                verbose_name="Can hide dashboards",
            ),
        ),
        migrations.AddField(
            model_name="companymembershiptemplateaccess",
            name="can_hide_dashboards",
            field=models.BooleanField(
                default=False,
                verbose_name="Can hide dashboards",
            ),
        ),
        migrations.AddField(
            model_name="dashboard",
            name="is_hidden",
            field=models.BooleanField(
                db_index=True,
                default=False,
                help_text=(
                    "When enabled, nobody can see or open this dashboard except users "
                    "who have the hide permission for its template."
                ),
                verbose_name="Hidden from everyone",
            ),
        ),
    ]
