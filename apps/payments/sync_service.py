"""
Payment Sync Service
Syncs payment data from Firebase Firestore 'payments' collection to the PostgreSQL Payment model.
"""

from .firebase_service import PaymentFirebaseService
from .models import Payment, CUSTOMER_MODEL_PATH, RIDE_MODEL_PATH
from django.apps import apps # To get models from string paths
from datetime import datetime
import logging
from django.utils.timezone import make_aware # To handle timezone warnings

logger = logging.getLogger(__name__)

class PaymentSyncService:
    """Service to sync payments from Firebase to PostgreSQL"""

    def __init__(self):
        self.firebase_service = PaymentFirebaseService()
        # Get the actual model classes
        self.CustomerModel = apps.get_model(CUSTOMER_MODEL_PATH.split('.')[0], CUSTOMER_MODEL_PATH.split('.')[1])
        self.RideHistoryModel = apps.get_model(RIDE_MODEL_PATH.split('.')[0], RIDE_MODEL_PATH.split('.')[1])

    def _map_firebase_to_django(self, firebase_data: dict) -> dict:
        """Maps Firebase payment data keys/types to Django model fields."""
        mapped_data = {}
        payment_firebase_id = firebase_data.get('firebase_id', 'unknown')

        # Basic fields
        try:
            mapped_data['amount'] = float(firebase_data.get('amount', 0.0)) # Ensure float/Decimal
        except (ValueError, TypeError) as e:
            logger.warning(f"Invalid amount for payment {payment_firebase_id}: {e}. Setting to 0.0")
            mapped_data['amount'] = 0.0

        mapped_data['payment_account_info'] = firebase_data.get('paymentAccount', '')

        # Map status and type, converting to uppercase expected by choices
        fb_status = firebase_data.get('paymentStatus', 'UNKNOWN').upper()
        mapped_data['payment_status'] = fb_status if fb_status in dict(Payment.PAYMENT_STATUS_CHOICES) else 'UNKNOWN'

        fb_type = firebase_data.get('paymentType', 'UNKNOWN').upper()
        mapped_data['payment_type'] = fb_type if fb_type in dict(Payment.PAYMENT_TYPE_CHOICES) else 'UNKNOWN'

        # Handle timestamp (use the pre-converted datetime object if available)
        payment_dt = firebase_data.get('payment_date_dt')
        if payment_dt:
            # Make the datetime timezone-aware if it's naive
            if payment_dt.tzinfo is None or payment_dt.tzinfo.utcoffset(payment_dt) is None:
                 # Assume UTC if no timezone info from Firebase, adjust if needed based on actual data
                 try:
                     mapped_data['payment_date'] = make_aware(payment_dt)
                     logger.debug(f"Converted naive datetime to aware for payment {payment_firebase_id}")
                 except Exception as tz_error:
                     logger.error(f"Error making datetime timezone-aware for payment {payment_firebase_id}: {tz_error}")
                     mapped_data['payment_date'] = None
            else:
                 mapped_data['payment_date'] = payment_dt
        else:
             logger.warning(f"No payment_date_dt found for payment {payment_firebase_id}. Payment date will be NULL in database.")
             mapped_data['payment_date'] = None

        # --- Link Foreign Keys ---
        # Link Customer (using firebase_id)
        customer_firebase_id = firebase_data.get('uid')
        if customer_firebase_id:
            try:
                # Get the Customer instance using firebase_id
                customer_instance = self.CustomerModel.objects.filter(firebase_id=customer_firebase_id).first()
                if customer_instance:
                    mapped_data['customer'] = customer_instance
                    logger.debug(f"Linked payment {payment_firebase_id} to customer {customer_firebase_id}")
                else:
                    logger.warning(f"Customer with firebase_id {customer_firebase_id} not found in Django DB for payment {payment_firebase_id}.")
                    mapped_data['customer'] = None
            except Exception as customer_error:
                logger.error(f"Error linking customer {customer_firebase_id} for payment {payment_firebase_id}: {customer_error}")
                mapped_data['customer'] = None
        else:
            logger.warning(f"No uid (customer ID) found for payment {payment_firebase_id}")
            mapped_data['customer'] = None


        # Link RideHistory (using firebase_id, find based on paymentId in ride_logs)
        # We need the RideHistory Firebase ID which matches the Payment Firebase ID ('firebase_id')
        if payment_firebase_id and payment_firebase_id != 'unknown':
            try:
                # Find RideHistory where its paymentId (from Firebase ride_logs) matches this payment's firebase_id
                # NOTE: This logic depends on how CustomerRideHistory model stores payment references
                # 
                # Option 1: If CustomerRideHistory has a field storing the payment's firebase_id
                # ride_instance = self.RideHistoryModel.objects.filter(payment_firebase_id=payment_firebase_id).first()
                
                # Option 2: If the relationship is via OneToOneField from Payment to RideHistory
                # We need to find the ride where ride.firebase_id matches some payment reference
                
                # For now, attempt to find using the helper function or skip if not implemented
                ride_ids = self._get_ride_ids_for_payment(payment_firebase_id)
                
                if ride_ids:
                    ride_instance = self.RideHistoryModel.objects.filter(firebase_id__in=ride_ids).first()
                    if ride_instance:
                        mapped_data['ride'] = ride_instance
                        logger.debug(f"Linked payment {payment_firebase_id} to ride {ride_instance.firebase_id}")
                    else:
                        logger.debug(f"Ride IDs found for payment {payment_firebase_id} but not in Django DB: {ride_ids}")
                        mapped_data['ride'] = None
                else:
                    # No ride IDs found - this is normal for many payments
                    mapped_data['ride'] = None

            except Exception as ride_link_error:
                logger.error(f"Error linking ride for payment {payment_firebase_id}: {ride_link_error}", exc_info=True)
                mapped_data['ride'] = None
        else:
             mapped_data['ride'] = None

        return mapped_data

    def _get_ride_ids_for_payment(self, payment_firebase_id: str) -> list:
        """
        Helper function to find ride IDs associated with a payment.

        Queries the Firebase 'ride_logs' collection where 'paymentId' == payment_firebase_id
        and returns the document IDs (firebase_ids) of the matching ride logs.

        Returns:
            List of ride firebase_ids associated with this payment
        """
        try:
            # Query Firebase ride_logs collection for rides with this paymentId
            ride_docs = self.firebase_service.db.collection('ride_logs').where('paymentId', '==', payment_firebase_id).stream()
            ride_ids = [doc.id for doc in ride_docs]

            if ride_ids:
                logger.debug(f"Found {len(ride_ids)} ride(s) for payment {payment_firebase_id}: {ride_ids}")

            return ride_ids
        except Exception as e:
            logger.error(f"Error querying ride_logs for payment {payment_firebase_id}: {e}", exc_info=True)
            return []


    def sync_single_payment(self, payment_id: str) -> bool:
        """
        Sync a single payment record from Firebase to PostgreSQL.

        Args:
            payment_id: Firebase document ID of the payment.

        Returns:
            True if successful, False otherwise.
        """
        try:
            firebase_data = self.firebase_service.get_payment(payment_id)
            if not firebase_data:
                logger.error(f"Could not retrieve payment {payment_id} from Firebase")
                return False

            # Map data to Django model fields
            defaults = self._map_firebase_to_django(firebase_data)

            # Check if customer link exists (optional check - remove if payments without customers are valid)
            if not defaults.get('customer'):
                logger.warning(f"Payment {payment_id} has no associated customer. Syncing anyway.")
                # Uncomment the following lines if you want to skip payments without customers:
                # logger.error(f"Skipping payment {payment_id} sync: Associated customer not found in Django DB.")
                # return False

            # Update or create in PostgreSQL
            payment, created = Payment.objects.update_or_create(
                firebase_id=payment_id,
                defaults=defaults
            )

            action = "created" if created else "updated"
            logger.info(f"Payment {payment_id} {action} in PostgreSQL. Amount: {defaults.get('amount')}, Status: {defaults.get('payment_status')}, Date: {defaults.get('payment_date')}")
            return True

        except Exception as e:
            logger.error(f"Error syncing payment {payment_id}: {e}", exc_info=True)
            return False

    def sync_all_payments(self, limit: int = 1000) -> dict:
        """
        Sync multiple payments from Firebase to PostgreSQL.

        Args:
            limit: Maximum number of payments to fetch from Firebase in one go.

        Returns:
            Dictionary with sync statistics.
        """
        stats = {
            'total': 0,
            'processed': 0, # Successfully synced (created or updated)
            'failed': 0
        }
        try:
            logger.info(f"Starting bulk payment sync with limit {limit}")
            
            # Fetch payments from Firebase
            firebase_payments = self.firebase_service.list_payments(limit=limit)
            stats['total'] = len(firebase_payments)
            
            logger.info(f"Fetched {stats['total']} payments from Firebase. Beginning sync...")

            for fb_payment_data in firebase_payments:
                payment_id = fb_payment_data.get('firebase_id')
                if not payment_id:
                    stats['failed'] += 1
                    logger.warning("Found Firebase payment data without an ID. Skipping.")
                    continue

                if self.sync_single_payment(payment_id):
                    stats['processed'] += 1
                else:
                    stats['failed'] += 1

            logger.info(f"Payment sync completed: Processed {stats['processed']}, Failed {stats['failed']} out of {stats['total']} fetched.")
            return stats

        except Exception as e:
            logger.error(f"Error during bulk payment sync: {e}", exc_info=True)
            return stats

    def sync_payments_for_customer(self, customer_firebase_id: str, limit: int = 100) -> dict:
        """
        Syncs recent payments specifically for one customer.
        
        Args:
            customer_firebase_id: Firebase UID of the customer
            limit: Maximum number of payments to fetch
            
        Returns:
            Dictionary with sync statistics
        """
        stats = {'total': 0, 'processed': 0, 'failed': 0}
        try:
            logger.info(f"Starting payment sync for customer {customer_firebase_id} with limit {limit}")
            
            firebase_payments = self.firebase_service.get_payments_for_user(customer_firebase_id, limit=limit)
            stats['total'] = len(firebase_payments)
            
            logger.info(f"Fetched {stats['total']} payments for customer {customer_firebase_id}")
            
            for fb_payment_data in firebase_payments:
                 payment_id = fb_payment_data.get('firebase_id')
                 if payment_id and self.sync_single_payment(payment_id):
                     stats['processed'] += 1
                 else:
                     stats['failed'] += 1
                     
            logger.info(f"Synced payments for customer {customer_firebase_id}: Processed {stats['processed']}, Failed {stats['failed']}")
            return stats
        except Exception as e:
            logger.error(f"Error syncing payments for customer {customer_firebase_id}: {e}", exc_info=True)
            return stats