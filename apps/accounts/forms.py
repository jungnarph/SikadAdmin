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
