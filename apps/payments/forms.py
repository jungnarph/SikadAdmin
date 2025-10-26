"""
Forms for the Payments app
"""

from django import forms
from .models import Payment # Import the model to get choices

class PaymentFilterForm(forms.Form):
    """Form for filtering the payments list."""

    # Get choices directly from the model to stay consistent
    PAYMENT_STATUS_CHOICES = [('', 'All Statuses')] + Payment.PAYMENT_STATUS_CHOICES
    PAYMENT_TYPE_CHOICES = [('', 'All Types')] + Payment.PAYMENT_TYPE_CHOICES

    payment_status = forms.ChoiceField(
        choices=PAYMENT_STATUS_CHOICES,
        required=False,
        widget=forms.Select(attrs={'class': 'form-select form-select-sm'})
    )

    payment_type = forms.ChoiceField(
        choices=PAYMENT_TYPE_CHOICES,
        required=False,
        widget=forms.Select(attrs={'class': 'form-select form-select-sm'})
    )

    date_from = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={'class': 'form-control form-control-sm', 'type': 'date'}),
        label="Date From"
    )

    date_to = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={'class': 'form-control form-control-sm', 'type': 'date'}),
        label="Date To"
    )

    search = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control form-control-sm',
            'placeholder': 'Search ID, Customer, Ride, Ref...'
        }),
        label="Search"
    )
