"""
Firebase Service for Payments
Handles reading payment data from the Firebase Firestore 'payments' collection.
"""

from firebase_admin import firestore
from datetime import datetime
from typing import List, Dict, Optional
import logging

logger = logging.getLogger(__name__)

class PaymentFirebaseService:
    """Service class for Firebase payment operations"""

    def __init__(self):
        self.db = firestore.client()
        self.collection = self.db.collection('payments') # Assumes collection name is 'payments'

    def _convert_timestamp(self, data: Dict, doc_id: str) -> Optional[datetime]:
        """
        Helper to find and convert various timestamp formats to Python datetime.
        Handles:
        - datetime objects (including DatetimeWithNanoseconds from Firestore)
        - Firestore Timestamp objects (with to_datetime() method)
        - ISO 8601 date strings (e.g., "2025-01-15T10:30:00Z")
        - Unix timestamps in seconds (e.g., 1704067800)
        - Unix timestamps in milliseconds (e.g., 1704067800000)
        """
        # List of potential field names for the timestamp
        possible_field_names = ['paymentDate', 'payment_date', 'timestamp', 'created_at', 'date', 'createdAt']
        
        for field_name in possible_field_names:
            if field_name not in data:
                continue
                
            potential_ts = data[field_name]
            
            # Skip None or empty values
            if potential_ts is None or potential_ts == '':
                continue
            
            # Method 1: Already a datetime object (includes DatetimeWithNanoseconds)
            # This MUST be checked FIRST before checking for to_datetime() method
            if isinstance(potential_ts, datetime):
                logger.debug(f"✓ Field '{field_name}' is a datetime object for payment {doc_id}")
                return potential_ts
            
            # Method 2: Firestore Timestamp object (has to_datetime() method)
            if hasattr(potential_ts, 'to_datetime') and callable(potential_ts.to_datetime):
                try:
                    converted_dt = potential_ts.to_datetime()
                    logger.debug(f"✓ Converted Firestore Timestamp field '{field_name}' for payment {doc_id}")
                    return converted_dt
                except Exception as conv_err:
                    logger.error(f"Error converting Firestore Timestamp field '{field_name}' for payment {doc_id}: {conv_err}", exc_info=True)
                    continue
            
            # Method 3: String (ISO 8601 format or similar)
            if isinstance(potential_ts, str):
                # Try various string formats
                string_formats = [
                    '%Y-%m-%dT%H:%M:%S.%fZ',      # 2025-01-15T10:30:00.123Z
                    '%Y-%m-%dT%H:%M:%SZ',          # 2025-01-15T10:30:00Z
                    '%Y-%m-%dT%H:%M:%S.%f',        # 2025-01-15T10:30:00.123
                    '%Y-%m-%dT%H:%M:%S',           # 2025-01-15T10:30:00
                    '%Y-%m-%d %H:%M:%S',           # 2025-01-15 10:30:00
                    '%Y-%m-%d',                     # 2025-01-15
                    '%m/%d/%Y %H:%M:%S',           # 01/15/2025 10:30:00
                    '%m/%d/%Y',                     # 01/15/2025
                ]
                
                for date_format in string_formats:
                    try:
                        converted_dt = datetime.strptime(potential_ts, date_format)
                        logger.debug(f"✓ Converted string field '{field_name}' (format: {date_format}) for payment {doc_id}")
                        return converted_dt
                    except ValueError:
                        continue
                
                # If none of the formats worked, log the actual value
                logger.warning(f"Could not parse date string '{potential_ts}' in field '{field_name}' for payment {doc_id}")
                continue
            
            # Method 4: Unix timestamp (number)
            if isinstance(potential_ts, (int, float)):
                try:
                    # Check if it's in milliseconds (typical for JavaScript timestamps)
                    if potential_ts > 10000000000:  # If timestamp is > year 2286 in seconds, it's likely milliseconds
                        converted_dt = datetime.fromtimestamp(potential_ts / 1000.0)
                        logger.debug(f"✓ Converted Unix timestamp (ms) field '{field_name}' for payment {doc_id}")
                    else:
                        converted_dt = datetime.fromtimestamp(potential_ts)
                        logger.debug(f"✓ Converted Unix timestamp (s) field '{field_name}' for payment {doc_id}")
                    return converted_dt
                except (ValueError, OSError) as conv_err:
                    logger.error(f"Error converting numeric timestamp field '{field_name}' (value: {potential_ts}) for payment {doc_id}: {conv_err}")
                    continue
            
            # If we reach here, the field exists but is in an unrecognized format
            logger.warning(f"Field '{field_name}' exists but is in unrecognized format (type: {type(potential_ts).__name__}) for payment {doc_id}")

        # No valid timestamp found in any field
        logger.warning(f"No valid timestamp found in payment {doc_id}. Tried: {possible_field_names}. Available fields: {list(data.keys())}")
        return None

    def get_payment(self, payment_id: str) -> Optional[Dict]:
        """
        Get a single payment record from Firebase.

        Args:
            payment_id: Firebase document ID for the payment.

        Returns:
            Dictionary with payment data or None if not found.
        """
        try:
            doc_ref = self.collection.document(payment_id)
            doc = doc_ref.get()

            if doc.exists:
                data = doc.to_dict()
                data['firebase_id'] = doc.id
                # Convert timestamp to Python datetime using helper
                data['payment_date_dt'] = self._convert_timestamp(data, doc.id)
                return data
            else:
                logger.warning(f"Payment {payment_id} not found in Firebase.")
                return None
        except Exception as e:
            logger.error(f"Error fetching payment {payment_id} from Firebase: {e}", exc_info=True)
            return None

    def list_payments(self, limit: int = 1000, start_after_doc=None, order_by: str = 'paymentDate', direction: str = 'DESCENDING', start_after_timestamp: Optional[datetime] = None) -> List[Dict]:
        """
        List payment records from Firebase, ordered by date descending.

        Args:
            limit: Maximum number of payments to retrieve per call.
            start_after_doc: Firestore document snapshot to start querying after (for pagination).

        Returns:
            List of payment dictionaries.
        """
        query = self.collection
        
        if start_after_timestamp:
                logger.info(f"Querying for payments starting after: {start_after_timestamp}")
                # Firestore query: field > timestamp
                query = query.where(order_by, '>', start_after_timestamp)

        try:
            # Try to order by paymentDate first, but be flexible if it doesn't exist
            try:
                query = self.collection.order_by('paymentDate', direction=firestore.Query.DESCENDING).limit(limit)
            except Exception as order_error:
                logger.warning(f"Cannot order by 'paymentDate', trying 'payment_date': {order_error}")
                try:
                    query = self.collection.order_by('payment_date', direction=firestore.Query.DESCENDING).limit(limit)
                except Exception as order_error2:
                    logger.warning(f"Cannot order by 'payment_date' either, fetching unordered: {order_error2}")
                    query = self.collection.limit(limit)

            if start_after_doc:
                query = query.start_after(start_after_doc)

            docs = query.stream()
            payments = []
            last_doc = None
            for doc in docs:
                data = doc.to_dict()
                data['firebase_id'] = doc.id
                # Convert timestamp using helper method
                data['payment_date_dt'] = self._convert_timestamp(data, doc.id)
                payments.append(data)
                last_doc = doc # Keep track of the last document for potential pagination

            logger.info(f"Fetched {len(payments)} payments from Firebase.")
            return payments

        except Exception as e:
            logger.error(f"Error listing payments from Firebase: {e}", exc_info=True)
            return []

    def get_payments_for_user(self, user_firebase_id: str, limit: int = 100) -> List[Dict]:
        """Gets payments for a specific user."""
        try:
            # Try to query and order by paymentDate
            try:
                query = self.collection.where('uid', '==', user_firebase_id)\
                              .order_by('paymentDate', direction=firestore.Query.DESCENDING)\
                              .limit(limit)
            except Exception as order_error:
                logger.warning(f"Cannot order by 'paymentDate' for user query, trying 'payment_date': {order_error}")
                try:
                    query = self.collection.where('uid', '==', user_firebase_id)\
                                  .order_by('payment_date', direction=firestore.Query.DESCENDING)\
                                  .limit(limit)
                except Exception as order_error2:
                    logger.warning(f"Cannot order by 'payment_date' either, fetching unordered: {order_error2}")
                    query = self.collection.where('uid', '==', user_firebase_id).limit(limit)
            
            docs = query.stream()
            payments = []
            for doc in docs:
                 data = doc.to_dict()
                 data['firebase_id'] = doc.id
                 # Convert timestamp using helper method
                 data['payment_date_dt'] = self._convert_timestamp(data, doc.id)
                 payments.append(data)
            
            logger.info(f"Fetched {len(payments)} payments for user {user_firebase_id}")
            return payments
        except Exception as e:
            logger.error(f"Error fetching payments for user {user_firebase_id}: {e}", exc_info=True)
            return []