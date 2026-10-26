"""Shared, delivery-neutral distribution choices for both news feeds."""

DISTRIBUTION_OPTION_FIELDS = (
    ("distribution_email_everyone", "Email everyone with access", "send_email"),
    ("distribution_email_subscribers", "Email only subscribers", None),
    ("distribution_post_to_slack", "Post to Slack", "post_to_slack"),
)

DISTRIBUTION_OPTIONS_BY_LABEL = {
    label: field_name for field_name, label, _legacy_field_name in DISTRIBUTION_OPTION_FIELDS
}
