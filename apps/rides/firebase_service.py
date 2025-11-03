# New file: apps/rides/firebase_service.py
"""
Firebase Service for Rides
Handles reading ride data from the Firebase Firestore 'ride_logs' collection.
"""

import logging
from typing import List, Dict, Optional
from datetime import datetime
from firebase_admin import firestore

logger = logging.getLogger(__name__)

class RideFirebaseService:
    """Service class for Firebase ride_logs operations"""

    def __init__(self):
        self.db = firestore.client()
        self.collection = self.db.collection('ride_logs')

    def _convert_timestamp(self, data: Dict, doc_id: str, field_name: str) -> Optional[datetime]:
        """
        Helper to convert various timestamp formats to Python datetime.
        Handles:
        - datetime objects (including DatetimeWithNanoseconds from Firestore)
        - Firestore Timestamp objects (with to_datetime() method)
        - ISO 8601 date strings
        - Unix timestamps in seconds or milliseconds
        """
        if field_name not in data:
            return None
            
        potential_ts = data[field_name]
        
        # Skip None or empty values
        if potential_ts is None or potential_ts == '':
            return None
        
        # Method 1: Already a datetime object (includes DatetimeWithNanoseconds)
        # This MUST be checked FIRST before checking for to_datetime() method
        if isinstance(potential_ts, datetime):
            logger.debug(f"✓ Field '{field_name}' is a datetime object for ride {doc_id}")
            return potential_ts
        
        # Method 2: Firestore Timestamp object (has to_datetime() method)
        if hasattr(potential_ts, 'to_datetime') and callable(potential_ts.to_datetime):
            try:
                converted_dt = potential_ts.to_datetime()
                logger.debug(f"✓ Converted Firestore Timestamp field '{field_name}' for ride {doc_id}")
                return converted_dt
            except Exception as conv_err:
                logger.error(f"Error converting Firestore Timestamp field '{field_name}' for ride {doc_id}: {conv_err}", exc_info=True)
                return None
        
        # Method 3: String (ISO 8601 format or similar)
        if isinstance(potential_ts, str):
            from dateutil import parser as dateutil_parser
            try:
                converted_dt = dateutil_parser.parse(potential_ts)
                logger.debug(f"✓ Converted string field '{field_name}' for ride {doc_id}")
                return converted_dt
            except (ValueError, TypeError, dateutil_parser.ParserError) as e:
                logger.warning(f"Could not parse date string '{potential_ts}' in field '{field_name}' for ride {doc_id}: {e}")
                return None
        
        # Method 4: Unix timestamp (number)
        if isinstance(potential_ts, (int, float)):
            try:
                # Check if it's in milliseconds
                if potential_ts > 10000000000:
                    converted_dt = datetime.fromtimestamp(potential_ts / 1000.0)
                    logger.debug(f"✓ Converted Unix timestamp (ms) field '{field_name}' for ride {doc_id}")
                else:
                    converted_dt = datetime.fromtimestamp(potential_ts)
                    logger.debug(f"✓ Converted Unix timestamp (s) field '{field_name}' for ride {doc_id}")
                return converted_dt
            except (ValueError, OSError) as conv_err:
                logger.error(f"Error converting numeric timestamp field '{field_name}' (value: {potential_ts}) for ride {doc_id}: {conv_err}")
                return None
        
        logger.warning(f"Field '{field_name}' exists but is in unrecognized format (type: {type(potential_ts).__name__}) for ride {doc_id}")
        return None

    def get_ride(self, ride_id: str) -> Optional[Dict]:
        """
        Get a single ride log from Firebase.

        Args:
            ride_id: Firebase document ID for the ride log.

        Returns:
            Dictionary with ride data or None if not found.
        """
        try:
            doc_ref = self.collection.document(ride_id)
            doc = doc_ref.get()

            if doc.exists:
                data = doc.to_dict()
                data['firebase_id'] = doc.id
                
                # Convert timestamps using helper method
                data['startTime_dt'] = self._convert_timestamp(data, doc.id, 'startTime')
                data['endTime_dt'] = self._convert_timestamp(data, doc.id, 'endTime')
                
                return data
            else:
                logger.warning(f"Ride log {ride_id} not found in Firebase.")
                return None
        except Exception as e:
            logger.error(f"Error fetching ride log {ride_id} from Firebase: {e}", exc_info=True)
            return None

    def list_rides(self, limit: int = 1000, start_after_doc=None, order_by: str = 'startTime', direction: str = 'DESCENDING', start_after_timestamp: Optional[datetime] = None) -> List[Dict]:
        """
        List ride logs from Firebase, ordered by a specified field.

        Args:
            limit: Maximum number of rides to retrieve per call.
            start_after_doc: Firestore document snapshot to start querying after (for pagination).
            order_by: Field to order by (e.g., 'startTime', 'endTime').
            direction: Direction to order ('ASCENDING' or 'DESCENDING').

        Returns:
            List of ride dictionaries.
        """
        try:
            query = self.collection
            
            if start_after_timestamp:
                logger.info(f"Querying for rides starting after: {start_after_timestamp}")
                # Firestore query: field > timestamp
                query = query.where(order_by, '>', start_after_timestamp)

            # Apply ordering
            order_direction = firestore.Query.DESCENDING if direction.upper() == 'DESCENDING' else firestore.Query.ASCENDING
            try:
                query = query.order_by(order_by, direction=order_direction)
            except Exception as order_error:
                logger.warning(f"Cannot order rides by '{order_by}'. Fetching unordered. Error: {order_error}")

            # Apply limit
            query = query.limit(limit)

            # Apply pagination if start_after_doc is provided
            if start_after_doc:
                query = query.start_after(start_after_doc)

            docs = query.stream()
            rides = []
            last_doc = None
            for doc in docs:
                data = doc.to_dict()
                data['firebase_id'] = doc.id
                
                # Convert timestamps using helper method
                data['startTime_dt'] = self._convert_timestamp(data, doc.id, 'startTime')
                data['endTime_dt'] = self._convert_timestamp(data, doc.id, 'endTime')
                
                rides.append(data)
                last_doc = doc # Keep track for pagination

            logger.info(f"Fetched {len(rides)} ride logs from Firebase.")
            return rides

        except Exception as e:
            logger.error(f"Error listing ride logs from Firebase: {e}", exc_info=True)
            return []

    def get_rides_for_customer(self, customer_firebase_id: str, limit: int = 100) -> List[Dict]:
        """Gets rides for a specific customer."""
        try:
            query = self.collection.where('userId', '==', customer_firebase_id)\
                          .order_by('startTime', direction=firestore.Query.DESCENDING)\
                          .limit(limit)
            
            docs = query.stream()
            rides = []
            for doc in docs:
                data = doc.to_dict()
                data['firebase_id'] = doc.id
                
                # Convert timestamps
                data['startTime_dt'] = self._convert_timestamp(data, doc.id, 'startTime')
                data['endTime_dt'] = self._convert_timestamp(data, doc.id, 'endTime')
                
                rides.append(data)
            
            logger.info(f"Fetched {len(rides)} rides for customer {customer_firebase_id}")
            return rides
        except Exception as e:
            logger.error(f"Error fetching rides for customer {customer_firebase_id}: {e}", exc_info=True)
            return []

    def get_rides_for_bike(self, bike_firebase_id: str, limit: int = 100) -> List[Dict]:
        """Gets rides for a specific bike."""
        try:
            query = self.collection.where('bikeId', '==', bike_firebase_id)\
                          .order_by('startTime', direction=firestore.Query.DESCENDING)\
                          .limit(limit)
            
            docs = query.stream()
            rides = []
            for doc in docs:
                data = doc.to_dict()
                data['firebase_id'] = doc.id
                
                # Convert timestamps
                data['startTime_dt'] = self._convert_timestamp(data, doc.id, 'startTime')
                data['endTime_dt'] = self._convert_timestamp(data, doc.id, 'endTime')
                
                rides.append(data)
            
            logger.info(f"Fetched {len(rides)} rides for bike {bike_firebase_id}")
            return rides
        except Exception as e:
            logger.error(f"Error fetching rides for bike {bike_firebase_id}: {e}", exc_info=True)
            return []