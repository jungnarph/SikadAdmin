"""
Firebase Service for Geofencing
Handles all Firebase Firestore operations for geofence zones
"""

from firebase_admin import firestore
from datetime import datetime
from typing import List, Dict, Optional
import logging

logger = logging.getLogger(__name__)


class GeofenceFirebaseService:
    """Service class for Firebase geofence operations"""
    
    def __init__(self):
        self.db = firestore.client()
        self.collection = self.db.collection('geofence')
    
    def get_zone(self, zone_id: str) -> Optional[Dict]:
        """
        Get a single geofence zone from Firebase
        
        Args:
            zone_id: Firebase document ID
            
        Returns:
            Dictionary with zone data or None if not found
        """
        try:
            doc_ref = self.collection.document(zone_id)
            doc = doc_ref.get()
            
            if doc.exists:
                data = doc.to_dict()
                
                # Extract points from nested structure
                points = []
                if 'points' in data:
                    # Sort by key (0, 1, 2, ...)
                    sorted_points = sorted(data['points'].items(), key=lambda x: int(x[0]))
                    
                    for key, point_data in sorted_points:
                        if 'location' in point_data:
                            points.append({
                                'index': int(key),
                                'latitude': point_data['location'].latitude,
                                'longitude': point_data['location'].longitude
                            })
                
                # Calculate center point
                if points:
                    avg_lat = sum(p['latitude'] for p in points) / len(points)
                    avg_lng = sum(p['longitude'] for p in points) / len(points)
                    data['center_latitude'] = avg_lat
                    data['center_longitude'] = avg_lng
                
                data['firebase_id'] = doc.id
                data['polygon_points'] = points
                return data
            
            return None
        except Exception as e:
            logger.error(f"Error fetching zone {zone_id}: {e}")
            return None
    
    def list_zones(self, active_only: bool = True) -> List[Dict]:
        """
        List all geofence zones from Firebase
        
        Args:
            active_only: If True, only return active zones
            
        Returns:
            List of zone dictionaries
        """
        try:
            query = self.collection
            
            if active_only:
                query = query.where('is_active', '==', True)
            
            docs = query.stream()
            zones = []
            
            for doc in docs:
                data = doc.to_dict()
                
                # Extract points
                points = []
                if 'points' in data:
                    sorted_points = sorted(data['points'].items(), key=lambda x: int(x[0]))
                    
                    for key, point_data in sorted_points:
                        if 'location' in point_data:
                            points.append({
                                'index': int(key),
                                'latitude': point_data['location'].latitude,
                                'longitude': point_data['location'].longitude
                            })
                
                # Calculate center
                if points:
                    avg_lat = sum(p['latitude'] for p in points) / len(points)
                    avg_lng = sum(p['longitude'] for p in points) / len(points)
                    data['center_latitude'] = avg_lat
                    data['center_longitude'] = avg_lng
                
                data['firebase_id'] = doc.id
                data['polygon_points'] = points
                zones.append(data)
            
            return zones
        except Exception as e:
            logger.error(f"Error listing zones: {e}")
            return []
    
    def create_zone(self, zone_id: str, zone_data: Dict) -> bool:
        """
        Create a new geofence zone in Firebase
        
        Args:
            zone_id: Document ID for the zone
            zone_data: Dictionary containing zone information
                Required: name, zone_type, points (list of {lat, lng})
                Optional: color_code, is_active
            
        Returns:
            True if successful, False otherwise
        """
        try:
            doc_ref = self.collection.document(zone_id)
            
            # Prepare points in Firebase nested structure
            firebase_points = {}
            points = zone_data.get('points', [])
            
            for i, point in enumerate(points):
                firebase_points[str(i)] = {
                    'location': firestore.GeoPoint(
                        latitude=float(point['latitude']),
                        longitude=float(point['longitude'])
                    )
                }
            
            # Prepare zone data
            data = {
                'name': zone_data.get('name'),
                'zone_type': zone_data.get('zone_type', 'OPERATIONAL'),
                'is_active': zone_data.get('is_active', True),
                'color_code': zone_data.get('color_code', '#3388ff'),
                'points': firebase_points,
                'created_at': firestore.SERVER_TIMESTAMP,
                'updated_at': firestore.SERVER_TIMESTAMP
            }
            
            doc_ref.set(data)
            logger.info(f"Created zone {zone_id} in Firebase")
            return True
        except Exception as e:
            logger.error(f"Error creating zone {zone_id}: {e}")
            return False
    
    def update_zone(self, zone_id: str, updates: Dict) -> bool:
        """
        Update a geofence zone in Firebase
        
        Args:
            zone_id: Firebase document ID
            updates: Dictionary of fields to update
            
        Returns:
            True if successful, False otherwise
        """
        try:
            doc_ref = self.collection.document(zone_id)
            
            # Convert points if present
            if 'points' in updates:
                firebase_points = {}
                points = updates.pop('points')
                
                for i, point in enumerate(points):
                    firebase_points[str(i)] = {
                        'location': firestore.GeoPoint(
                            latitude=float(point['latitude']),
                            longitude=float(point['longitude'])
                        )
                    }
                
                updates['points'] = firebase_points
            
            updates['updated_at'] = firestore.SERVER_TIMESTAMP
            doc_ref.update(updates)
            logger.info(f"Updated zone {zone_id} in Firebase")
            return True
        except Exception as e:
            logger.error(f"Error updating zone {zone_id}: {e}")
            return False
    
    def delete_zone(self, zone_id: str) -> bool:
        """
        Delete a zone from Firebase (soft delete)
        
        Args:
            zone_id: Firebase document ID
            
        Returns:
            True if successful, False otherwise
        """
        try:
            doc_ref = self.collection.document(zone_id)
            doc_ref.update({
                'is_active': False,
                'updated_at': firestore.SERVER_TIMESTAMP
            })
            logger.info(f"Soft deleted zone {zone_id}")
            return True
        except Exception as e:
            logger.error(f"Error deleting zone {zone_id}: {e}")
            return False
    
    def add_point_to_zone(self, zone_id: str, latitude: float, longitude: float) -> bool:
        """
        Add a new point to an existing zone
        
        Args:
            zone_id: Firebase document ID
            latitude: Point latitude
            longitude: Point longitude
            
        Returns:
            True if successful, False otherwise
        """
        try:
            doc_ref = self.collection.document(zone_id)
            doc = doc_ref.get()
            
            if not doc.exists:
                logger.error(f"Zone {zone_id} not found")
                return False
            
            data = doc.to_dict()
            points = data.get('points', {})
            
            # Find next index
            max_index = max([int(k) for k in points.keys()]) if points else -1
            next_index = str(max_index + 1)
            
            # Add new point
            points[next_index] = {
                'location': firestore.GeoPoint(
                    latitude=float(latitude),
                    longitude=float(longitude)
                )
            }
            
            doc_ref.update({
                'points': points,
                'updated_at': firestore.SERVER_TIMESTAMP
            })
            
            logger.info(f"Added point to zone {zone_id}")
            return True
        except Exception as e:
            logger.error(f"Error adding point to zone {zone_id}: {e}")
            return False
    
    def remove_point_from_zone(self, zone_id: str, point_index: int) -> bool:
        """
        Remove a point from a zone
        
        Args:
            zone_id: Firebase document ID
            point_index: Index of point to remove
            
        Returns:
            True if successful, False otherwise
        """
        try:
            doc_ref = self.collection.document(zone_id)
            doc = doc_ref.get()
            
            if not doc.exists:
                logger.error(f"Zone {zone_id} not found")
                return False
            
            data = doc.to_dict()
            points = data.get('points', {})
            
            # Remove the point
            if str(point_index) in points:
                del points[str(point_index)]
                
                # Re-index remaining points
                sorted_points = sorted([(int(k), v) for k, v in points.items()])
                reindexed_points = {str(i): v for i, (_, v) in enumerate(sorted_points)}
                
                doc_ref.update({
                    'points': reindexed_points,
                    'updated_at': firestore.SERVER_TIMESTAMP
                })
                
                logger.info(f"Removed point {point_index} from zone {zone_id}")
                return True
            else:
                logger.error(f"Point {point_index} not found in zone {zone_id}")
                return False
        except Exception as e:
            logger.error(f"Error removing point from zone {zone_id}: {e}")
            return False
    
    def get_zones_by_type(self, zone_type: str) -> List[Dict]:
        """
        Get all zones of a specific type
        
        Args:
            zone_type: Zone type (PARKING, NO_PARKING, etc.)
            
        Returns:
            List of zones
        """
        try:
            query = self.collection.where('zone_type', '==', zone_type).where('is_active', '==', True)
            docs = query.stream()
            
            zones = []
            for doc in docs:
                data = doc.to_dict()
                data['firebase_id'] = doc.id
                zones.append(data)
            
            return zones
        except Exception as e:
            logger.error(f"Error fetching zones by type {zone_type}: {e}")
            return []