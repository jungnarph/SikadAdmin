"""
Geofence Sync Service - ARRAY Format Compatible
Syncs geofence zone data from Firebase to PostgreSQL
"""

from .firebase_service import GeofenceFirebaseService
from .models import Zone
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


class GeofenceSyncService:
    """Service to sync geofence zones from Firebase to PostgreSQL"""
    
    def __init__(self):
        self.firebase_service = GeofenceFirebaseService()
    
    def sync_single_zone(self, zone_id: str) -> bool:
        """
        Sync a single zone from Firebase to PostgreSQL
        
        Args:
            zone_id: Firebase document ID
            
        Returns:
            True if successful, False otherwise
        """
        try:
            # Get zone data from Firebase (now returns ARRAY format)
            firebase_data = self.firebase_service.get_zone(zone_id)
            
            if not firebase_data:
                logger.warning(f"Zone {zone_id} not found in Firebase")
                return False
            
            # Update or create in PostgreSQL
            zone, created = Zone.objects.update_or_create(
                firebase_id=zone_id,
                defaults={
                    'name': firebase_data.get('name', ''),
                    'color_code': firebase_data.get('color_code', '#3388ff'),
                    'is_active': firebase_data.get('is_active', True),
                    'center_latitude': firebase_data.get('center_latitude'),
                    'center_longitude': firebase_data.get('center_longitude'),
                    'polygon_points': firebase_data.get('polygon_points', []),
                }
            )
            
            action = "created" if created else "updated"
            logger.info(f"Zone {zone_id} {action} in PostgreSQL")
            return True
            
        except Exception as e:
            logger.error(f"Error syncing zone {zone_id}: {e}")
            return False
    
    def sync_all_zones(self) -> dict:
        """
        Sync all zones from Firebase to PostgreSQL
        
        Returns:
            Dictionary with sync statistics
        """
        stats = {
            'total': 0,
            'created': 0,
            'updated': 0,
            'failed': 0
        }
        
        try:
            # Get all zones from Firebase (now returns ARRAY format)
            firebase_zones = self.firebase_service.list_zones(active_only=False)
            stats['total'] = len(firebase_zones)
            
            for zone_data in firebase_zones:
                try:
                    zone_id = zone_data['firebase_id']
                    
                    zone, created = Zone.objects.update_or_create(
                        firebase_id=zone_id,
                        defaults={
                            'name': zone_data.get('name', ''),
                            'color_code': zone_data.get('color_code', '#3388ff'),
                            'is_active': zone_data.get('is_active', True),
                            'center_latitude': zone_data.get('center_latitude'),
                            'center_longitude': zone_data.get('center_longitude'),
                            'polygon_points': zone_data.get('polygon_points', []),
                        }
                    )
                    
                    if created:
                        stats['created'] += 1
                    else:
                        stats['updated'] += 1
                        
                except Exception as e:
                    logger.error(f"Error syncing zone: {e}")
                    stats['failed'] += 1
            
            logger.info(f"Zone sync completed: {stats}")
            return stats
            
        except Exception as e:
            logger.error(f"Error syncing all zones: {e}")
            return stats
    
    def get_zones_needing_sync(self) -> list:
        """
        Get list of zones that need to be synced
        (Zones in Firebase but not in PostgreSQL)
        
        Returns:
            List of zone IDs
        """
        try:
            # Get all zone IDs from Firebase
            firebase_zones = self.firebase_service.list_zones(active_only=False)
            firebase_ids = {zone['firebase_id'] for zone in firebase_zones}
            
            # Get all zone IDs from PostgreSQL
            postgres_ids = set(Zone.objects.values_list('firebase_id', flat=True))
            
            # Find zones in Firebase but not in PostgreSQL
            missing_ids = firebase_ids - postgres_ids
            
            return list(missing_ids)
            
        except Exception as e:
            logger.error(f"Error finding zones needing sync: {e}")
            return []
    
    def sync_zone_to_firebase(self, zone_id: str, updates: dict) -> bool:
        """
        Push updates from PostgreSQL/Admin to Firebase
        
        Args:
            zone_id: Firebase document ID
            updates: Dictionary of fields to update
            
        Returns:
            True if successful, False otherwise
        """
        try:
            success = self.firebase_service.update_zone(zone_id, updates)
            
            if success:
                # Also update in PostgreSQL
                Zone.objects.filter(firebase_id=zone_id).update(**updates)
                logger.info(f"Pushed updates for zone {zone_id} to Firebase")
            
            return success
            
        except Exception as e:
            logger.error(f"Error pushing zone updates to Firebase: {e}")
            return False
    
    def create_zone_in_firebase(self, zone_data: dict) -> str:
        """
        Create a new zone in Firebase from admin panel
        
        Args:
            zone_data: Dictionary with zone information
            
        Returns:
            Zone ID if successful, None otherwise
        """
        try:
            # Generate zone ID (or use provided one)
            zone_id = zone_data.get('firebase_id') or zone_data.get('name').lower().replace(' ', '_')
            
            # Create in Firebase (uses ARRAY format)
            success = self.firebase_service.create_zone(zone_id, zone_data)
            
            if success:
                # Sync back to PostgreSQL
                self.sync_single_zone(zone_id)
                logger.info(f"Created zone {zone_id} in Firebase and PostgreSQL")
                return zone_id
            
            return None
            
        except Exception as e:
            logger.error(f"Error creating zone in Firebase: {e}")
            return None