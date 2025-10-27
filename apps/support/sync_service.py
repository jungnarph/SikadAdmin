"""
Support Request Sync Service
Syncs support request data from Firebase support_requests collection to the PostgreSQL SupportRequest model.
"""
import logging
from datetime import datetime
from django.utils.timezone import make_aware, is_aware
from django.apps import apps
from dateutil import parser as dateutil_parser

from .firebase_service import SupportFirebaseService
from .models import SupportRequest

# String references for related models
CUSTOMER_MODEL_PATH = 'customers.Customer'

logger = logging.getLogger(__name__)


class SupportSyncService:
    """Service to sync support requests from Firebase to PostgreSQL"""

    def __init__(self):
        self.firebase_service = SupportFirebaseService()
        self.CustomerModel = apps.get_model(CUSTOMER_MODEL_PATH.split('.')[0], CUSTOMER_MODEL_PATH.split('.')[1])

    def _parse_firebase_timestamp(self, timestamp_data, request_id, field_name):
        """
        Safely parse various timestamp formats from Firebase.

        IMPORTANT: Check for datetime objects FIRST before other types.
        Firebase often returns DatetimeWithNanoseconds which is a datetime subclass.
        """
        if not timestamp_data:
            return None

        # Method 1: Already a datetime object (includes DatetimeWithNanoseconds)
        if isinstance(timestamp_data, datetime):
            logger.debug(f"✓ Field '{field_name}' is already a datetime object for support request {request_id}")
            # Ensure it's timezone-aware
            if not is_aware(timestamp_data):
                timestamp_data = make_aware(timestamp_data)
            return timestamp_data

        # Method 2: Firestore Timestamp object
        if hasattr(timestamp_data, 'to_datetime') and callable(timestamp_data.to_datetime):
            try:
                dt = timestamp_data.to_datetime()
                if not is_aware(dt):
                    dt = make_aware(dt)
                logger.debug(f"✓ Converted Firestore Timestamp for support request {request_id}, field {field_name}")
                return dt
            except Exception as e:
                logger.error(f"Error converting Firestore Timestamp for support request {request_id}, field {field_name}: {e}")
                return None

        # Method 3: String format
        if isinstance(timestamp_data, str):
            try:
                dt = dateutil_parser.parse(timestamp_data)
                if not is_aware(dt):
                    dt = make_aware(dt)
                logger.debug(f"✓ Converted string timestamp for support request {request_id}, field {field_name}")
                return dt
            except (ValueError, TypeError, dateutil_parser.ParserError) as e:
                logger.warning(f"Could not parse date string '{timestamp_data}' for support request {request_id}, field {field_name}: {e}")
                return None

        # Method 4: Numeric (Unix timestamp)
        if isinstance(timestamp_data, (int, float)):
            try:
                if timestamp_data > 10000000000:  # Likely milliseconds
                    dt = datetime.fromtimestamp(timestamp_data / 1000.0)
                else:  # Likely seconds
                    dt = datetime.fromtimestamp(timestamp_data)
                dt = make_aware(dt)
                logger.debug(f"✓ Converted numeric timestamp for support request {request_id}, field {field_name}")
                return dt
            except Exception as e:
                logger.error(f"Error converting numeric timestamp {timestamp_data} for support request {request_id}, field {field_name}: {e}")
                return None

        logger.warning(f"Unrecognized timestamp format for support request {request_id}, field {field_name}: type {type(timestamp_data).__name__}")
        return None

    def _map_firebase_to_django(self, firebase_data: dict) -> dict:
        """Maps Firebase support_requests data to Django SupportRequest model fields."""
        mapped_data = {}
        request_id = firebase_data.get('firebase_id', 'unknown')

        # --- Relationships ---
        customer_firebase_id = firebase_data.get('userId')
        if customer_firebase_id:
            try:
                customer_instance = self.CustomerModel.objects.filter(firebase_id=customer_firebase_id).first()
                mapped_data['customer'] = customer_instance
                if not customer_instance:
                    logger.warning(f"Customer {customer_firebase_id} not found in DB for support request {request_id}.")
            except Exception as e:
                logger.error(f"Error linking customer {customer_firebase_id} for support request {request_id}: {e}")
        else:
            logger.warning(f"No userId found for support request {request_id}")

        # --- Request Details ---
        mapped_data['issue'] = firebase_data.get('issue', '')
        mapped_data['response'] = firebase_data.get('response', '')
        mapped_data['app_version'] = firebase_data.get('appVersion', '')
        mapped_data['test_id'] = firebase_data.get('testId', '')

        # --- Status and Priority ---
        status = firebase_data.get('status', 'pending').lower()
        mapped_data['status'] = status if status in dict(SupportRequest.STATUS_CHOICES) else 'pending'

        priority = firebase_data.get('priority', 'medium').lower()
        mapped_data['priority'] = priority if priority in dict(SupportRequest.PRIORITY_CHOICES) else 'medium'

        # --- Assignment ---
        mapped_data['assigned_to'] = firebase_data.get('assignedTo', '')

        # --- Timestamps ---
        mapped_data['submission_time'] = firebase_data.get('submissionTime', '')

        # Parse timestamp
        timestamp = firebase_data.get('timestamp')
        if timestamp:
            mapped_data['timestamp'] = timestamp
            # Convert timestamp to datetime
            submission_dt = firebase_data.get('submission_datetime')  # Pre-parsed from firebase_service
            if not submission_dt:
                submission_dt = self._parse_firebase_timestamp(timestamp, request_id, 'timestamp')
            mapped_data['submission_datetime'] = submission_dt
        else:
            logger.warning(f"No timestamp found for support request {request_id}")

        return mapped_data

    def sync_single_support_request(self, request_id: str, firebase_data: dict = None) -> tuple:
        """
        Sync a single support request from Firebase to PostgreSQL.
        Can optionally accept pre-fetched firebase_data.

        Returns:
            tuple: (success: bool, created: bool)
        """
        try:
            if not firebase_data:
                # Fetch from Firebase
                firebase_data = self.firebase_service.get_support_request(request_id)

            if not firebase_data:
                logger.warning(f"Support request {request_id} not found in Firebase (or fetch failed).")
                return False, False

            # Ensure firebase_id is in the data dict
            firebase_data['firebase_id'] = request_id

            defaults = self._map_firebase_to_django(firebase_data)

            # Update or create in PostgreSQL
            support_request, created = SupportRequest.objects.update_or_create(
                firebase_id=request_id,
                defaults=defaults
            )

            action = "created" if created else "updated"
            logger.info(
                f"Support request {request_id} {action} in PostgreSQL. "
                f"Status: {defaults.get('status')}, "
                f"Priority: {defaults.get('priority')}, "
                f"Customer: {defaults.get('customer')}"
            )
            return True, created

        except Exception as e:
            logger.error(f"Error syncing support request {request_id}: {e}", exc_info=True)
            return False, False

    def sync_all_support_requests(self, limit: int = 1000) -> dict:
        """
        Sync multiple support requests from Firebase to PostgreSQL.
        """
        stats = {'total': 0, 'created': 0, 'updated': 0, 'failed': 0, 'processed': 0}
        try:
            logger.info(f"Starting bulk support request sync with limit {limit}")
            support_requests_data = self.firebase_service.list_support_requests(limit=limit)

            stats['total'] = len(support_requests_data)
            logger.info(f"Fetched {stats['total']} support requests from Firebase. Beginning sync...")

            for request_data in support_requests_data:
                request_id = request_data.get('firebase_id')
                if request_id:
                    success, created = self.sync_single_support_request(request_id, request_data)
                    if success:
                        if created:
                            stats['created'] += 1
                        else:
                            stats['updated'] += 1
                        stats['processed'] += 1
                    else:
                        stats['failed'] += 1
                else:
                    logger.warning("Found support request data without firebase_id during bulk sync.")
                    stats['failed'] += 1

            logger.info(f"Support request sync completed: Processed {stats['processed']}, Failed {stats['failed']} out of {stats['total']} fetched.")
            return stats

        except Exception as e:
            logger.error(f"Error during bulk support request sync: {e}", exc_info=True)
            return stats

    def sync_support_requests_for_customer(self, customer_firebase_id: str, limit: int = 100) -> dict:
        """Syncs support requests for a specific customer."""
        stats = {'total': 0, 'processed': 0, 'failed': 0, 'created': 0, 'updated': 0}
        try:
            logger.info(f"Starting support request sync for customer {customer_firebase_id} with limit {limit}")

            support_requests_data = self.firebase_service.get_support_requests_for_customer(customer_firebase_id, limit=limit)
            stats['total'] = len(support_requests_data)

            logger.info(f"Fetched {stats['total']} support requests for customer {customer_firebase_id}")

            for request_data in support_requests_data:
                request_id = request_data.get('firebase_id')
                if request_id:
                    success, created = self.sync_single_support_request(request_id, request_data)
                    if success:
                        if created:
                            stats['created'] += 1
                        else:
                            stats['updated'] += 1
                        stats['processed'] += 1
                    else:
                        stats['failed'] += 1
                else:
                    stats['failed'] += 1

            logger.info(f"Synced support requests for customer {customer_firebase_id}: Processed {stats['processed']}, Failed {stats['failed']}")
            return stats
        except Exception as e:
            logger.error(f"Error syncing support requests for customer {customer_firebase_id}: {e}", exc_info=True)
            return stats

    def sync_support_requests_by_status(self, status: str, limit: int = 100) -> dict:
        """Syncs support requests with a specific status."""
        stats = {'total': 0, 'processed': 0, 'failed': 0, 'created': 0, 'updated': 0}
        try:
            logger.info(f"Starting support request sync for status '{status}' with limit {limit}")

            support_requests_data = self.firebase_service.get_support_requests_by_status(status, limit=limit)
            stats['total'] = len(support_requests_data)

            logger.info(f"Fetched {stats['total']} support requests with status '{status}'")

            for request_data in support_requests_data:
                request_id = request_data.get('firebase_id')
                if request_id:
                    success, created = self.sync_single_support_request(request_id, request_data)
                    if success:
                        if created:
                            stats['created'] += 1
                        else:
                            stats['updated'] += 1
                        stats['processed'] += 1
                    else:
                        stats['failed'] += 1
                else:
                    stats['failed'] += 1

            logger.info(f"Synced support requests by status '{status}': Processed {stats['processed']}, Failed {stats['failed']}")
            return stats
        except Exception as e:
            logger.error(f"Error syncing support requests by status '{status}': {e}", exc_info=True)
            return stats