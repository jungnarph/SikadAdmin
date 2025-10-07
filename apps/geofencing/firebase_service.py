"""
Firebase Service for Geofencing - ARRAY FORMAT
Handles all Firebase Firestore operations for geofence zones
Updated to use ARRAY format for polygon points instead of MAP
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
    
    def _extract_points_from_array(self, points_data: list) -> List[Dict]:
        """
        Extract points from ARRAY format
        
        Args:
            points_data: List of point objects from Firebase
            
        Returns:
            List of dictionaries with index, latitude, longitude
        """
        points = []
        
        if not points_data or not isinstance(points_data, list):
            return points
        
        for index, point_data in enumerate(points_data):
            try:
                if 'location' in point_data:
                    # GeoPoint format
                    points.append({
                        'index': index,
                        'latitude': point_data['location'].latitude,
                        'longitude': point_data['location'].longitude
                    })
                elif 'latitude' in point_data and 'longitude' in point_data:
                    # Already in lat/lng format
                    points.append({
                        'index': index,
                        'latitude': point_data['latitude'],
                        'longitude': point_data['longitude']
                    })
            except Exception as e:
                logger.warning(f"Error extracting point at index {index}: {e}")
                continue
        
        return points
    
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
                
                # Extract points from ARRAY format
                points = self._extract_points_from_array(data.get('points', []))
                
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
                
                # Extract points from ARRAY format
                points = self._extract_points_from_array(data.get('points', []))
                
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
        Create a new geofence zone in Firebase using ARRAY format
        
        Args:
            zone_id: Document ID for the zone
            zone_data: Dictionary containing zone information
                Required: name, points (list of {latitude, longitude})
                Optional: color_code, is_active
            
        Returns:
            True if successful, False otherwise
        """
        try:
            doc_ref = self.collection.document(zone_id)
            
            # Prepare points in ARRAY format (list)
            points_list = []
            points = zone_data.get('points', [])
            
            for point in points:
                points_list.append({
                    'location': firestore.GeoPoint(
                        latitude=float(point['latitude']),
                        longitude=float(point['longitude'])
                    )
                })
            
            # Prepare zone data
            data = {
                'name': zone_data.get('name'),
                'is_active': zone_data.get('is_active', True),
                'color_code': zone_data.get('color_code', '#3388ff'),
                'points': points_list,  # ARRAY format
                'created_at': firestore.SERVER_TIMESTAMP,
                'updated_at': firestore.SERVER_TIMESTAMP
            }
            
            doc_ref.set(data)
            logger.info(f"Created zone {zone_id} in Firebase with ARRAY format")
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
            
            # Convert points if present (ARRAY format)
            if 'points' in updates:
                points_list = []
                points = updates.pop('points')
                
                for point in points:
                    points_list.append({
                        'location': firestore.GeoPoint(
                            latitude=float(point['latitude']),
                            longitude=float(point['longitude'])
                        )
                    })
                
                updates['points'] = points_list  # ARRAY format
            
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
        Add a new point to an existing zone (ARRAY format)
        
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
            points = data.get('points', [])
            
            # Append new point to array
            new_point = {
                'location': firestore.GeoPoint(
                    latitude=float(latitude),
                    longitude=float(longitude)
                )
            }
            
            # Use arrayUnion for atomic append
            doc_ref.update({
                'points': firestore.ArrayUnion([new_point]),
                'updated_at': firestore.SERVER_TIMESTAMP
            })
            
            logger.info(f"Added point to zone {zone_id}")
            return True
        except Exception as e:
            logger.error(f"Error adding point to zone {zone_id}: {e}")
            return False
    
    def remove_point_from_zone(self, zone_id: str, point_index: int) -> bool:
        """
        Remove a point from a zone (ARRAY format)
        Note: In array format, we need to read, modify, and write the entire array
        
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
            points = data.get('points', [])
            
            # Check if index is valid
            if not (0 <= point_index < len(points)):
                logger.error(f"Invalid point index {point_index} for zone {zone_id}")
                return False
            
            # Remove the point
            points.pop(point_index)
            
            # Update with new array
            doc_ref.update({
                'points': points,
                'updated_at': firestore.SERVER_TIMESTAMP
            })
            
            logger.info(f"Removed point {point_index} from zone {zone_id}")
            return True
        except Exception as e:
            logger.error(f"Error removing point from zone {zone_id}: {e}")
            return False
    
    def update_point_in_zone(self, zone_id: str, point_index: int, latitude: float, longitude: float) -> bool:
        """
        Update a specific point in a zone (ARRAY format)
        
        Args:
            zone_id: Firebase document ID
            point_index: Index of point to update
            latitude: New latitude
            longitude: New longitude
            
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
            points = data.get('points', [])
            
            # Check if index is valid
            if not (0 <= point_index < len(points)):
                logger.error(f"Invalid point index {point_index} for zone {zone_id}")
                return False
            
            # Update the point
            points[point_index] = {
                'location': firestore.GeoPoint(
                    latitude=float(latitude),
                    longitude=float(longitude)
                )
            }
            
            # Update with modified array
            doc_ref.update({
                'points': points,
                'updated_at': firestore.SERVER_TIMESTAMP
            })
            
            logger.info(f"Updated point {point_index} in zone {zone_id}")
            return True
        except Exception as e:
            logger.error(f"Error updating point in zone {zone_id}: {e}")
            return False