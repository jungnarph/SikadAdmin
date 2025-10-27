"""
Geofencing Views - Complete CRUD Operations
"""

from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.utils import timezone
from .models import Zone, ZoneViolation
from .firebase_service import GeofenceFirebaseService
from .sync_service import GeofenceSyncService
from .violation_listener import GeofenceViolationListener
from .forms import ZoneCreateForm, ZoneUpdateForm, ViolationFilterForm
from apps.accounts.decorators import super_admin_required, staff_or_super_admin_required
import json


@login_required
def zone_list(request):
    """List all geofence zones from PostgreSQL"""
    zones = Zone.objects.all().order_by('name')
    
    # Apply filters
    is_active = request.GET.get('is_active')
    search = request.GET.get('search')
    
    if is_active == 'active':
        zones = zones.filter(is_active=True)
    elif is_active == 'inactive':
        zones = zones.filter(is_active=False)
    if search:
        zones = zones.filter(name__icontains=search) | zones.filter(firebase_id__icontains=search)
    
    context = {
        'zones': zones,
        'total_count': Zone.objects.count(),
        'active_count': Zone.objects.filter(is_active=True).count(),
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
    
    # Get recent violations for this zone
    violations = ZoneViolation.objects.filter(
        zone__firebase_id=zone_id
    ).order_by('-violation_time')[:10]
    
    context = {
        'zone': zone_data,
        'pg_zone': pg_zone,
        'violations': violations,
    }
    
    return render(request, 'geofencing/zone_detail.html', context)


@login_required
@staff_or_super_admin_required
def zone_create(request):
    """Create a new geofence zone"""
    if request.method == 'POST':
        form = ZoneCreateForm(request.POST)
        if form.is_valid():
            zone_id = form.cleaned_data['zone_id']
            
            # Check if zone already exists
            firebase_service = GeofenceFirebaseService()
            existing_zone = firebase_service.get_zone(zone_id)
            
            if existing_zone:
                messages.error(request, f'Zone {zone_id} already exists!')
                return render(request, 'geofencing/zone_form.html', {
                    'form': form,
                    'title': 'Create New Zone',
                    'action': 'Create'
                })
            
            # Prepare zone data
            polygon_points = json.loads(form.cleaned_data['polygon_points'])
            
            zone_data = {
                'name': form.cleaned_data['name'],
                'color_code': form.cleaned_data['color_code'],
                'points': polygon_points,
            }
            
            if form.cleaned_data.get('description'):
                zone_data['description'] = form.cleaned_data['description']
            
            # Create in Firebase
            success = firebase_service.create_zone(zone_id, zone_data)
            
            if success:
                # Sync to PostgreSQL
                sync_service = GeofenceSyncService()
                sync_service.sync_single_zone(zone_id)
                
                messages.success(request, f'Zone {zone_id} created successfully!')
                return redirect('geofencing:zone_detail', zone_id=zone_id)
            else:
                messages.error(request, 'Failed to create zone in Firebase')
        else:
            messages.error(request, 'Please correct the errors below')
    else:
        form = ZoneCreateForm()
    
    return render(request, 'geofencing/zone_form.html', {
        'form': form,
        'title': 'Create New Zone',
        'action': 'Create'
    })


@login_required
@staff_or_super_admin_required
def zone_update(request, zone_id):
    """Update geofence zone"""
    firebase_service = GeofenceFirebaseService()
    zone_data = firebase_service.get_zone(zone_id)
    
    if not zone_data:
        messages.error(request, f'Zone {zone_id} not found')
        return redirect('geofencing:zone_list')
    
    if request.method == 'POST':
        form = ZoneUpdateForm(request.POST)
        if form.is_valid():
            # Prepare update data
            updates = {
                'name': form.cleaned_data['name'],
                'color_code': form.cleaned_data['color_code'],
                'is_active': form.cleaned_data.get('is_active', True),
            }
            
            if form.cleaned_data.get('description'):
                updates['description'] = form.cleaned_data['description']
            
            # Update polygon if provided
            if form.cleaned_data.get('polygon_points'):
                updates['points'] = json.loads(form.cleaned_data['polygon_points'])
            
            # Update in Firebase
            success = firebase_service.update_zone(zone_id, updates)
            
            if success:
                # Sync to PostgreSQL
                sync_service = GeofenceSyncService()
                sync_service.sync_single_zone(zone_id)
                
                messages.success(request, f'Zone {zone_id} updated successfully!')
                return redirect('geofencing:zone_detail', zone_id=zone_id)
            else:
                messages.error(request, 'Failed to update zone')
        else:
            messages.error(request, 'Please correct the errors below')
    else:
        # Pre-fill form with existing data
        initial_data = {
            'name': zone_data.get('name'),
            'color_code': zone_data.get('color_code', '#3388ff'),
            'description': zone_data.get('description', ''),
            'is_active': zone_data.get('is_active', True),
            'polygon_points': json.dumps(zone_data.get('polygon_points', [])),
        }
        form = ZoneUpdateForm(initial=initial_data)
    
    return render(request, 'geofencing/zone_form.html', {
        'form': form,
        'zone_id': zone_id,
        'zone': zone_data,
        'title': f'Edit Zone: {zone_data.get("name")}',
        'action': 'Update'
    })


@login_required
@super_admin_required
def zone_delete(request, zone_id):
    """Delete (deactivate) geofence zone"""
    if request.method == 'POST':
        firebase_service = GeofenceFirebaseService()
        
        # Soft delete in Firebase
        success = firebase_service.delete_zone(zone_id)
        
        if success:
            # Update in PostgreSQL
            Zone.objects.filter(firebase_id=zone_id).update(is_active=False)
            
            messages.success(request, f'Zone {zone_id} has been deactivated')
            return redirect('geofencing:zone_list')
        else:
            messages.error(request, 'Failed to deactivate zone')
            return redirect('geofencing:zone_detail', zone_id=zone_id)
    
    # Show confirmation page
    firebase_service = GeofenceFirebaseService()
    zone_data = firebase_service.get_zone(zone_id)
    
    if not zone_data:
        messages.error(request, f'Zone {zone_id} not found')
        return redirect('geofencing:zone_list')
    
    return render(request, 'geofencing/zone_confirm_delete.html', {
        'zone': zone_data,
        'zone_id': zone_id
    })


@login_required
def violation_list(request):
    """List all zone violations"""
    violations = ZoneViolation.objects.all().order_by('-violation_time')
    
    # Apply filters
    form = ViolationFilterForm(request.GET)
    if form.is_valid():
        if form.cleaned_data.get('violation_type'):
            violations = violations.filter(violation_type=form.cleaned_data['violation_type'])
        
        if form.cleaned_data.get('status') == 'resolved':
            violations = violations.filter(resolved=True)
        elif form.cleaned_data.get('status') == 'unresolved':
            violations = violations.filter(resolved=False)
        
        if form.cleaned_data.get('zone'):
            violations = violations.filter(zone__firebase_id__icontains=form.cleaned_data['zone'])
        
        if form.cleaned_data.get('bike_id'):
            violations = violations.filter(bike_id__icontains=form.cleaned_data['bike_id'])
    
    # Pagination
    from django.core.paginator import Paginator
    paginator = Paginator(violations, 25)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'violations': page_obj,
        'form': form,
        'total_violations': ZoneViolation.objects.count(),
        'unresolved_count': ZoneViolation.objects.filter(resolved=False).count(),
    }
    
    return render(request, 'geofencing/violation_list.html', context)


@login_required
@staff_or_super_admin_required
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
@staff_or_super_admin_required
def sync_all_zones(request):
    """Sync all zones from Firebase to PostgreSQL"""
    sync_service = GeofenceSyncService()
    stats = sync_service.sync_all_zones()

    messages.success(
        request,
        f'Synced {stats["total"]} zones: {stats["created"]} created, {stats["updated"]} updated'
    )

    return redirect('geofencing:zone_list')


@login_required
@staff_or_super_admin_required
def process_violations(request):
    """
    Process geofence violations from Firebase.
    Can be triggered manually via POST or show status via GET.
    """
    if request.method == 'POST':
        limit = int(request.POST.get('limit', 100))

        try:
            listener = GeofenceViolationListener()
            processed, created = listener.process_existing_violations(limit=limit)

            messages.success(
                request,
                f'✓ Processed {processed} violations. Created {created} new ZoneViolation records.'
            )
        except Exception as e:
            messages.error(request, f'Error processing violations: {str(e)}')

        return redirect('geofencing:violation_list')

    # GET request - show violation processing status
    context = {
        'total_violations': ZoneViolation.objects.count(),
        'unresolved_violations': ZoneViolation.objects.filter(resolved=False).count(),
        'recent_violations': ZoneViolation.objects.order_by('-created_at')[:10],
    }

    return render(request, 'geofencing/process_violations.html', context)


@login_required
@require_http_methods(["GET"])
def get_zone_data(request, zone_firebase_id):
    """
    API endpoint to get zone polygon data for map visualization
    """
    try:
        zone = Zone.objects.get(firebase_id=zone_firebase_id)

        # Normalize polygon points for frontend
        polygon_points = []
        if zone.polygon_points:
            for point in zone.polygon_points:
                if isinstance(point, dict):
                    if 'latitude' in point and 'longitude' in point:
                        polygon_points.append({
                            'lat': float(point['latitude']),
                            'lng': float(point['longitude'])
                        })

        return JsonResponse({
            'success': True,
            'zone': {
                'firebase_id': zone.firebase_id,
                'name': zone.name,
                'color_code': zone.color_code,
                'is_active': zone.is_active,
                'polygon_points': polygon_points,
                'center': {
                    'lat': float(zone.center_latitude) if zone.center_latitude else None,
                    'lng': float(zone.center_longitude) if zone.center_longitude else None
                }
            }
        })
    except Zone.DoesNotExist:
        return JsonResponse({
            'success': False,
            'error': 'Zone not found'
        }, status=404)
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


@login_required
@staff_or_super_admin_required
@require_http_methods(["POST"])
def resolve_violation(request, violation_id):
    """
    API endpoint to mark a violation as resolved
    """
    try:
        violation = ZoneViolation.objects.get(id=violation_id)

        # Update violation status
        violation.resolved = True
        violation.resolved_at = timezone.now()

        # Add note about who resolved it
        resolver_name = request.user.get_full_name() or request.user.username
        resolution_note = f"Resolved by {resolver_name} on {timezone.now().strftime('%Y-%m-%d %H:%M:%S')}"

        if violation.notes:
            violation.notes += f"\n{resolution_note}"
        else:
            violation.notes = resolution_note

        violation.save()

        return JsonResponse({
            'success': True,
            'message': 'Violation marked as resolved',
            'resolved_at': violation.resolved_at.strftime('%Y-%m-%d %H:%M:%S')
        })

    except ZoneViolation.DoesNotExist:
        return JsonResponse({
            'success': False,
            'error': 'Violation not found'
        }, status=404)
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)