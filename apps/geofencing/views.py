"""
Geofencing Views
"""

from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from .models import Zone
from .firebase_service import GeofenceFirebaseService
from .sync_service import GeofenceSyncService


@login_required
def zone_list(request):
    """List all geofence zones from PostgreSQL"""
    zones = Zone.objects.all().order_by('name')
    
    context = {
        'zones': zones,
        'total_count': zones.count(),
        'active_count': zones.filter(is_active=True).count(),
    }
    
    return render(request, 'geofencing/zone_list.html', context)


@login_required
def zone_detail(request, zone_id):
    """View zone details from Firebase"""
    firebase_service = GeofenceFirebaseService()
    zone_data = firebase_service.get_zone(zone_id)
    
    if not zone_data:
        messages.error(request, f'Zone {zone_id} not found in Firebase')
        return redirect('geofencing:zone_list')
    
    # Get PostgreSQL data if exists
    try:
        pg_zone = Zone.objects.get(firebase_id=zone_id)
    except Zone.DoesNotExist:
        pg_zone = None
    
    context = {
        'zone': zone_data,
        'pg_zone': pg_zone,
    }
    
    return render(request, 'geofencing/zone_detail.html', context)


@login_required
def sync_zone(request, zone_id):
    """Sync a single zone from Firebase to PostgreSQL"""
    sync_service = GeofenceSyncService()
    success = sync_service.sync_single_zone(zone_id)
    
    if success:
        messages.success(request, f'Zone {zone_id} synced successfully')
    else:
        messages.error(request, f'Failed to sync zone {zone_id}')
    
    return redirect('geofencing:zone_detail', zone_id=zone_id)


@login_required
def sync_all_zones(request):
    """Sync all zones from Firebase to PostgreSQL"""
    sync_service = GeofenceSyncService()
    stats = sync_service.sync_all_zones()
    
    messages.success(
        request,
        f'Synced {stats["total"]} zones: {stats["created"]} created, {stats["updated"]} updated'
    )
    
    return redirect('geofencing:zone_list')