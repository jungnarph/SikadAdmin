"""
Bike Sync Service
Syncs bike data from Firebase to PostgreSQL
"""

from .firebase_service import BikeFirebaseService
from .models import Bike, BikeLocationHistory
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


class BikeSyncService:
    """Service to sync bikes from Firebase to PostgreSQL"""
    
    def __init__(self):
        self.firebase_service = BikeFirebaseService()
    
    def sync_single_bike(self, bike_id: str) -> bool:
        """
        Sync a single bike from Firebase to PostgreSQL
        
        Args:
            bike_id: Firebase document ID
            
        Returns:
            True if successful, False otherwise
        """
        try:
            # Get bike data from Firebase
            firebase_data = self.firebase_service.get_bike(bike_id)
            
            if not firebase_data:
                logger.warning(f"Bike {bike_id} not found in Firebase")
                return False
            
            # Update or create in PostgreSQL
            bike, created = Bike.objects.update_or_create(
                firebase_id=bike_id,
                defaults={
                    'bike_model': firebase_data.get('bike_model', ''),
                    'bike_type': firebase_data.get('bike_type', 'REGULAR'),
                    'status': firebase_data.get('status', 'AVAILABLE'),
                    'current_latitude': firebase_data.get('current_latitude'),
                    'current_longitude': firebase_data.get('current_longitude'),
                    'current_zone_id': firebase_data.get('current_zone_id', ''),
                }
            )
            
            action = "created" if created else "updated"
            logger.info(f"Bike {bike_id} {action} in PostgreSQL")
            return True
            
        except Exception as e:
            logger.error(f"Error syncing bike {bike_id}: {e}")
            return False
    
    def sync_all_bikes(self) -> dict:
        """
        Sync all bikes from Firebase to PostgreSQL
        
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
            # Get all bikes from Firebase
            firebase_bikes = self.firebase_service.list_bikes()
            stats['total'] = len(firebase_bikes)
            
            for bike_data in firebase_bikes:
                try:
                    bike_id = bike_data['firebase_id']
                    
                    bike, created = Bike.objects.update_or_create(
                        firebase_id=bike_id,
                        defaults={
                            'bike_model': bike_data.get('bike_model', ''),
                            'bike_type': bike_data.get('bike_type', 'REGULAR'),
                            'status': bike_data.get('status', 'AVAILABLE'),
                            'current_latitude': bike_data.get('current_latitude'),
                            'current_longitude': bike_data.get('current_longitude'),
                            'current_zone_id': bike_data.get('current_zone_id', ''),
                        }
                    )
                    
                    if created:
                        stats['created'] += 1
                    else:
                        stats['updated'] += 1
                        
                except Exception as e:
                    logger.error(f"Error syncing bike: {e}")
                    stats['failed'] += 1
            
            logger.info(f"Sync completed: {stats}")
            return stats
            
        except Exception as e:
            logger.error(f"Error syncing all bikes: {e}")
            return stats
    
    def sync_bike_location_history(self, bike_id: str, limit: int = 100) -> int:
        """
        Sync location history for a bike from Firebase to PostgreSQL
        
        Args:
            bike_id: Firebase document ID
            limit: Maximum number of records to sync
            
        Returns:
            Number of records synced
        """
        try:
            # Ensure bike exists in PostgreSQL
            bike = Bike.objects.filter(firebase_id=bike_id).first()
            if not bike:
                logger.warning(f"Bike {bike_id} not found in PostgreSQL, syncing first")
                self.sync_single_bike(bike_id)
                bike = Bike.objects.get(firebase_id=bike_id)
            
            # Get location history from Firebase
            history = self.firebase_service.get_location_history(bike_id, limit=limit)
            
            synced_count = 0
            for record in history:
                try:
                    BikeLocationHistory.objects.update_or_create(
                        bike=bike,
                        recorded_at=record.get('recorded_at'),
                        defaults={
                            'latitude': record.get('latitude'),
                            'longitude': record.get('longitude'),
                            'speed': record.get('speed'),
                        }
                    )
                    synced_count += 1
                except Exception as e:
                    logger.error(f"Error syncing location record: {e}")
            
            logger.info(f"Synced {synced_count} location records for bike {bike_id}")
            return synced_count
            
        except Exception as e:
            logger.error(f"Error syncing location history for bike {bike_id}: {e}")
            return 0
    
    def get_bikes_needing_sync(self) -> list:
        """
        Get list of bikes that need to be synced
        (Bikes in Firebase but not in PostgreSQL or outdated)
        
        Returns:
            List of bike IDs
        """
        try:
            # Get all bike IDs from Firebase
            firebase_bikes = self.firebase_service.list_bikes()
            firebase_ids = {bike['firebase_id'] for bike in firebase_bikes}
            
            # Get all bike IDs from PostgreSQL
            postgres_ids = set(Bike.objects.values_list('firebase_id', flat=True))
            
            # Find bikes in Firebase but not in PostgreSQL
            missing_ids = firebase_ids - postgres_ids
            
            return list(missing_ids)
            
        except Exception as e:
            logger.error(f"Error finding bikes needing sync: {e}")
            return []
    
    def sync_bike_to_firebase(self, bike_id: str, updates: dict) -> bool:
        """
        Push updates from PostgreSQL/Admin to Firebase
        
        Args:
            bike_id: Firebase document ID
            updates: Dictionary of fields to update
            
        Returns:
            True if successful, False otherwise
        """
        try:
            success = self.firebase_service.update_bike(bike_id, updates)
            
            if success:
                # Also update in PostgreSQL
                Bike.objects.filter(firebase_id=bike_id).update(**updates)
                logger.info(f"Pushed updates for bike {bike_id} to Firebase")
            
            return success
            
        except Exception as e:
            logger.error(f"Error pushing bike updates to Firebase: {e}")
            return False