"""
Django management command to sync payments from Firebase Firestore to PostgreSQL.
Usage: python manage.py sync_payments [--payment-id <id>] [--limit <num>]
"""

from django.core.management.base import BaseCommand, CommandError
from apps.payments.sync_service import PaymentSyncService
import logging

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = 'Sync payments from Firebase Firestore to PostgreSQL database'

    def add_arguments(self, parser):
        parser.add_argument(
            '--payment-id',
            type=str,
            help='Sync only a specific payment by its Firebase document ID.'
        )
        parser.add_argument(
            '--limit',
            type=int,
            default=1000, # Default limit for bulk sync
            help='Maximum number of payments to fetch during bulk sync (default: 1000).'
        )
        parser.add_argument(
            '--customer-id',
            type=str,
            help='Sync payments only for a specific customer by their Firebase UID.'
        )

    def handle(self, *args, **options):
        sync_service = PaymentSyncService()

        payment_id = options.get('payment_id')
        limit = options.get('limit')
        customer_id = options.get('customer_id')

        start_message = "Starting payment sync process..."
        self.stdout.write(self.style.NOTICE(start_message))
        logger.info(start_message)

        try:
            if payment_id:
                # Sync a single payment
                self.stdout.write(f"Attempting to sync specific payment: {payment_id}")
                success = sync_service.sync_single_payment(payment_id)
                if success:
                    self.stdout.write(self.style.SUCCESS(f'✓ Successfully synced payment {payment_id}'))
                    logger.info(f'Successfully synced payment {payment_id}')
                else:
                    self.stdout.write(self.style.ERROR(f'✗ Failed to sync payment {payment_id}. Check logs.'))
                    logger.error(f'Failed to sync payment {payment_id}.')

            elif customer_id:
                 # Sync payments for a specific customer
                 self.stdout.write(f"Attempting to sync payments for customer: {customer_id} (limit: {limit})")
                 stats = sync_service.sync_payments_for_customer(customer_id, limit=limit)
                 self.stdout.write(
                     f"Customer Payment Sync Result: Fetched {stats['total']}, "
                     f"Processed {stats['processed']}, Failed {stats['failed']}."
                 )
                 if stats['failed'] > 0:
                     self.stdout.write(self.style.WARNING(f"Encountered {stats['failed']} failures. Check logs."))
                 self.stdout.write(self.style.SUCCESS('✓ Customer payment sync finished.'))
                 logger.info(f"Customer payment sync finished for {customer_id}: {stats}")


            else:
                # Sync all payments (up to the limit)
                self.stdout.write(f"Attempting to sync multiple payments (limit: {limit})...")
                stats = sync_service.sync_all_payments(limit=limit)
                self.stdout.write(
                    f"Bulk Sync Result: Fetched {stats['total']}, "
                    f"Processed {stats['processed']}, Failed {stats['failed']}."
                )
                if stats['failed'] > 0:
                    self.stdout.write(self.style.WARNING(f"Encountered {stats['failed']} failures. Check logs."))
                self.stdout.write(self.style.SUCCESS('✓ Bulk payment sync finished.'))
                logger.info(f"Bulk payment sync finished: {stats}")

        except Exception as e:
            logger.error(f"An unexpected error occurred during payment sync: {e}", exc_info=True)
            raise CommandError(f"Payment sync failed: {e}")

        final_message = "Payment sync process complete."
        self.stdout.write(self.style.SUCCESS(final_message))
        logger.info(final_message)
