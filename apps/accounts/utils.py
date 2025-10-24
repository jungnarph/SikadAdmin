# apps/accounts/utils.py
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.conf import settings
import logging

logger = logging.getLogger(__name__)

def send_mfa_email(user, code):
    """Sends the MFA code via email using defined templates."""
    if not user.email:
        logger.warning(f"Attempted to send MFA code to user {user.username} with no email address.")
        return False

    context = {
        'user': user,
        'code': code,
        'site_name': 'Sikad Bike Sharing Admin', # Or pull from settings if needed
    }
    subject = f'Your Login Verification Code - {context["site_name"]}'

    try:
        # Render both HTML and plain text versions
        html_message = render_to_string('accounts/emails/mfa_code_email.html', context)
        plain_message = render_to_string('accounts/emails/mfa_code_email.txt', context)

        send_mail(
            subject=subject,
            message=plain_message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[user.email],
            html_message=html_message,
            fail_silently=False,
        )
        logger.info(f"MFA code sent successfully to {user.email}")
        return True
    except Exception as e:
        logger.error(f"Error sending MFA email to {user.email}: {e}", exc_info=True)
        return False