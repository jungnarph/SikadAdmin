"""
Support Views - For listing and viewing support request details
"""

from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.contrib import messages

from apps.accounts.decorators import support_or_higher_required, super_admin_required

from .models import SupportRequest


@login_required
@support_or_higher_required
def support_request_list(request):
    """Displays a list of all support requests."""
    support_requests_queryset = SupportRequest.objects.select_related('customer').order_by('-timestamp')

    # Add filtering based on request.GET parameters
    status_filter = request.GET.get('status')
    priority_filter = request.GET.get('priority')

    if status_filter:
        support_requests_queryset = support_requests_queryset.filter(status=status_filter)
    if priority_filter:
        support_requests_queryset = support_requests_queryset.filter(priority=priority_filter)

    paginator = Paginator(support_requests_queryset, 25)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    context = {
        'support_requests': page_obj,
        'status_choices': SupportRequest.STATUS_CHOICES,
        'priority_choices': SupportRequest.PRIORITY_CHOICES,
        'current_status': status_filter,
        'current_priority': priority_filter,
    }
    return render(request, 'support/support_request_list.html', context)


@login_required
@support_or_higher_required
def support_request_detail(request, request_firebase_id):
    """Displays details for a single support request."""
    support_request = get_object_or_404(
        SupportRequest.objects.select_related('customer'),
        firebase_id=request_firebase_id
    )
    context = {'support_request': support_request}
    return render(request, 'support/support_request_detail.html', context)


@login_required
@super_admin_required
def sync_support_requests(request):
    """Sync all support requests from Firebase to PostgreSQL"""
    try:
        from .sync_service import SupportSyncService
        sync_service = SupportSyncService()
        stats = sync_service.sync_all_support_requests()

        messages.success(
            request,
            f'Synced {stats["total"]} support requests: {stats["created"]} created, {stats["updated"]} updated'
        )
    except Exception as e:
        messages.error(request, f'Error syncing support requests: {str(e)}')

    return redirect('support:support_request_list')