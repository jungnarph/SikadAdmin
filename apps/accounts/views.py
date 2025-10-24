"""
Accounts Views
Admin authentication and profile management
"""

from django.shortcuts import render, redirect
from django.contrib.auth import login, authenticate, logout, update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.contrib.auth.forms import PasswordChangeForm, SetPasswordForm
from django.contrib.auth.tokens import default_token_generator
from django.utils.http import urlsafe_base64_encode, urlsafe_base64_decode
from django.utils.encoding import force_bytes, force_str
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.conf import settings
from .forms import AdminLoginForm, AdminProfileForm, PasswordResetRequestForm
from .models import AdminUser


def admin_login(request):
    """
    Admin login view
    Only for existing admin users - no signup allowed
    """
    if request.user.is_authenticated:
        return redirect('dashboard')
    
    if request.method == 'POST':
        form = AdminLoginForm(request, data=request.POST)
        if form.is_valid():
            username = form.cleaned_data.get('username')
            password = form.cleaned_data.get('password')
            user = authenticate(username=username, password=password)
            
            if user is not None:
                login(request, user)
                messages.success(request, f'Welcome back, {user.first_name or user.username}!')
                
                # Redirect to next parameter or dashboard
                next_url = request.GET.get('next', 'dashboard')
                return redirect(next_url)
            else:
                messages.error(request, 'Invalid username or password.')
        else:
            messages.error(request, 'Invalid username or password.')
    else:
        form = AdminLoginForm()
    
    return render(request, 'accounts/login.html', {'form': form})


@login_required
def admin_logout(request):
    """Admin logout view"""
    user_name = request.user.first_name or request.user.username
    logout(request)
    messages.success(request, f'Goodbye, {user_name}! You have been logged out.')
    return redirect('accounts:login')


@login_required
def profile(request):
    """Admin profile view and edit"""
    if request.method == 'POST':
        form = AdminProfileForm(request.POST, instance=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, 'Your profile has been updated successfully!')
            return redirect('accounts:profile')
    else:
        form = AdminProfileForm(instance=request.user)
    
    context = {
        'form': form,
        'user': request.user,
    }
    return render(request, 'accounts/profile.html', context)


@login_required
def change_password(request):
    """Change password view"""
    if request.method == 'POST':
        form = PasswordChangeForm(request.user, request.POST)
        if form.is_valid():
            user = form.save()
            update_session_auth_hash(request, user)  # Keep user logged in
            messages.success(request, 'Your password has been changed successfully!')
            return redirect('accounts:profile')
        else:
            messages.error(request, 'Please correct the errors below.')
    else:
        form = PasswordChangeForm(request.user)
    
    context = {'form': form}
    return render(request, 'accounts/change_password.html', context)


# ==================== PASSWORD RESET FLOW ====================

def password_reset_request(request):
    """
    Step 1: User enters their email to request password reset
    """
    if request.user.is_authenticated:
        return redirect('dashboard')
    
    if request.method == 'POST':
        form = PasswordResetRequestForm(request.POST)
        if form.is_valid():
            email = form.cleaned_data['email']
            
            # Check if user with this email exists
            users = AdminUser.objects.filter(email=email, is_active=True)
            
            if users.exists():
                user = users.first()
                
                # Generate password reset token
                token = default_token_generator.make_token(user)
                uid = urlsafe_base64_encode(force_bytes(user.pk))
                
                # Build reset URL
                reset_url = request.build_absolute_uri(
                    f'/accounts/password-reset/{uid}/{token}/'
                )
                
                # Prepare email context
                context = {
                    'user': user,
                    'reset_url': reset_url,
                    'site_name': 'Sikad Bike Sharing Admin',
                }
                
                # Render email templates
                subject = 'Password Reset Request - Sikad Admin'
                html_message = render_to_string('accounts/emails/password_reset_email.html', context)
                plain_message = render_to_string('accounts/emails/password_reset_email.txt', context)
                
                # Send email
                try:
                    send_mail(
                        subject=subject,
                        message=plain_message,
                        from_email=settings.DEFAULT_FROM_EMAIL,
                        recipient_list=[email],
                        html_message=html_message,
                        fail_silently=False,
                    )
                except Exception as e:
                    # Log the error but don't reveal to user
                    print(f"Error sending password reset email: {e}")
            
            # Always redirect to "sent" page for security
            # (Don't reveal if email exists or not)
            return redirect('accounts:password_reset_sent')
    else:
        form = PasswordResetRequestForm()
    
    return render(request, 'accounts/password_reset_request.html', {'form': form})


def password_reset_sent(request):
    """
    Step 2: Show confirmation that email was sent
    """
    return render(request, 'accounts/password_reset_sent.html')


def password_reset_confirm(request, uidb64, token):
    """
    Step 3: User clicks link from email and enters new password
    """
    if request.user.is_authenticated:
        return redirect('dashboard')
    
    try:
        # Decode user ID
        uid = force_str(urlsafe_base64_decode(uidb64))
        user = AdminUser.objects.get(pk=uid)
    except (TypeError, ValueError, OverflowError, AdminUser.DoesNotExist):
        user = None
    
    # Validate token
    if user is not None and default_token_generator.check_token(user, token):
        if request.method == 'POST':
            form = SetPasswordForm(user, request.POST)
            if form.is_valid():
                form.save()
                messages.success(request, 'Your password has been reset successfully! You can now log in.')
                return redirect('accounts:password_reset_complete')
        else:
            form = SetPasswordForm(user)
        
        context = {
            'form': form,
            'validlink': True,
        }
        return render(request, 'accounts/password_reset_confirm.html', context)
    else:
        # Invalid or expired token
        context = {
            'validlink': False,
        }
        return render(request, 'accounts/password_reset_confirm.html', context)


def password_reset_complete(request):
    """
    Step 4: Show success message and redirect to login
    """
    return render(request, 'accounts/password_reset_complete.html')
