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
        """Helper to find and convert Firestore Timestamp to Python datetime."""
        # List of potential field names for the timestamp
        possible_field_names = ['paymentDate', 'payment_date', 'timestamp', 'created_at', 'date']
        timestamp_field = None
        found_field_name = None

        for field_name in possible_field_names:
            if field_name in data:
                potential_ts = data[field_name]
                # Check if it's a Firestore Timestamp object
                if hasattr(potential_ts, 'to_datetime') and callable(potential_ts.to_datetime):
                    timestamp_field = potential_ts
                    found_field_name = field_name
                    break # Found a valid timestamp

        if timestamp_field:
            try:
                return timestamp_field.to_datetime()
            except Exception as conv_err:
                logger.error(f"Error converting timestamp field '{found_field_name}' for payment {doc_id}: {conv_err}", exc_info=True)
                return None
        else:
            # logger.warning(f"No valid Firestore Timestamp field found in payment {doc_id} using names: {possible_field_names}")
            # Optionally try parsing if it might be a string - add specific formats if needed
            # For now, just return None if no Timestamp object is found.
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
                # Convert Firestore Timestamp to Python datetime if necessary
                if 'paymentDate' in data and hasattr(data['paymentDate'], 'to_datetime'):
                    data['payment_date_dt'] = data['paymentDate'].to_datetime()
                return data
            else:
                logger.warning(f"Payment {payment_id} not found in Firebase.")
                return None
        except Exception as e:
            logger.error(f"Error fetching payment {payment_id} from Firebase: {e}", exc_info=True)
            return None

    def list_payments(self, limit: int = 1000, start_after_doc=None) -> List[Dict]:
        """
        List payment records from Firebase, ordered by date descending.

        Args:
            limit: Maximum number of payments to retrieve per call.
            start_after_doc: Firestore document snapshot to start querying after (for pagination).

        Returns:
            List of payment dictionaries.
        """
        try:
            query = self.collection.order_by('paymentDate', direction=firestore.Query.DESCENDING).limit(limit)

            if start_after_doc:
                query = query.start_after(start_after_doc)

            docs = query.stream()
            payments = []
            last_doc = None
            for doc in docs:
                data = doc.to_dict()
                data['firebase_id'] = doc.id
                # Convert Firestore Timestamp
                if 'paymentDate' in data and hasattr(data['paymentDate'], 'to_datetime'):
                    data['payment_date_dt'] = data['paymentDate'].to_datetime()
                payments.append(data)
                last_doc = doc # Keep track of the last document for potential pagination

            # logger.info(f"Fetched {len(payments)} payments from Firebase.")
            # Return payments and the last document fetched
            # You might need a more robust pagination strategy for large datasets
            return payments # For simplicity, just returning the list for now

        except Exception as e:
            logger.error(f"Error listing payments from Firebase: {e}", exc_info=True)
            return []

    # Add more methods if needed, e.g., querying by user ID, date range, etc.
    def get_payments_for_user(self, user_firebase_id: str, limit: int = 100) -> List[Dict]:
        """Gets payments for a specific user."""
        try:
            query = self.collection.where('uid', '==', user_firebase_id)\
                          .order_by('paymentDate', direction=firestore.Query.DESCENDING)\
                          .limit(limit)
            docs = query.stream()
            payments = []
            for doc in docs:
                 data = doc.to_dict()
                 data['firebase_id'] = doc.id
                 if 'paymentDate' in data and hasattr(data['paymentDate'], 'to_datetime'):
                     data['payment_date_dt'] = data['paymentDate'].to_datetime()
                 payments.append(data)
            return payments
        except Exception as e:
            logger.error(f"Error fetching payments for user {user_firebase_id}: {e}", exc_info=True)
            return []
