# apps/accounts/decorators.py

from functools import wraps
from django.shortcuts import redirect
from django.contrib import messages
from django.urls import reverse

def role_required(allowed_roles=[]):
    """
    Decorator for views that checks if user's role is in allowed_roles.
    Redirects to dashboard with an error message if not allowed.
    Assumes user is already authenticated (@login_required should be used first).
    """
    def decorator(view_func):
        @wraps(view_func)
        def _wrapped_view(request, *args, **kwargs):
            if not request.user.is_authenticated:
                # Should be handled by @login_required, but as a safeguard
                return redirect('accounts:login')

            if request.user.role not in allowed_roles:
                messages.error(request, "You do not have permission to access this page.")
                # Redirect to a safe page, like the dashboard
                return redirect(reverse('dashboard'))
            return view_func(request, *args, **kwargs)
        return _wrapped_view
    return decorator

# Specific role decorators for convenience
super_admin_required = role_required(['SUPER_ADMIN'])
staff_or_super_admin_required = role_required(['SUPER_ADMIN', 'STAFF_ADMIN'])
support_or_higher_required = role_required(['SUPER_ADMIN', 'STAFF_ADMIN', 'SUPPORT']) # If support needs more than just support app access

def is_super_admin(user):
    return user.is_authenticated and user.role == 'SUPER_ADMIN'

def is_staff_or_super_admin(user):
    return user.is_authenticated and (user.role == 'SUPER_ADMIN' or user.role == 'STAFF_ADMIN')

def is_support_or_higher(user):
     return user.is_authenticated and (user.role == 'SUPER_ADMIN' or user.role == 'STAFF_ADMIN' or user.role == 'SUPPORT')