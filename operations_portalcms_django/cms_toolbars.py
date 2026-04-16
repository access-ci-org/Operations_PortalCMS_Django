from cms.toolbar.items import ButtonList
from django.urls import reverse
from django.utils.translation import gettext_lazy as _

from djangocms_versioning.cms_toolbars import LOCK_VERSIONS, VersioningToolbar, replace_toolbar
from djangocms_versioning.constants import DRAFT
from djangocms_versioning.models import Version


class ReviewWorkflowVersioningToolbar(VersioningToolbar):
    def _add_unlock_button(self):
        if not LOCK_VERSIONS or not self._is_versioned():
            return

        version = Version.objects.filter_by_content_grouping_values(self.toolbar.obj).filter(state=DRAFT).first()
        if not version or not version.check_unlock.as_bool(self.request.user):
            return

        can_unlock = self.request.user.has_perm(f"{version._meta.app_label}.delete_versionlock")
        owns_lock = version.locked_by_id == self.request.user.pk
        can_publish = version.check_publish.as_bool(self.request.user)

        if owns_lock and not can_publish:
            item = ButtonList(side=self.toolbar.RIGHT)
            submit_url = reverse(
                "operations_portalcms_django:submit_page_draft_for_review",
                args=(version.pk,),
            )
            item.add_button(
                _("Submit for Review"),
                url=submit_url,
                disabled=False,
                extra_classes=[
                    "cms-btn-action",
                    "cms-form-post-method",
                    "cms-versioning-js-submit-for-review-btn",
                ],
            )
            self.toolbar.add_item(item)
            return

        if not can_unlock:
            return

        item = ButtonList(side=self.toolbar.RIGHT)
        current_path = self.request.get_full_path()
        unlock_url = (
            reverse(
                "operations_portalcms_django:unlock_cms_page_draft",
                args=(version.pk,),
            )
            + f"?next={current_path}"
        )
        item.add_button(
            _("Unlock"),
            url=unlock_url,
            disabled=False,
            extra_classes=[
                "cms-btn-action",
                "cms-form-post-method",
                "cms-versioning-js-unlock-btn",
            ],
        )
        self.toolbar.add_item(item)


replace_toolbar(VersioningToolbar, ReviewWorkflowVersioningToolbar)
