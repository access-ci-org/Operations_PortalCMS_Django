from django import forms
from django.utils import timezone
from zoneinfo import ZoneInfo

from resources.models import CiderInfrastructure
from resources.services import get_active_infrastructure_queryset

from .models import SystemStatusNews

NEWS_TIME_ZONE = ZoneInfo("America/Chicago")


class CentralDateTimeField(forms.DateTimeField):
    """Parse and render schedule dates in Central time, independent of site settings."""

    def clean(self, value):
        with timezone.override(NEWS_TIME_ZONE):
            return super().clean(value)

    def prepare_value(self, value):
        if value is not None and timezone.is_aware(value):
            value = timezone.localtime(value, NEWS_TIME_ZONE)
        return super().prepare_value(value)


class SystemStatusNewsForm(forms.ModelForm):
    email_notification = forms.BooleanField(
        required=False,
        initial=False,
        label="Email everyone with access",
        widget=forms.CheckboxInput(attrs={"class": "form-check-input"}),
    )
    subscriber_notification = forms.BooleanField(
        required=False,
        initial=False,
        label="Email only subscribers",
        widget=forms.CheckboxInput(attrs={"class": "form-check-input"}),
    )
    slack_notification = forms.BooleanField(
        required=False,
        initial=False,
        label="Post to Slack",
        widget=forms.CheckboxInput(attrs={"class": "form-check-input"}),
    )
    start_datetime = CentralDateTimeField(
        required=True,
        label="Start Date and Time",
        widget=forms.DateTimeInput(
            format="%Y-%m-%dT%H:%M", attrs={"class": "form-control", "type": "datetime-local"}
        ),
        help_text="Enter in Central Time (America/Chicago). Daylight saving time is applied automatically.",
    )
    end_datetime = CentralDateTimeField(
        required=False,
        label="End Date and Time",
        widget=forms.DateTimeInput(
            format="%Y-%m-%dT%H:%M", attrs={"class": "form-control", "type": "datetime-local"}
        ),
        help_text="Enter in Central Time (America/Chicago). May be left blank for permanent configuration changes.",
    )
    affected_infrastructure_items = forms.ModelMultipleChoiceField(
        queryset=CiderInfrastructure.objects.none(),
        required=False,
        label="Affected Infrastructure",
        widget=forms.SelectMultiple(attrs={"class": "form-select", "size": 10}),
        help_text="Select one or more infrastructure resources from CIDER. Leave blank if not resource-specific.",
    )

    class Meta:
        model = SystemStatusNews
        fields = [
            "subject",
            "content",
            "infrastructure_news_type",
            "affected_infrastructure_items",
            "start_datetime",
            "end_datetime",
            "is_active",
        ]
        labels = {
            "subject": "Subject",
            "content": "News Content",
            "infrastructure_news_type": "Infrastructure News Type",
            "affected_infrastructure_items": "Affected Infrastructure",
            "is_active": "Active",
        }
        widgets = {
            "subject": forms.TextInput(attrs={"class": "form-control", "placeholder": "Enter news subject"}),
            "infrastructure_news_type": forms.Select(attrs={"class": "form-select"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["affected_infrastructure_items"].queryset = get_active_infrastructure_queryset()
        self.fields["affected_infrastructure_items"].label_from_instance = (
            lambda item: f"{item.resource_descriptive_name} - {item.info_resourceid}"
        )
        if self.instance.pk:
            self.fields["affected_infrastructure_items"].initial = self.instance.affected_infrastructure_items.all()
            self.fields["email_notification"].initial = self.instance.distribution_email_everyone
            self.fields["subscriber_notification"].initial = self.instance.distribution_email_subscribers
            self.fields["slack_notification"].initial = self.instance.distribution_post_to_slack

    def save_related_fields(self, news):
        affected_items = list(self.cleaned_data.get("affected_infrastructure_items", []))
        news.affected_infrastructure_items.set(affected_items)
        news.affected_infrastructure = ", ".join(item.info_resourceid for item in affected_items)
        news.distribution_email_everyone = self.cleaned_data["email_notification"]
        news.distribution_email_subscribers = self.cleaned_data["subscriber_notification"]
        news.distribution_post_to_slack = self.cleaned_data["slack_notification"]
        news.save(
            update_fields=[
                "affected_infrastructure",
                "distribution_email_everyone",
                "distribution_email_subscribers",
                "distribution_post_to_slack",
            ]
        )
