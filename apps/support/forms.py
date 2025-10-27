"""
Support Forms
"""

from django import forms
from .models import SupportRequest


class SupportRequestForm(forms.ModelForm):
    """Form for creating/editing support requests"""

    class Meta:
        model = SupportRequest
        fields = ['status', 'priority', 'assigned_to', 'response']
        widgets = {
            'status': forms.Select(attrs={'class': 'form-control'}),
            'priority': forms.Select(attrs={'class': 'form-control'}),
            'assigned_to': forms.TextInput(attrs={'class': 'form-control'}),
            'response': forms.Textarea(attrs={'class': 'form-control', 'rows': 4}),
        }


class SupportRequestFilterForm(forms.Form):
    """Form for filtering support requests"""

    status = forms.ChoiceField(
        choices=[('', 'All Statuses')] + list(SupportRequest.STATUS_CHOICES),
        required=False,
        widget=forms.Select(attrs={'class': 'form-control'})
    )

    priority = forms.ChoiceField(
        choices=[('', 'All Priorities')] + list(SupportRequest.PRIORITY_CHOICES),
        required=False,
        widget=forms.Select(attrs={'class': 'form-control'})
    )