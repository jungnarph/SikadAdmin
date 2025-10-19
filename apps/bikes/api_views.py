"""
Bikes API Views - REST endpoints for real-time bike data
"""

from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.contrib.auth.decorators import login_required
from django.views.decorators.csrf import csrf_exempt
from .models import Bike
from .firebase_service import BikeFirebaseService
import json


@login_required
@require_http_methods(["GET"])
def api_bikes_list(request):
    """
    API endpoint to get all bikes with current locations
    Used for real-time map updates
    """
    try:
        # Get bikes from PostgreSQL with location data
        bikes = Bike.objects.filter(
            current_latitude__isnull=False,
            current_longitude__isnull=False
        ).exclude(status='ARCHIVED')
        
        bikes_data = []
        for bike in bikes:
            bikes_data.append({
                'bike_id': bike.firebase_id,
                'bike_model': bike.bike_model,
                'bike_type': bike.bike_type,
                'status': bike.status,
                'latitude': float(bike.current_latitude),
                'longitude': float(bike.current_longitude),
                'current_zone_id': bike.current_zone_id or '',
                'last_updated': bike.updated_at.isoformat() if bike.updated_at else None,
            })
        
        return JsonResponse({
            'success': True,
            'count': len(bikes_data),
            'bikes': bikes_data
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


@login_required
@require_http_methods(["GET"])
def api_bike_detail(request, bike_id):
    """
    API endpoint to get single bike details from Firebase
    """
    try:
        firebase_service = BikeFirebaseService()
        bike_data = firebase_service.get_bike(bike_id)
        
        if not bike_data:
            return JsonResponse({
                'success': False,
                'error': f'Bike {bike_id} not found'
            }, status=404)
        
        return JsonResponse({
            'success': True,
            'bike': bike_data
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


@login_required
@require_http_methods(["POST"])
@csrf_exempt
def api_bike_update_location(request, bike_id):
    """
    API endpoint to manually update bike location
    """
    try:
        data = json.loads(request.body)
        latitude = data.get('latitude')
        longitude = data.get('longitude')
        speed = data.get('speed')
        
        if not latitude or not longitude:
            return JsonResponse({
                'success': False,
                'error': 'Latitude and longitude are required'
            }, status=400)
        
        # Update in Firebase
        firebase_service = BikeFirebaseService()
        success = firebase_service.update_bike_location(
            bike_id, 
            float(latitude), 
            float(longitude),
            float(speed) if speed else None
        )
        
        if success:
            # Update PostgreSQL
            try:
                bike = Bike.objects.get(firebase_id=bike_id)
                bike.current_latitude = latitude
                bike.current_longitude = longitude
                bike.save()
            except Bike.DoesNotExist:
                pass  # PostgreSQL record doesn't exist yet
            
            return JsonResponse({
                'success': True,
                'message': f'Location updated for bike {bike_id}'
            })
        else:
            return JsonResponse({
                'success': False,
                'error': 'Failed to update location in Firebase'
            }, status=500)
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


@login_required
@require_http_methods(["GET"])
def api_bikes_by_status(request):
    """
    API endpoint to get bikes grouped by status
    """
    try:
        from django.db.models import Count
        
        status_counts = Bike.objects.exclude(status='ARCHIVED').values('status').annotate(
            count=Count('id')
        )
        
        stats = {
            'AVAILABLE': 0,
            'IN_USE': 0,
            'OFFLINE': 0,
            'MAINTENANCE': 0
        }
        
        for item in status_counts:
            stats[item['status']] = item['count']
        
        return JsonResponse({
            'success': True,
            'stats': stats,
            'total': sum(stats.values())
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


@login_required
@require_http_methods(["GET"])
def api_bike_location_history(request, bike_id):
    """
    API endpoint to get bike location history
    """
    try:
        firebase_service = BikeFirebaseService()
        limit = int(request.GET.get('limit', 50))
        
        history = firebase_service.get_location_history(bike_id, limit=limit)
        
        return JsonResponse({
            'success': True,
            'bike_id': bike_id,
            'count': len(history),
            'history': history
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)