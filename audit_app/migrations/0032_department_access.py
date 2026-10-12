"""Company departments and per-user department access."""

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("audit_app", "0031_dashboard_hide_permission"),
    ]

    operations = [
        migrations.CreateModel(
            name="Department",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "is_deleted",
                    models.BooleanField(
                        db_index=True,
                        default=False,
                        verbose_name="Soft deleted",
                    ),
                ),
                (
                    "deleted_at",
                    models.DateTimeField(
                        blank=True, null=True, verbose_name="Deleted at"
                    ),
                ),
                (
                    "name",
                    models.CharField(
                        help_text=(
                            "Must match the Department value in the Excel file "
                            "(spacing and letter case are ignored)."
                        ),
                        max_length=255,
                        verbose_name="Department",
                    ),
                ),
                (
                    "excel_aliases",
                    models.TextField(
                        blank=True,
                        help_text=(
                            "Optional extra names as they appear in the Excel Department "
                            "column, one per line. The department name itself is always accepted."
                        ),
                        verbose_name="Excel department names",
                    ),
                ),
                (
                    "is_active",
                    models.BooleanField(default=True, verbose_name="Active"),
                ),
                (
                    "created_at",
                    models.DateTimeField(auto_now_add=True, verbose_name="Created at"),
                ),
                (
                    "active_name_key",
                    models.CharField(
                        blank=True,
                        editable=False,
                        max_length=255,
                        null=True,
                        verbose_name="Active name key",
                    ),
                ),
                (
                    "company",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="departments",
                        to="audit_app.company",
                        verbose_name="Company",
                    ),
                ),
                (
                    "deleted_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="+",
                        to=settings.AUTH_USER_MODEL,
                        verbose_name="Deleted by",
                    ),
                ),
            ],
            options={
                "verbose_name": "Department",
                "verbose_name_plural": "Departments",
                "ordering": ["company__code", "name"],
            },
        ),
        migrations.CreateModel(
            name="UserDepartmentAccess",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "is_deleted",
                    models.BooleanField(
                        db_index=True,
                        default=False,
                        verbose_name="Soft deleted",
                    ),
                ),
                (
                    "deleted_at",
                    models.DateTimeField(
                        blank=True, null=True, verbose_name="Deleted at"
                    ),
                ),
                (
                    "created_at",
                    models.DateTimeField(auto_now_add=True, verbose_name="Created at"),
                ),
                (
                    "active_department_id",
                    models.PositiveBigIntegerField(
                        blank=True,
                        editable=False,
                        null=True,
                        verbose_name="Active department id",
                    ),
                ),
                (
                    "deleted_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="+",
                        to=settings.AUTH_USER_MODEL,
                        verbose_name="Deleted by",
                    ),
                ),
                (
                    "department",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="user_accesses",
                        to="audit_app.department",
                        verbose_name="Department",
                    ),
                ),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="department_accesses",
                        to=settings.AUTH_USER_MODEL,
                        verbose_name="User",
                    ),
                ),
            ],
            options={
                "verbose_name": "Department access",
                "verbose_name_plural": "Department access",
                "ordering": ["department__company__code", "department__name"],
            },
        ),
        migrations.AddConstraint(
            model_name="department",
            constraint=models.UniqueConstraint(
                fields=("company", "active_name_key"),
                name="uniq_active_department_name_company",
            ),
        ),
        migrations.AddConstraint(
            model_name="userdepartmentaccess",
            constraint=models.UniqueConstraint(
                fields=("user", "active_department_id"),
                name="uniq_active_user_department_access",
            ),
        ),
    ]
