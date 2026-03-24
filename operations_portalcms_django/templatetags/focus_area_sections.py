from django import template

from operations_portalcms_django.models import FocusAreaSection
from operations_portalcms_django.utils import can_edit_focus_area_section

register = template.Library()


@register.simple_tag(takes_context=True)
def get_focus_area_sections(context):
    """
    Return active managed focus-area sections for the current CMS page keyed by section_key.
    """
    current_page = context.get('current_page')
    request = context.get('request')
    if current_page is None and request is not None:
        current_page = getattr(request, 'current_page', None)

    if current_page is None:
        return {}

    sections = (
        FocusAreaSection.objects.filter(page=current_page, is_active=True)
        .select_related('updated_by')
        .prefetch_related('owner_groups')
        .order_by('section_key')
    )
    return {section.section_key: section for section in sections}


@register.filter
def can_edit_focus_section(user, section):
    return can_edit_focus_area_section(user, section)
