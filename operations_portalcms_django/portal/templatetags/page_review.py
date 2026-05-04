from django import template
from django.urls import reverse

from djangocms_versioning.constants import DRAFT

register = template.Library()


def _get_version(content):
    if hasattr(content, "prefetched_versions"):
        return content.prefetched_versions[0]
    return content.versions.first()


@register.filter
def url_submit_for_review(content, user):
    version = _get_version(content)
    if not version:
        return ""

    if version.state != DRAFT:
        return ""

    if version.locked_by_id != user.pk:
        return ""

    if version.check_publish.as_bool(user):
        return ""

    return reverse(
        "portal:submit_page_draft_for_review",
        args=(version.pk,),
    )
