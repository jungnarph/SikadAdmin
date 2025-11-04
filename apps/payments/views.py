"""
Payments Views
Handles listing and viewing payment details.
"""

from datetime import datetime
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Q
from .models import Payment
from .forms import PaymentFilterForm
from .sync_service import PaymentSyncService
from apps.accounts.decorators import super_admin_required
import logging
from django.db.models import Max

logger = logging.getLogger(__name__)

@login_required
def payment_list(request):
    """
    Displays a list of all payments, with filtering capabilities.
    """
    payments_queryset = Payment.objects.select_related('customer', 'ride').order_by('-payment_date')
    form = PaymentFilterForm(request.GET)

    # Apply filters if form is valid
    if form.is_valid():
        status = form.cleaned_data.get('payment_status')
        payment_type = form.cleaned_data.get('payment_type')
        date_from = form.cleaned_data.get('date_from')
        date_to = form.cleaned_data.get('date_to')
        search = form.cleaned_data.get('search')

        if status:
            payments_queryset = payments_queryset.filter(payment_status=status)
        if payment_type:
            payments_queryset = payments_queryset.filter(payment_type=payment_type)
        if date_from:
            payments_queryset = payments_queryset.filter(payment_date__gte=date_from)
        if date_to:
            # Add time component to include the whole day
            from datetime import timedelta, time
            date_to_end_of_day = datetime.combine(date_to, time.max)
            payments_queryset = payments_queryset.filter(payment_date__lte=date_to_end_of_day)
        if search:
            payments_queryset = payments_queryset.filter(
                Q(firebase_id__icontains=search) |
                Q(customer__name__icontains=search) |
                Q(customer__email__icontains=search) |
                Q(customer__firebase_id__icontains=search) |
                Q(ride__firebase_id__icontains=search) |
                Q(payment_account_info__icontains=search)
            )

    # Pagination
    paginator = Paginator(payments_queryset, 25) # Show 25 payments per page
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    context = {
        'payments': page_obj,
        'form': form,
        'total_payments': payments_queryset.count(),
    }
    return render(request, 'payments/payment_list.html', context)

@login_required
@super_admin_required
def sync_all_payments(request):
    """
    Triggers a QUICK, BATCHED sync from the web.
    
    This is a "failsafe" sync that only processes a small batch
    of the oldest unsynced payments to prevent a web timeout.
    """
    
    # Define a safe batch size that won't time out
    QUICK_SYNC_BATCH_SIZE = 30 
    
    try:
        # 1. Find the payment_date of the most recent payment we have.
        latest_payment = Payment.objects.order_by('-payment_date').first()
        start_after = latest_payment.payment_date if latest_payment else None

        if start_after:
            logger.info(f"Quick Sync: Found last payment sync point at {start_after}")
        else:
            logger.info("Quick Sync: No payments found, syncing from beginning.")

        # 2. Call the sync service for one small batch
        sync_service = PaymentSyncService()
        stats = sync_service.sync_all_payments(
            limit=QUICK_SYNC_BATCH_SIZE,
            start_after_timestamp=start_after,
            order_by='paymentDate', # Match Firebase field
            direction='ASCENDING'   # Sync oldest-to-newest
        )
        
        created = stats.get("created", 0)
        updated = stats.get("updated", 0)
        
        if created > 0 or updated > 0:
            messages.success(
                request,
                f'✓ Quick sync complete: {created} new payments created, {updated} payments updated.'
            )
        elif stats.get('total', 0) == 0 and start_after:
             messages.info(
                request,
                'Your database is already up-to-date. No new payments found.'
            )
        else:
             messages.warning(
                request,
                f'Sync ran but no changes were made. Failed: {stats.get("failed", 0)}.'
            )

    except Exception as e:
        logger.error(f"Error during quick sync view: {e}", exc_info=True)
        messages.error(request, f"An error occurred: {e}")
    
    return redirect('payments:payment_list')
