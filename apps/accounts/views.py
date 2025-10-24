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
from django.utils import timezone
from datetime import timedelta
from .forms import (
    AdminLoginForm, AdminProfileForm, PasswordResetRequestForm,
    MfaVerifyForm, MfaEnableDisableForm # Added MFA forms
)
from .utils import send_mfa_email # Added MFA email utility
from .models import AdminUser


def admin_login(request):
    """
    Admin login view
    Handles standard login and redirects to MFA verification if enabled.
    """
    if request.user.is_authenticated:
        return redirect('dashboard')

    if request.method == 'POST':
        form = AdminLoginForm(request, data=request.POST)
        if form.is_valid():
            username = form.cleaned_data.get('username')
            password = form.cleaned_data.get('password')
            # Authenticate the user first regardless of MFA status
            user = authenticate(username=username, password=password)

            if user is not None:
                # --- MFA Check ---
                if user.is_mfa_enabled:
                    # MFA is enabled, generate code, send email, redirect to verify view
                    mfa_code = user.generate_mfa_code()
                    if send_mfa_email(user, mfa_code):
                        # Store user's PK in session to know who is verifying
                        request.session['mfa_user_id'] = str(user.pk)
                        # Store timestamp to prevent replay/timeout
                        request.session['mfa_login_attempt'] = timezone.now().isoformat()
                        messages.info(request, f'Verification needed. A code has been sent to {user.email}.')
                        # Redirect to the MFA verification page
                        return redirect('accounts:mfa_verify')
                    else:
                        # Email failed to send
                        messages.error(request, 'Failed to send verification code email. Please check configuration or contact support.')
                        # Don't log the user in, show login page again
                        return render(request, 'accounts/login.html', {'form': form})
                else:
                    # --- No MFA, login directly ---
                    login(request, user)
                    messages.success(request, f'Welcome back, {user.first_name or user.username}!')
                    next_url = request.GET.get('next', 'dashboard')
                    return redirect(next_url)
            else:
                # Authentication failed (username/password)
                messages.error(request, 'Invalid username or password.')
        else:
            # Form validation failed
            messages.error(request, 'Invalid username or password.') # Keep generic for security
    else:
        # GET request
        form = AdminLoginForm()

    return render(request, 'accounts/login.html', {'form': form})

# --- New View for MFA Verification ---
def mfa_verify(request):
    """Handles the submission and verification of the MFA code."""
    mfa_user_id = request.session.get('mfa_user_id')
    mfa_login_attempt_str = request.session.get('mfa_login_attempt')

    # Basic validation: Check if MFA process was started
    if not mfa_user_id or not mfa_login_attempt_str:
        messages.error(request, 'Verification session not found or expired. Please log in again.')
        return redirect('accounts:login')

    # Check for attempt timeout (e.g., code expiry + buffer or fixed time)
    try:
        mfa_login_attempt = timezone.datetime.fromisoformat(mfa_login_attempt_str)
        # Allow, for example, 6 minutes total for the verification page
        if timezone.now() > mfa_login_attempt + timedelta(minutes=6):
             messages.error(request, 'Verification time limit exceeded. Please log in again.')
             request.session.pop('mfa_user_id', None)
             request.session.pop('mfa_login_attempt', None)
             return redirect('accounts:login')
    except ValueError:
         messages.error(request, 'Invalid verification session data. Please log in again.')
         request.session.pop('mfa_user_id', None)
         request.session.pop('mfa_login_attempt', None)
         return redirect('accounts:login')

    try:
        # Retrieve the user attempting to log in
        user = AdminUser.objects.get(pk=mfa_user_id)
    except AdminUser.DoesNotExist:
        messages.error(request, 'User associated with verification not found. Please log in again.')
        request.session.pop('mfa_user_id', None)
        request.session.pop('mfa_login_attempt', None)
        return redirect('accounts:login')

    if request.method == 'POST':
        form = MfaVerifyForm(request.POST)
        if form.is_valid():
            code = form.cleaned_data['code']
            # Use the method on the user model to verify
            if user.verify_mfa_code(code):
                # --- Code is valid, complete the login ---
                # Need to log the user in properly AFTER MFA verification
                # Since authenticate() was already done, we just call login()
                user.backend = 'django.contrib.auth.backends.ModelBackend' # Needed for login()
                login(request, user)

                # Clear MFA session variables
                request.session.pop('mfa_user_id', None)
                request.session.pop('mfa_login_attempt', None)

                messages.success(request, f'Verification successful. Welcome back, {user.first_name or user.username}!')
                next_url = request.GET.get('next', 'dashboard')
                return redirect(next_url)
            else:
                # Code was invalid or expired
                messages.error(request, 'Invalid or expired verification code. Please try again.')
                # Keep session variables, allow retry
    else:
        # GET request, show the form
        form = MfaVerifyForm()

    # Pass user's email to template for context
    return render(request, 'accounts/mfa_verify.html', {'form': form, 'user_email': user.email})

@login_required
def admin_logout(request):
    """Admin logout view"""
    user_name = request.user.first_name or request.user.username
    logout(request)
    messages.success(request, f'Goodbye, {user_name}! You have been logged out.')
    return redirect('accounts:login')


@login_required
def profile(request):
    """Admin profile view and edit, now includes MFA enable/disable."""
    user = request.user
    if request.method == 'POST':
        # Instantiate both forms with POST data
        profile_form = AdminProfileForm(request.POST, instance=user)
        mfa_form = MfaEnableDisableForm(request.POST)

        # Use button names to determine which form was submitted
        if 'update_profile' in request.POST:
            if profile_form.is_valid():
                profile_form.save()
                messages.success(request, 'Your profile information has been updated.')
                return redirect('accounts:profile')
            else:
                 messages.error(request, 'Please correct the errors in the profile information.')
                 # Re-render with profile errors, reset MFA form
                 mfa_form = MfaEnableDisableForm(initial={'enable_mfa': user.is_mfa_enabled})

        elif 'update_mfa' in request.POST:
             # Validate the MFA form specifically
             # Note: It might seem simple, but good practice for future extension
             if mfa_form.is_valid():
                 enable_mfa = mfa_form.cleaned_data['enable_mfa']

                 # Crucial check: User must have an email to enable MFA
                 if enable_mfa and not user.email:
                     messages.error(request, "Cannot enable MFA. Please set and verify your email address first.")
                     # Reset profile form state
                     profile_form = AdminProfileForm(instance=user)
                 else:
                     user.is_mfa_enabled = enable_mfa
                     user.save(update_fields=['is_mfa_enabled'])
                     if enable_mfa:
                         messages.success(request, 'Multi-Factor Authentication via email has been ENABLED.')
                     else:
                         messages.success(request, 'Multi-Factor Authentication has been DISABLED.')
                     # Redirect after successful MFA update
                     return redirect('accounts:profile')
             else:
                  # This case is less likely for a single checkbox but included for completeness
                  messages.error(request, 'Error updating MFA setting.')
                  profile_form = AdminProfileForm(instance=user) # Reset profile form


    else: # GET request
        profile_form = AdminProfileForm(instance=user)
        mfa_form = MfaEnableDisableForm(initial={'enable_mfa': user.is_mfa_enabled})

    context = {
        'profile_form': profile_form, # Pass profile form
        'mfa_form': mfa_form,       # Pass MFA form
        'user': user,
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
