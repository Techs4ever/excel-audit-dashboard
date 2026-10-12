"""Share departments across every company."""

from django.db import migrations, models


def collapse_duplicate_departments(apps, schema_editor):
    Department = apps.get_model("audit_app", "Department")
    Access = apps.get_model("audit_app", "UserDepartmentAccess")
    keepers: dict[str, int] = {}
    for department in Department.objects.order_by("id"):
        key = department.active_name_key
        if not key:
            continue
        keeper_id = keepers.get(key)
        if keeper_id is None:
            keepers[key] = department.id
            continue
        for access in Access.objects.filter(department_id=department.id):
            already_linked = (
                Access.objects.filter(
                    user_id=access.user_id,
                    department_id=keeper_id,
                    is_deleted=False,
                )
                .exclude(pk=access.pk)
                .exists()
            )
            if already_linked:
                access.is_deleted = True
                access.active_department_id = None
                access.save(update_fields=["is_deleted", "active_department_id"])
            else:
                access.department_id = keeper_id
                if not access.is_deleted:
                    access.active_department_id = keeper_id
                access.save(update_fields=["department_id", "active_department_id"])
        department.active_name_key = None
        department.is_deleted = True
        department.is_active = False
        department.save(update_fields=["active_name_key", "is_deleted", "is_active"])


class Migration(migrations.Migration):

    dependencies = [
        ("audit_app", "0032_department_access"),
    ]

    operations = [
        migrations.RunPython(
            collapse_duplicate_departments,
            migrations.RunPython.noop,
        ),
        migrations.RemoveConstraint(
            model_name="department",
            name="uniq_active_department_name_company",
        ),
        migrations.RemoveField(
            model_name="department",
            name="company",
        ),
        migrations.AddConstraint(
            model_name="department",
            constraint=models.UniqueConstraint(
                fields=("active_name_key",),
                name="uniq_active_department_name",
            ),
        ),
        migrations.AlterModelOptions(
            name="department",
            options={
                "ordering": ["name"],
                "verbose_name": "Department",
                "verbose_name_plural": "Departments",
            },
        ),
        migrations.AlterModelOptions(
            name="userdepartmentaccess",
            options={
                "ordering": ["department__name"],
                "verbose_name": "Department access",
                "verbose_name_plural": "Department access",
            },
        ),
    ]
