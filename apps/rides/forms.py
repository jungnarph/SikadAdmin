"""
Forms for the Rides app (e.g., filtering)
"""

from django import forms
from .models import Ride

class RideFilterForm(forms.Form):
    """Form for filtering the rides list."""
    # Example filters - expand as needed
    rental_status = forms.ChoiceField(
        choices=[('', 'All Statuses')] + Ride.RENTAL_STATUS_CHOICES,
        required=False,
        widget=forms.Select(attrs={'class': 'form-select form-select-sm'})
    )
    payment_status = forms.ChoiceField(
        choices=[('', 'All Payment Statuses')] + Ride.PAYMENT_STATUS_CHOICES,
        required=False,
        widget=forms.Select(attrs={'class': 'form-select form-select-sm'})
    )
    search = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control form-control-sm',
            'placeholder': 'Search Ride ID, Cust ID, Bike ID...'
        }),
        label="Search"
    )
    # Add date filters if needed