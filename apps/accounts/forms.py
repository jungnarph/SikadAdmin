"""
Accounts Forms
"""

from django import forms
from django.contrib.auth.forms import AuthenticationForm
from .models import AdminUser


class AdminLoginForm(AuthenticationForm):
    """Custom login form for admin users"""
    username = forms.CharField(
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Username',
            'autofocus': True
        })
    )
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'Password'
        })
    )


class AdminProfileForm(forms.ModelForm):
    """Form for editing admin profile"""
    
    class Meta:
        model = AdminUser
        fields = ['first_name', 'last_name', 'email', 'phone_number']
        widgets = {
            'first_name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'First Name'
            }),
            'last_name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Last Name'
            }),
            'email': forms.EmailInput(attrs={
                'class': 'form-control',
                'placeholder': 'email@example.com'
            }),
            'phone_number': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': '+63 XXX XXX XXXX'
            }),
        }


class PasswordResetRequestForm(forms.Form):
    """Form for requesting password reset"""
    email = forms.EmailField(
        label='Email Address',
        max_length=254,
        widget=forms.EmailInput(attrs={
            'class': 'form-control',
            'placeholder': 'Enter your email address',
            'autofocus': True
        }),
        help_text='Enter the email address associated with your account.'
    )


class MfaVerifyForm(forms.Form):
    """Form for verifying the MFA code entered by the user."""
    code = forms.CharField(
        max_length=6,
        min_length=6,
        widget=forms.TextInput(attrs={
            'class': 'form-control form-control-lg text-center', # Style for emphasis
            'placeholder': 'Enter 6-digit code',
            'autofocus': True,
            'inputmode': 'numeric', # Hint for numeric keyboard on mobile
            'pattern': '[0-9]*',    # Basic pattern validation
        }),
        label="Verification Code",
        help_text="Enter the 6-digit code sent to your email."
    )

    def clean_code(self):
        """Ensure the code contains only digits."""
        code = self.cleaned_data.get('code')
        if code and not code.isdigit():
            raise forms.ValidationError("Verification code must contain only digits.")
        return code

class MfaEnableDisableForm(forms.Form):
    """Simple form used on the profile page to toggle MFA status."""
    enable_mfa = forms.BooleanField(
        required=False, # Allows unchecking to disable
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        label="Enable Multi-Factor Authentication via Email"
    )