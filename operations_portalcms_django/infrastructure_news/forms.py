from django import forms
from resources.models import CiderInfrastructure
from resources.services import get_active_infrastructure_queryset
from .models import SystemStatusNews


class SystemStatusNewsForm(forms.ModelForm):
    start_datetime = forms.DateTimeField(
        required=True,
        label='Start Date and Time',
        widget=forms.DateTimeInput(attrs={'class': 'form-control', 'type': 'datetime-local'}),
        help_text='When the infrastructure outage or reconfiguration starts (in your local timezone)',
    )
    end_datetime = forms.DateTimeField(
        required=False,
        label='End Date and Time',
        widget=forms.DateTimeInput(attrs={'class': 'form-control', 'type': 'datetime-local'}),
        help_text='When this outage or configuration change ends. May be left blank for permanent configuration changes.',
    )
    affected_infrastructure_items = forms.ModelMultipleChoiceField(
        queryset=CiderInfrastructure.objects.none(),
        required=False,
        label='Affected Infrastructure',
        widget=forms.SelectMultiple(attrs={'class': 'form-select', 'size': 10}),
        help_text='Select one or more infrastructure resources from CIDER. Leave blank if not resource-specific.',
    )

    class Meta:
        model = SystemStatusNews
        fields = [
            'subject', 'content', 'infrastructure_news_type',
            'affected_infrastructure_items', 'start_datetime', 'end_datetime',
            'send_email', 'email_list', 'post_to_slack', 'slack_channel', 'is_active',
        ]
        labels = {
            'subject': 'Subject',
            'content': 'News Content',
            'infrastructure_news_type': 'Infrastructure News Type',
            'affected_infrastructure_items': 'Affected Infrastructure',
            'is_active': 'Active',
            'send_email': 'Send Email Notification',
            'email_list': 'Email Recipients',
            'post_to_slack': 'Post to Slack',
            'slack_channel': 'Slack Channel',
        }
        widgets = {
            'subject': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Enter news subject'}),
            'content': forms.Textarea(attrs={'class': 'form-control', 'rows': 8, 'placeholder': 'Enter news content'}),
            'infrastructure_news_type': forms.Select(attrs={'class': 'form-select'}),
            'email_list': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'email1@example.com, email2@example.com'}),
            'slack_channel': forms.TextInput(attrs={'class': 'form-control', 'placeholder': '#channel-name'}),
        }
        help_texts = {
            'content': 'To update news content text please follow formatting guidance at <a href="https://operations.access-ci.org/operational-status-communications" target="_blank">Operational Status Communications</a>',
            'email_list': 'Comma-separated email addresses for notifications',
            'slack_channel': 'Slack channel name (e.g., #operations-alerts)',
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['affected_infrastructure_items'].queryset = get_active_infrastructure_queryset()
        self.fields['affected_infrastructure_items'].label_from_instance = (
            lambda item: f"{item.info_resourceid} - {item.resource_descriptive_name}"
        )
        if self.instance.pk:
            self.fields['affected_infrastructure_items'].initial = self.instance.affected_infrastructure_items.all()

    def save_related_fields(self, news):
        affected_items = list(self.cleaned_data.get('affected_infrastructure_items', []))
        news.affected_infrastructure_items.set(affected_items)
        news.affected_infrastructure = ', '.join(item.info_resourceid for item in affected_items)
        news.save(update_fields=['affected_infrastructure'])
