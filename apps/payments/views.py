"""
Payments Views
Handles listing and viewing payment details.
"""

from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Q
from .models import Payment
from .forms import PaymentFilterForm
from .sync_service import PaymentSyncService

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
def sync_all_payments(request):
    """
    Triggers the sync process for all payments from Firebase.
    Redirects back to the payment list with a status message.
    """
    sync_service = PaymentSyncService()
    stats = sync_service.sync_all_payments() # Assuming a limit or fetching all

    messages.success(
        request,
        f'Sync initiated. Attempted to sync {stats.get("total", 0)} payments: '
        f'{stats.get("created", 0)} created/updated, {stats.get("failed", 0)} failed. '
        f'Check logs for details.'
    )

    return redirect('payments:payment_list')

# Note: A payment_detail view might not be strictly necessary if all relevant info
# is in the list and linked models (Customer, Ride), but could be added if needed.

# Example placeholder for a detail view if desired later:
# @login_required
# def payment_detail(request, payment_firebase_id):
#     payment = get_object_or_404(Payment.objects.select_related('customer', 'ride'), firebase_id=payment_firebase_id)
#     context = {'payment': payment}
#     return render(request, 'payments/payment_detail.html', context)
