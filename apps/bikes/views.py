"""
Bikes Views - Complete CRUD Operations
"""

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from .models import Bike
from .firebase_service import BikeFirebaseService
from .sync_service import BikeSyncService
from .forms import BikeCreateForm, BikeUpdateForm
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
        'offline_count': Bike.objects.filter(status='OFFLINE').count(),
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
def bike_create(request):
    """Create a new bike in Firebase and PostgreSQL"""
    if request.method == 'POST':
        form = BikeCreateForm(request.POST)
        if form.is_valid():
            bike_id = form.cleaned_data['bike_id']
            
            # Check if bike already exists
            firebase_service = BikeFirebaseService()
            existing_bike = firebase_service.get_bike(bike_id)
            
            if existing_bike:
                messages.error(request, f'Bike {bike_id} already exists!')
                return render(request, 'bikes/bike_form.html', {'form': form})
            
            # Prepare bike data
            bike_data = {
                'bike_model': form.cleaned_data['bike_model'],
                'bike_type': form.cleaned_data['bike_type'],
                'status': form.cleaned_data['status'],
                'current_zone_id': form.cleaned_data.get('current_zone_id', ''),
            }
            
            # Add location if provided
            if form.cleaned_data.get('latitude') and form.cleaned_data.get('longitude'):
                bike_data['latitude'] = form.cleaned_data['latitude']
                bike_data['longitude'] = form.cleaned_data['longitude']
            
            # Create in Firebase
            success = firebase_service.create_bike(bike_id, bike_data)
            
            if success:
                # Sync to PostgreSQL
                sync_service = BikeSyncService()
                sync_service.sync_single_bike(bike_id)
                
                messages.success(request, f'Bike {bike_id} created successfully!')
                return redirect('bikes:bike_detail', bike_id=bike_id)
            else:
                messages.error(request, 'Failed to create bike in Firebase')
        else:
            messages.error(request, 'Please correct the errors below')
    else:
        form = BikeCreateForm()
    
    return render(request, 'bikes/bike_form.html', {
        'form': form,
        'title': 'Add New Bike',
        'action': 'Create'
    })


@login_required
def bike_update(request, bike_id):
    """Update bike in Firebase and PostgreSQL"""
    firebase_service = BikeFirebaseService()
    bike_data = firebase_service.get_bike(bike_id)
    
    if not bike_data:
        messages.error(request, f'Bike {bike_id} not found')
        return redirect('bikes:bike_list')
    
    if request.method == 'POST':
        form = BikeUpdateForm(request.POST)
        if form.is_valid():
            # Prepare update data
            updates = {}
            
            if form.cleaned_data.get('bike_model'):
                updates['bike_model'] = form.cleaned_data['bike_model']
            if form.cleaned_data.get('bike_type'):
                updates['bike_type'] = form.cleaned_data['bike_type']
            if form.cleaned_data.get('status'):
                updates['status'] = form.cleaned_data['status']
            if form.cleaned_data.get('current_zone_id') is not None:
                updates['current_zone_id'] = form.cleaned_data['current_zone_id']
            
            # Update location if provided
            if form.cleaned_data.get('latitude') and form.cleaned_data.get('longitude'):
                updates['latitude'] = form.cleaned_data['latitude']
                updates['longitude'] = form.cleaned_data['longitude']
            
            # Update in Firebase
            success = firebase_service.update_bike(bike_id, updates)
            
            if success:
                # Sync to PostgreSQL
                sync_service = BikeSyncService()
                sync_service.sync_single_bike(bike_id)
                
                messages.success(request, f'Bike {bike_id} updated successfully!')
                return redirect('bikes:bike_detail', bike_id=bike_id)
            else:
                messages.error(request, 'Failed to update bike')
        else:
            messages.error(request, 'Please correct the errors below')
    else:
        # Pre-fill form with existing data
        initial_data = {
            'bike_model': bike_data.get('bike_model'),
            'bike_type': bike_data.get('bike_type'),
            'status': bike_data.get('status'),
            'current_zone_id': bike_data.get('current_zone_id', ''),
            'latitude': bike_data.get('current_latitude'),
            'longitude': bike_data.get('current_longitude'),
        }
        form = BikeUpdateForm(initial=initial_data)
    
    return render(request, 'bikes/bike_form.html', {
        'form': form,
        'bike_id': bike_id,
        'title': f'Edit Bike {bike_id}',
        'action': 'Update'
    })


@login_required
def bike_delete(request, bike_id):
    """Archive bike from Firebase and PostgreSQL"""
    if request.method == 'POST':
        firebase_service = BikeFirebaseService()
        
        # Archive in Firebase (soft delete)
        success = firebase_service.delete_bike(bike_id)
        
        if success:
            # Update status in PostgreSQL to ARCHIVED
            Bike.objects.filter(firebase_id=bike_id).update(status='ARCHIVED')
            
            messages.success(request, f'Bike {bike_id} has been archived')
            return redirect('bikes:bike_list')
        else:
            messages.error(request, 'Failed to archive bike')
            return redirect('bikes:bike_detail', bike_id=bike_id)
    
    # Show confirmation page
    firebase_service = BikeFirebaseService()
    bike_data = firebase_service.get_bike(bike_id)
    
    if not bike_data:
        messages.error(request, f'Bike {bike_id} not found')
        return redirect('bikes:bike_list')
    
    return render(request, 'bikes/bike_confirm_delete.html', {
        'bike': bike_data,
        'bike_id': bike_id
    })


@login_required
def bike_restore(request, bike_id):
    """Restore an archived bike"""
    if request.method == 'POST':
        new_status = request.POST.get('status', 'AVAILABLE')
        
        firebase_service = BikeFirebaseService()
        success = firebase_service.restore_bike(bike_id, new_status)
        
        if success:
            # Sync to PostgreSQL
            sync_service = BikeSyncService()
            sync_service.sync_single_bike(bike_id)
            
            messages.success(request, f'Bike {bike_id} has been restored')
            return redirect('bikes:bike_detail', bike_id=bike_id)
        else:
            messages.error(request, 'Failed to restore bike')
            return redirect('bikes:bike_list')
    
    # Show confirmation page
    firebase_service = BikeFirebaseService()
    bike_data = firebase_service.get_bike(bike_id)
    
    if not bike_data:
        messages.error(request, f'Bike {bike_id} not found')
        return redirect('bikes:bike_list')
    
    return render(request, 'bikes/bike_confirm_restore.html', {
        'bike': bike_data,
        'bike_id': bike_id
    })


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
def bike_update_status(request, bike_id):
    """Quick status update via AJAX"""
    if request.method == 'POST':
        new_status = request.POST.get('status')
        
        if new_status not in ['AVAILABLE', 'IN_USE', 'MAINTENANCE', 'OFFLINE']:
            return JsonResponse({'success': False, 'error': 'Invalid status'})
        
        firebase_service = BikeFirebaseService()
        success = firebase_service.update_bike_status(bike_id, new_status)
        
        if success:
            # Sync to PostgreSQL
            sync_service = BikeSyncService()
            sync_service.sync_single_bike(bike_id)
            
            return JsonResponse({
                'success': True,
                'message': f'Status updated to {new_status}'
            })
        else:
            return JsonResponse({
                'success': False,
                'error': 'Failed to update status'
            })
    
    return JsonResponse({'success': False, 'error': 'Invalid request method'})


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