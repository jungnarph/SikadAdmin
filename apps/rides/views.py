"""
Rides Views - For listing and viewing ride details
"""

from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.contrib import messages
from django.db.models import Q
from django.db.models import Max
from apps.accounts.decorators import super_admin_required

from apps.rides.sync_service import RideSyncService
from .models import Ride
import logging

logger = logging.getLogger(__name__)

@login_required
def ride_list(request):
    """Displays a list of all rides."""
    rides_queryset = Ride.objects.select_related('customer', 'bike').order_by('-start_time')

    # Add Filtering based on request.GET parameters (e.g., status, customer, bike)
    # ...

    paginator = Paginator(rides_queryset, 25)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    context = {
        'rides': page_obj,
        # Add filter form context later
    }
    return render(request, 'rides/ride_list.html', context) # Assumes template exists

@login_required
def ride_detail(request, ride_firebase_id):
    """Displays details for a single ride."""
    ride = get_object_or_404(
        Ride.objects.select_related('customer', 'bike', 'payment_record'),
        firebase_id=ride_firebase_id
    )
    context = {'ride': ride}
    return render(request, 'rides/ride_detail.html', context) # Assumes template exists

@login_required
@super_admin_required
def sync_all_rides(request):
    """
    Triggers a QUICK, BATCHED sync from the web.
    
    This is a "failsafe" sync that only processes a small batch
    of the oldest unsynced rides to prevent a web timeout.
    """
    
    # Define a safe batch size that won't time out
    QUICK_SYNC_BATCH_SIZE = 100 
    
    try:
        # 1. Find the start_time of the most recent ride we have in our database.
        # This is the user's "failsafe" logic.
        latest_ride = Ride.objects.order_by('-start_time').first()
        start_after = latest_ride.start_time if latest_ride else None

        if start_after:
            logger.info(f"Quick Sync: Found last sync point at {start_after}")
        else:
            logger.info("Quick Sync: No rides found, syncing from beginning.")

        # 2. Call the sync service, but only for a small, safe batch
        sync_service = RideSyncService()
        stats = sync_service.sync_all_rides(
            limit=QUICK_SYNC_BATCH_SIZE,
            start_after_timestamp=start_after,
            order_by='startTime',
            direction='ASCENDING' # Sync oldest-to-newest
        )
        
        created = stats.get("created", 0)
        updated = stats.get("updated", 0)
        
        if created > 0 or updated > 0:
            messages.success(
                request,
                f'✓ Quick sync complete: {created} new rides created, {updated} rides updated.'
            )
        elif stats.get('total', 0) == 0 and start_after:
             messages.info(
                request,
                'Your database is already up-to-date. No new rides found.'
            )
        else:
             messages.warning(
                request,
                f'Sync ran but no changes were made. Failed: {stats.get("failed", 0)}.'
            )

    except Exception as e:
        logger.error(f"Error during quick sync view: {e}", exc_info=True)
        messages.error(request, f"An error occurred: {e}")
    
    return redirect('rides:ride_list')