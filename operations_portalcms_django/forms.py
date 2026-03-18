from django import forms
from .models import IntegrationNews, SystemStatusNews


class DateInput(forms.DateInput):
    """Custom widget for date fields with HTML5 date picker"""
    input_type = 'date'


class IntegrationNewsForm(forms.ModelForm):
    """Form for creating and updating Integration News"""
    
    INTEGRATION_NEWS_TYPES = [
        ('software_release', 'Software Release'),
        ('new_roadmap', 'New Integration Roadmap'),
        ('changed_roadmap', 'Changed Integration Roadmap'),
        ('new_roadmap_task', 'New Integration Roadmap Task'),
        ('changed_roadmap_task', 'Changed Integration Roadmap Task'),
    ]
    
    AFFECTED_ELEMENTS = [
        ('cloud_roadmap', 'ACCESS Allocated Production Cloud - Integration Roadmap'),
        ('compute_roadmap', 'ACCESS Allocated Production Compute - Integration Roadmap'),
        ('storage_roadmap', 'ACCESS Allocated Production Storage - Integration Roadmap'),
        ('science_gateway_roadmap', 'ACCESS Integrated Science Gateway - Integration Roadmap'),
        ('nagios', 'ACCESS Monitoring Service - Nagios'),
        ('online_service_roadmap', 'ACCESS Production Online Service - Integration Roadmap'),
        ('aws_registry', 'ACCESS Public AWS Container Registry'),
        ('cider', 'CiDeR - CyberInfrastructure Description Repository'),
        ('ipf', 'Information Publishing Framework (IPF) tool for publishing compute resource information'),
    ]
    
    news_type = forms.ChoiceField(
        choices=INTEGRATION_NEWS_TYPES,
        required=True,
        label='Integration News Type',
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    
    affected_element = forms.ChoiceField(
        choices=AFFECTED_ELEMENTS,
        required=True,
        label='Affected Element',
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    
    effective_date = forms.DateField(
        required=True,
        label='Effective Date',
        widget=DateInput(attrs={'class': 'form-control'}),
        help_text='Date when this news becomes effective'
    )
    
    expiration_date = forms.DateField(
        required=False,
        label='Expiration Date',
        widget=DateInput(attrs={'class': 'form-control'}),
        help_text='Date when this news expires (optional)'
    )
    
    email_notification = forms.BooleanField(
        required=False,
        initial=False,
        label='Email everyone',
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        help_text='Not yet implemented'
    )
    
    slack_notification = forms.BooleanField(
        required=False,
        initial=False,
        label='Post to Slack',
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        help_text='Not yet implemented'
    )
    
    class Meta:
        model = IntegrationNews
        fields = ['title', 'content']
        labels = {
            'title': 'Subject',
            'content': 'News Content',
        }
        widgets = {
            'title': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Enter news subject'
            }),
            'content': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 8,
                'placeholder': 'Enter news content'
            }),
        }
        help_texts = {
            'content': 'To update news content text please follow formatting guidance at <a href="https://operations.access-ci.org/operational-status-communications" target="_blank">Operational Status Communications</a>',
        }


class SystemStatusNewsForm(forms.ModelForm):
    """Form for creating and updating System and Infrastructure Status News"""
    
    start_datetime = forms.DateTimeField(
        required=True,
        label='Start Date and Time',
        widget=forms.DateTimeInput(attrs={
            'class': 'form-control',
            'type': 'datetime-local'
        }),
        help_text='When the infrastructure outage or reconfiguration starts (in your local timezone)'
    )
    
    end_datetime = forms.DateTimeField(
        required=False,
        label='End Date and Time',
        widget=forms.DateTimeInput(attrs={
            'class': 'form-control',
            'type': 'datetime-local'
        }),
        help_text='When this outage or configuration change ends. May be left blank for permanent configuration changes.'
    )
    
    class Meta:
        model = SystemStatusNews
        fields = [
            'subject', 
            'content', 
            'infrastructure_news_type',
            'affected_infrastructure',
            'start_datetime',
            'end_datetime',
            'send_email',
            'email_list',
            'post_to_slack',
            'slack_channel',
            'is_active'
        ]
        labels = {
            'subject': 'Subject',
            'content': 'News Content',
            'infrastructure_news_type': 'Infrastructure News Type',
            'affected_infrastructure': 'Affected Infrastructure',
            'is_active': 'Active',
            'send_email': 'Send Email Notification',
            'email_list': 'Email Recipients',
            'post_to_slack': 'Post to Slack',
            'slack_channel': 'Slack Channel'
        }
        widgets = {
            'subject': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Enter news subject'
            }),
            'content': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 8,
                'placeholder': 'Enter news content'
            }),
            'infrastructure_news_type': forms.Select(attrs={
                'class': 'form-select'
            }),
            'affected_infrastructure': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Enter resource ID(s) from CIDER (comma-separated if multiple)'
            }),
            'email_list': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'email1@example.com, email2@example.com'
            }),
            'slack_channel': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': '#channel-name'
            }),
        }
        help_texts = {
            'content': 'To update news content text please follow formatting guidance at <a href="https://operations.access-ci.org/operational-status-communications" target="_blank">Operational Status Communications</a>',
            'affected_infrastructure': 'Resource ID(s) from CIDER database (comma-separated if multiple)',
            'email_list': 'Comma-separated email addresses for notifications',
            'slack_channel': 'Slack channel name (e.g., #operations-alerts)'
        }
