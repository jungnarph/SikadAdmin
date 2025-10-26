"""
Rides Views - For listing and viewing ride details
"""

from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from .models import Ride

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