"""
Bikes Views
"""

from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from .models import Bike
from .firebase_service import BikeFirebaseService
from .sync_service import BikeSyncService
import json


@login_required
def bike_list(request):
    """List all bikes from PostgreSQL"""
    bikes = Bike.objects.all().order_by('-created_at')
    
    # Apply filters
    status = request.GET.get('status')
    bike_type = request.GET.get('bike_type')
    search = request.GET.get('search')
    
    if status:
        bikes = bikes.filter(status=status)
    if bike_type:
        bikes = bikes.filter(bike_type=bike_type)
    if search:
        bikes = bikes.filter(
            firebase_id__icontains=search
        ) | bikes.filter(
            bike_model__icontains=search
        )
    
    context = {
        'bikes': bikes,
        'total_count': Bike.objects.count(),
        'available_count': Bike.objects.filter(status='AVAILABLE').count(),
        'in_use_count': Bike.objects.filter(status='IN_USE').count(),
        'maintenance_count': Bike.objects.filter(status='MAINTENANCE').count(),
    }
    
    return render(request, 'bikes/bike_list.html', context)


@login_required
def bike_detail(request, bike_id):
    """View bike details from Firebase"""
    firebase_service = BikeFirebaseService()
    bike_data = firebase_service.get_bike(bike_id)
    
    if not bike_data:
        messages.error(request, f'Bike {bike_id} not found in Firebase')
        return redirect('bikes:bike_list')
    
    # Get location history
    location_history = firebase_service.get_location_history(bike_id, limit=50)
    
    # Get PostgreSQL data if exists
    try:
        pg_bike = Bike.objects.get(firebase_id=bike_id)
    except Bike.DoesNotExist:
        pg_bike = None
    
    context = {
        'bike': bike_data,
        'pg_bike': pg_bike,
        'location_history': location_history,
    }
    
    return render(request, 'bikes/bike_detail.html', context)


@login_required
def bike_map(request):
    """Display live map of all bikes"""
    bikes = Bike.objects.filter(
        current_latitude__isnull=False,
        current_longitude__isnull=False
    )
    
    # Prepare bike data for JavaScript
    bikes_data = []
    for bike in bikes:
        bikes_data.append({
            'bike_id': bike.firebase_id,
            'bike_model': bike.bike_model,
            'bike_type': bike.get_bike_type_display(),
            'status': bike.status,
            'latitude': float(bike.current_latitude),
            'longitude': float(bike.current_longitude),
        })
    
    context = {
        'bikes_json': json.dumps(bikes_data),
    }
    
    return render(request, 'bikes/bike_map.html', context)


@login_required
def sync_bike(request, bike_id):
    """Sync a single bike from Firebase to PostgreSQL"""
    sync_service = BikeSyncService()
    success = sync_service.sync_single_bike(bike_id)
    
    if success:
        messages.success(request, f'Bike {bike_id} synced successfully')
    else:
        messages.error(request, f'Failed to sync bike {bike_id}')
    
    return redirect('bikes:bike_detail', bike_id=bike_id)


@login_required
def sync_all_bikes(request):
    """Sync all bikes from Firebase to PostgreSQL"""
    sync_service = BikeSyncService()
    stats = sync_service.sync_all_bikes()
    
    messages.success(
        request, 
        f'Synced {stats["total"]} bikes: {stats["created"]} created, {stats["updated"]} updated'
    )
    
    return redirect('bikes:bike_list')