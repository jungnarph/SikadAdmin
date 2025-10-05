"""
Dashboard Views
"""

from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from apps.bikes.models import Bike
from apps.geofencing.models import Zone
from django.utils import timezone


@login_required
def dashboard(request):
    """Main dashboard view"""
    
    # Bike statistics
    total_bikes = Bike.objects.count()
    available_bikes = Bike.objects.filter(status='AVAILABLE').count()
    in_use_bikes = Bike.objects.filter(status='IN_USE').count()
    offline_bikes = Bike.objects.filter(status='OFFLINE').count()
    
    # Calculate percentages
    if total_bikes > 0:
        available_percentage = round((available_bikes / total_bikes) * 100, 1)
        in_use_percentage = round((in_use_bikes / total_bikes) * 100, 1)
        offline_percentage = round((offline_bikes / total_bikes) * 100, 1)
    else:
        available_percentage = 0
        in_use_percentage = 0
        offline_percentage = 0
    
    # Zone statistics
    total_zones = Zone.objects.count()
    active_zones = Zone.objects.filter(is_active=True)[:5]
    
    # Recent bikes
    recent_bikes = Bike.objects.all().order_by('-created_at')[:5]
    
    # Last sync time
    last_bike = Bike.objects.order_by('-synced_at').first()
    last_sync = last_bike.synced_at if last_bike else timezone.now()
    
    # Active rentals (placeholder - will be implemented with rentals app)
    active_rentals = in_use_bikes  # For now, same as in_use bikes
    
    context = {
        'total_bikes': total_bikes,
        'available_bikes': available_bikes,
        'in_use_bikes': in_use_bikes,
        'offline_bikes': offline_bikes,
        'available_percentage': available_percentage,
        'in_use_percentage': in_use_percentage,
        'offline_percentage': offline_percentage,
        'total_zones': total_zones,
        'active_zones': active_zones,
        'recent_bikes': recent_bikes,
        'active_rentals': active_rentals,
        'last_sync': last_sync,
    }
    
    return render(request, 'dashboard/dashboard.html', context)