from django import forms
from .models import IntegrationElement, IntegrationNews


class DateInput(forms.DateInput):
    input_type = 'date'


class IntegrationNewsForm(forms.ModelForm):
    INTEGRATION_NEWS_TYPES = [
        ('software_release', 'Software Release'),
        ('new_roadmap', 'New Integration Roadmap'),
        ('changed_roadmap', 'Changed Integration Roadmap'),
        ('new_roadmap_task', 'New Integration Roadmap Task'),
        ('changed_roadmap_task', 'Changed Integration Roadmap Task'),
    ]

    news_type = forms.ChoiceField(
        choices=INTEGRATION_NEWS_TYPES,
        required=True,
        label='Integration News Type',
        widget=forms.Select(attrs={'class': 'form-select'}),
    )
    affected_elements = forms.ModelMultipleChoiceField(
        queryset=IntegrationElement.objects.none(),
        required=False,
        label='Affected Elements',
        widget=forms.SelectMultiple(attrs={'class': 'form-select', 'size': 8}),
        help_text='Select one or more affected integration elements. Leave blank for broad announcements.',
    )
    effective_date = forms.DateField(
        required=True,
        label='Effective Date',
        widget=DateInput(attrs={'class': 'form-control'}),
        help_text='Date when this news becomes effective',
    )
    expiration_date = forms.DateField(
        required=False,
        label='Expiration Date',
        widget=DateInput(attrs={'class': 'form-control'}),
        help_text='Date when this news expires (optional)',
    )
    email_notification = forms.BooleanField(
        required=False, initial=False, label='Email everyone',
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        help_text='Not yet implemented',
    )
    slack_notification = forms.BooleanField(
        required=False, initial=False, label='Post to Slack',
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        help_text='Not yet implemented',
    )

    class Meta:
        model = IntegrationNews
        fields = ['title', 'content']
        labels = {'title': 'Subject', 'content': 'News Content'}
        widgets = {
            'title': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Enter news subject'}),
            'content': forms.Textarea(attrs={'class': 'form-control', 'rows': 8, 'placeholder': 'Enter news content'}),
        }
        help_texts = {
            'content': 'To update news content text please follow formatting guidance at <a href="https://operations.access-ci.org/operational-status-communications" target="_blank">Operational Status Communications</a>',
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['affected_elements'].queryset = IntegrationElement.objects.order_by('label')
        if self.instance.pk:
            self.fields['affected_elements'].initial = self.instance.affected_elements.all()

    def save_related_fields(self, news):
        affected_elements = list(self.cleaned_data.get('affected_elements', []))
        news.affected_elements.set(affected_elements)
        news.affected_element = affected_elements[0].code if len(affected_elements) == 1 else ''
        news.save(update_fields=['affected_element'])
