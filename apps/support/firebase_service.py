"""
Firebase Service for Support Requests
Handles reading support request data from the Firebase Firestore 'support_requests' collection.
"""

import logging
from typing import List, Dict, Optional
from datetime import datetime
from firebase_admin import firestore

logger = logging.getLogger(__name__)


class SupportFirebaseService:
    """Service class for Firebase support_requests operations"""

    def __init__(self):
        self.db = firestore.client()
        self.collection = self.db.collection('support_requests')

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
        if isinstance(potential_ts, datetime):
            logger.debug(f"✓ Field '{field_name}' is a datetime object for support request {doc_id}")
            return potential_ts

        # Method 2: Firestore Timestamp object (has to_datetime() method)
        if hasattr(potential_ts, 'to_datetime') and callable(potential_ts.to_datetime):
            try:
                converted_dt = potential_ts.to_datetime()
                logger.debug(f"✓ Converted Firestore Timestamp field '{field_name}' for support request {doc_id}")
                return converted_dt
            except Exception as conv_err:
                logger.error(f"Error converting Firestore Timestamp field '{field_name}' for support request {doc_id}: {conv_err}", exc_info=True)
                return None

        # Method 3: String (ISO 8601 format or similar)
        if isinstance(potential_ts, str):
            from dateutil import parser as dateutil_parser
            try:
                converted_dt = dateutil_parser.parse(potential_ts)
                logger.debug(f"✓ Converted string field '{field_name}' for support request {doc_id}")
                return converted_dt
            except (ValueError, TypeError, dateutil_parser.ParserError) as e:
                logger.warning(f"Could not parse date string '{potential_ts}' in field '{field_name}' for support request {doc_id}: {e}")
                return None

        # Method 4: Unix timestamp (number)
        if isinstance(potential_ts, (int, float)):
            try:
                # Check if it's in milliseconds
                if potential_ts > 10000000000:
                    converted_dt = datetime.fromtimestamp(potential_ts / 1000.0)
                    logger.debug(f"✓ Converted Unix timestamp (ms) field '{field_name}' for support request {doc_id}")
                else:
                    converted_dt = datetime.fromtimestamp(potential_ts)
                    logger.debug(f"✓ Converted Unix timestamp (s) field '{field_name}' for support request {doc_id}")
                return converted_dt
            except (ValueError, OSError) as conv_err:
                logger.error(f"Error converting numeric timestamp field '{field_name}' (value: {potential_ts}) for support request {doc_id}: {conv_err}")
                return None

        logger.warning(f"Field '{field_name}' exists but is in unrecognized format (type: {type(potential_ts).__name__}) for support request {doc_id}")
        return None

    def get_support_request(self, request_id: str) -> Optional[Dict]:
        """
        Get a single support request from Firebase.

        Args:
            request_id: Firebase document ID for the support request.

        Returns:
            Dictionary with support request data or None if not found.
        """
        try:
            doc_ref = self.collection.document(request_id)
            doc = doc_ref.get()

            if doc.exists:
                data = doc.to_dict()
                data['firebase_id'] = doc.id

                # Convert timestamp to datetime
                data['submission_datetime'] = self._convert_timestamp(data, doc.id, 'timestamp')

                return data
            else:
                logger.warning(f"Support request {request_id} not found in Firebase.")
                return None
        except Exception as e:
            logger.error(f"Error fetching support request {request_id} from Firebase: {e}", exc_info=True)
            return None

    def list_support_requests(self, limit: int = 1000, start_after_doc=None, order_by: str = 'timestamp', direction: str = 'DESCENDING') -> List[Dict]:
        """
        List support requests from Firebase, ordered by a specified field.

        Args:
            limit: Maximum number of support requests to retrieve per call.
            start_after_doc: Firestore document snapshot to start querying after (for pagination).
            order_by: Field to order by (e.g., 'timestamp', 'status').
            direction: Direction to order ('ASCENDING' or 'DESCENDING').

        Returns:
            List of support request dictionaries.
        """
        try:
            query = self.collection

            # Apply ordering
            order_direction = firestore.Query.DESCENDING if direction.upper() == 'DESCENDING' else firestore.Query.ASCENDING
            try:
                query = query.order_by(order_by, direction=order_direction)
            except Exception as order_error:
                logger.warning(f"Cannot order support requests by '{order_by}'. Fetching unordered. Error: {order_error}")

            # Apply limit
            query = query.limit(limit)

            # Apply pagination if start_after_doc is provided
            if start_after_doc:
                query = query.start_after(start_after_doc)

            docs = query.stream()
            support_requests = []
            last_doc = None
            for doc in docs:
                data = doc.to_dict()
                data['firebase_id'] = doc.id

                # Convert timestamp to datetime
                data['submission_datetime'] = self._convert_timestamp(data, doc.id, 'timestamp')

                support_requests.append(data)
                last_doc = doc  # Keep track for pagination

            logger.info(f"Fetched {len(support_requests)} support requests from Firebase.")
            return support_requests

        except Exception as e:
            logger.error(f"Error listing support requests from Firebase: {e}", exc_info=True)
            return []

    def get_support_requests_for_customer(self, customer_firebase_id: str, limit: int = 100) -> List[Dict]:
        """Gets support requests for a specific customer."""
        try:
            query = self.collection.where('userId', '==', customer_firebase_id)\
                          .order_by('timestamp', direction=firestore.Query.DESCENDING)\
                          .limit(limit)

            docs = query.stream()
            support_requests = []
            for doc in docs:
                data = doc.to_dict()
                data['firebase_id'] = doc.id

                # Convert timestamp
                data['submission_datetime'] = self._convert_timestamp(data, doc.id, 'timestamp')

                support_requests.append(data)

            logger.info(f"Fetched {len(support_requests)} support requests for customer {customer_firebase_id}")
            return support_requests
        except Exception as e:
            logger.error(f"Error fetching support requests for customer {customer_firebase_id}: {e}", exc_info=True)
            return []

    def get_support_requests_by_status(self, status: str, limit: int = 100) -> List[Dict]:
        """Gets support requests by status."""
        try:
            query = self.collection.where('status', '==', status)\
                          .order_by('timestamp', direction=firestore.Query.DESCENDING)\
                          .limit(limit)

            docs = query.stream()
            support_requests = []
            for doc in docs:
                data = doc.to_dict()
                data['firebase_id'] = doc.id

                # Convert timestamp
                data['submission_datetime'] = self._convert_timestamp(data, doc.id, 'timestamp')

                support_requests.append(data)

            logger.info(f"Fetched {len(support_requests)} support requests with status '{status}'")
            return support_requests
        except Exception as e:
            logger.error(f"Error fetching support requests by status '{status}': {e}", exc_info=True)
            return []

    def get_support_requests_by_priority(self, priority: str, limit: int = 100) -> List[Dict]:
        """Gets support requests by priority."""
        try:
            query = self.collection.where('priority', '==', priority)\
                          .order_by('timestamp', direction=firestore.Query.DESCENDING)\
                          .limit(limit)

            docs = query.stream()
            support_requests = []
            for doc in docs:
                data = doc.to_dict()
                data['firebase_id'] = doc.id

                # Convert timestamp
                data['submission_datetime'] = self._convert_timestamp(data, doc.id, 'timestamp')

                support_requests.append(data)

            logger.info(f"Fetched {len(support_requests)} support requests with priority '{priority}'")
            return support_requests
        except Exception as e:
            logger.error(f"Error fetching support requests by priority '{priority}': {e}", exc_info=True)
            return []