"""
Firebase Service for Bikes
Handles all Firebase Firestore operations for bikes
"""

from firebase_admin import firestore
from datetime import datetime
from typing import List, Dict, Optional
import logging

logger = logging.getLogger(__name__)


class BikeFirebaseService:
    """Service class for Firebase bike operations"""
    
    def __init__(self):
        self.db = firestore.client()
        self.collection = self.db.collection('bikes')
    
    def get_bike(self, bike_id: str) -> Optional[Dict]:
        """
        Get a single bike from Firebase
        
        Args:
            bike_id: Firebase document ID
            
        Returns:
            Dictionary with bike data or None if not found
        """
        try:
            doc_ref = self.collection.document(bike_id)
            doc = doc_ref.get()
            
            if doc.exists:
                data = doc.to_dict()
                
                # Convert GeoPoint to lat/lng dict
                if 'current_location' in data and data['current_location']:
                    data['current_latitude'] = data['current_location'].latitude
                    data['current_longitude'] = data['current_location'].longitude
                
                data['firebase_id'] = doc.id
                return data
            
            return None
        except Exception as e:
            logger.error(f"Error fetching bike {bike_id}: {e}")
            return None
    
    def list_bikes(self, status: Optional[str] = None, zone_id: Optional[str] = None) -> List[Dict]:
        """
        List all bikes from Firebase with optional filters
        
        Args:
            status: Filter by status (AVAILABLE, IN_USE, etc.)
            zone_id: Filter by current zone
            
        Returns:
            List of bike dictionaries
        """
        try:
            query = self.collection
            
            if status:
                query = query.where('status', '==', status)
            
            if zone_id:
                query = query.where('current_zone_id', '==', zone_id)
            
            docs = query.stream()
            bikes = []
            
            for doc in docs:
                data = doc.to_dict()
                
                # Convert GeoPoint to lat/lng
                if 'current_location' in data and data['current_location']:
                    data['current_latitude'] = data['current_location'].latitude
                    data['current_longitude'] = data['current_location'].longitude
                
                data['firebase_id'] = doc.id
                bikes.append(data)
            
            return bikes
        except Exception as e:
            logger.error(f"Error listing bikes: {e}")
            return []
    
    def create_bike(self, bike_id: str, bike_data: Dict) -> bool:
        """
        Create a new bike in Firebase
        
        Args:
            bike_id: Document ID for the bike
            bike_data: Dictionary containing bike information
            
        Returns:
            True if successful, False otherwise
        """
        try:
            doc_ref = self.collection.document(bike_id)
            
            # Prepare data with GeoPoint
            data = {
                'bike_model': bike_data.get('bike_model', ''),
                'bike_type': bike_data.get('bike_type', 'REGULAR'),
                'status': bike_data.get('status', 'AVAILABLE'),
                'current_zone_id': bike_data.get('current_zone_id', ''),
                'created_at': firestore.SERVER_TIMESTAMP,
            }
            
            # Add current location as GeoPoint if provided
            if 'latitude' in bike_data and 'longitude' in bike_data:
                data['current_location'] = firestore.GeoPoint(
                    latitude=float(bike_data['latitude']),
                    longitude=float(bike_data['longitude'])
                )
            
            doc_ref.set(data)
            logger.info(f"Created bike {bike_id} in Firebase")
            return True
        except Exception as e:
            logger.error(f"Error creating bike {bike_id}: {e}")
            return False
    
    def update_bike(self, bike_id: str, updates: Dict) -> bool:
        """
        Update a bike in Firebase
        
        Args:
            bike_id: Firebase document ID
            updates: Dictionary of fields to update
            
        Returns:
            True if successful, False otherwise
        """
        try:
            doc_ref = self.collection.document(bike_id)
            
            # Convert lat/lng to GeoPoint if present
            if 'latitude' in updates and 'longitude' in updates:
                updates['current_location'] = firestore.GeoPoint(
                    latitude=float(updates.pop('latitude')),
                    longitude=float(updates.pop('longitude'))
                )
            
            updates['updated_at'] = firestore.SERVER_TIMESTAMP
            doc_ref.update(updates)
            logger.info(f"Updated bike {bike_id} in Firebase")
            return True
        except Exception as e:
            logger.error(f"Error updating bike {bike_id}: {e}")
            return False
    
    def update_bike_location(self, bike_id: str, latitude: float, longitude: float, speed: Optional[float] = None) -> bool:
        """
        Update bike location and add to location history
        
        Args:
            bike_id: Firebase document ID
            latitude: Current latitude
            longitude: Current longitude
            speed: Current speed in km/h (optional)
            
        Returns:
            True if successful, False otherwise
        """
        try:
            doc_ref = self.collection.document(bike_id)
            
            # Update current location
            doc_ref.update({
                'current_location': firestore.GeoPoint(
                    latitude=float(latitude),
                    longitude=float(longitude)
                ),
                'updated_at': firestore.SERVER_TIMESTAMP
            })
            
            # Add to location history subcollection
            history_ref = doc_ref.collection('location_history').document()
            history_data = {
                'location': firestore.GeoPoint(
                    latitude=float(latitude),
                    longitude=float(longitude)
                ),
                'recorded_at': firestore.SERVER_TIMESTAMP
            }
            
            if speed is not None:
                history_data['speed'] = float(speed)
            
            history_ref.set(history_data)
            
            logger.info(f"Updated location for bike {bike_id}")
            return True
        except Exception as e:
            logger.error(f"Error updating bike location {bike_id}: {e}")
            return False
    
    def get_location_history(self, bike_id: str, limit: int = 100) -> List[Dict]:
        """
        Get location history for a bike
        
        Args:
            bike_id: Firebase document ID
            limit: Maximum number of records to retrieve
            
        Returns:
            List of location history dictionaries
        """
        try:
            doc_ref = self.collection.document(bike_id)
            history_ref = doc_ref.collection('location_history')
            
            # Order by recorded_at descending and limit results
            query = history_ref.order_by('recorded_at', direction=firestore.Query.DESCENDING).limit(limit)
            docs = query.stream()
            
            history = []
            for doc in docs:
                data = doc.to_dict()
                
                # Convert GeoPoint to lat/lng
                if 'location' in data and data['location']:
                    data['latitude'] = data['location'].latitude
                    data['longitude'] = data['location'].longitude
                
                data['id'] = doc.id
                history.append(data)
            
            return history
        except Exception as e:
            logger.error(f"Error fetching location history for bike {bike_id}: {e}")
            return []
    
    def delete_bike(self, bike_id: str) -> bool:
        """
        Delete a bike from Firebase (or mark as inactive)
        
        Args:
            bike_id: Firebase document ID
            
        Returns:
            True if successful, False otherwise
        """
        try:
            doc_ref = self.collection.document(bike_id)
            
            # Soft delete - mark as OFFLINE
            doc_ref.update({
                'status': 'OFFLINE',
                'updated_at': firestore.SERVER_TIMESTAMP
            })
            
            logger.info(f"Soft deleted bike {bike_id}")
            return True
        except Exception as e:
            logger.error(f"Error deleting bike {bike_id}: {e}")
            return False
    
    def update_bike_status(self, bike_id: str, status: str) -> bool:
        """
        Update bike status
        
        Args:
            bike_id: Firebase document ID
            status: New status (AVAILABLE, IN_USE, MAINTENANCE, OFFLINE)
            
        Returns:
            True if successful, False otherwise
        """
        try:
            doc_ref = self.collection.document(bike_id)
            doc_ref.update({
                'status': status,
                'updated_at': firestore.SERVER_TIMESTAMP
            })
            logger.info(f"Updated bike {bike_id} status to {status}")
            return True
        except Exception as e:
            logger.error(f"Error updating bike status {bike_id}: {e}")
            return False
    
    def get_bikes_by_zone(self, zone_id: str) -> List[Dict]:
        """
        Get all bikes in a specific zone
        
        Args:
            zone_id: Firebase zone document ID
            
        Returns:
            List of bikes in the zone
        """
        return self.list_bikes(zone_id=zone_id)
    
    def get_available_bikes(self) -> List[Dict]:
        """
        Get all available bikes
        
        Returns:
            List of available bikes
        """
        return self.list_bikes(status='AVAILABLE')