"""
Customer Forms
"""

from django import forms


class CustomerEditForm(forms.Form):
    """Form for editing customer information"""
    
    full_name = forms.CharField(
        max_length=255,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Full Name'
        })
    )
    
    email = forms.EmailField(
        max_length=255,
        required=False,
        widget=forms.EmailInput(attrs={
            'class': 'form-control',
            'placeholder': 'email@example.com'
        })
    )
    
    phone_number = forms.CharField(
        max_length=20,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': '+63 XXX XXX XXXX'
        })
    )


class CustomerSuspendForm(forms.Form):
    """Form for suspending a customer account"""
    
    REASON_CHOICES = [
        ('', 'Select a reason...'),
        ('VIOLATION', 'Policy Violation'),
        ('FRAUD', 'Fraudulent Activity'),
        ('PAYMENT_ISSUE', 'Payment Issues'),
        ('ABUSE', 'System Abuse'),
        ('SAFETY', 'Safety Concerns'),
        ('OTHER', 'Other Reason'),
    ]
    
    reason_category = forms.ChoiceField(
        choices=REASON_CHOICES,
        required=True,
        widget=forms.Select(attrs={
            'class': 'form-select'
        }),
        label='Suspension Reason'
    )
    
    reason = forms.CharField(
        required=True,
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 4,
            'placeholder': 'Provide detailed explanation for the suspension...'
        }),
        label='Detailed Explanation'
    )
    
    notify_customer = forms.BooleanField(
        required=False,
        initial=True,
        widget=forms.CheckboxInput(attrs={
            'class': 'form-check-input'
        }),
        label='Send notification to customer'
    )


class CustomerNoteForm(forms.Form):
    """Form for adding admin notes to customer"""
    
    note = forms.CharField(
        required=True,
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 3,
            'placeholder': 'Add internal note about this customer...'
        }),
        label='Admin Note'
    )


class CustomerFilterForm(forms.Form):
    """Form for filtering customers"""
    
    STATUS_CHOICES = [
        ('', 'All Status'),
        ('ACTIVE', 'Active'),
        ('SUSPENDED', 'Suspended'),
        ('BANNED', 'Banned'),
        ('PENDING', 'Pending'),
    ]
    
    VERIFICATION_CHOICES = [
        ('', 'All Verification Status'),
        ('UNVERIFIED', 'Unverified'),
        ('PENDING', 'Pending'),
        ('VERIFIED', 'Verified'),
        ('REJECTED', 'Rejected'),
    ]
    
    status = forms.ChoiceField(
        choices=STATUS_CHOICES,
        required=False,
        widget=forms.Select(attrs={
            'class': 'form-select'
        })
    )
    
    verification = forms.ChoiceField(
        choices=VERIFICATION_CHOICES,
        required=False,
        widget=forms.Select(attrs={
            'class': 'form-select'
        })
    )
    
    search = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Search by name, email, or phone...'
        })
    )