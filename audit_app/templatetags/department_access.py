from django import template

from audit_app.models import Department

register = template.Library()


@register.simple_tag
def active_department_catalog():
    return [
        {"id": department.pk, "name": department.name}
        for department in Department.objects.filter(
            is_deleted=False,
            is_active=True,
        ).order_by("name")
    ]
