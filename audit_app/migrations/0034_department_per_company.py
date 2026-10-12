"""Departments belong to one main company again."""

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("audit_app", "0033_department_shared_across_companies"),
    ]

    operations = [
        migrations.AddField(
            model_name="department",
            name="company",
            field=models.ForeignKey(
                blank=False,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="departments",
                to="audit_app.company",
                verbose_name="Company",
            ),
        ),
        migrations.RemoveConstraint(
            model_name="department",
            name="uniq_active_department_name",
        ),
        migrations.AddConstraint(
            model_name="department",
            constraint=models.UniqueConstraint(
                fields=("company", "active_name_key"),
                name="uniq_active_department_name_company",
            ),
        ),
        migrations.AlterModelOptions(
            name="department",
            options={
                "ordering": ["company__code", "name"],
                "verbose_name": "Department",
                "verbose_name_plural": "Departments",
            },
        ),
    ]
