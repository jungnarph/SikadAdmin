"""
Django management command to sync rides from Firebase Firestore to PostgreSQL.
Usage: python manage.py sync_rides [--ride-id <firebase_doc_id>] [--limit <num>]
"""

from django.core.management.base import BaseCommand, CommandError
from apps.rides.sync_service import RideSyncService
from apps.rides.firebase_service import RideFirebaseService # Import Firebase service to fetch data
import logging

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = 'Sync rides from Firebase Firestore (ride_logs collection) to PostgreSQL database'

    def add_arguments(self, parser):
        parser.add_argument(
            '--ride-id',
            type=str,
            help='Sync only a specific ride by its Firebase document ID.'
        )
        parser.add_argument(
            '--limit',
            type=int,
            default=1000, # Default limit for bulk sync
            help='Maximum number of rides to fetch during bulk sync (default: 1000).'
        )
        # Add other arguments if needed, e.g., --start-date, --end-date

    def handle(self, *args, **options):
        # Instantiate services
        sync_service = RideSyncService()
        # Instantiate Firebase service here to fetch data if needed for sync_all
        firebase_service = RideFirebaseService()
        sync_service.firebase_service = firebase_service # Inject firebase service if needed by sync_service

        ride_id = options.get('ride_id')
        limit = options.get('limit')

        start_message = "Starting ride sync process..."
        self.stdout.write(self.style.NOTICE(start_message))
        logger.info(start_message)

        try:
            if ride_id:
                # Sync a single ride
                self.stdout.write(f"Attempting to sync specific ride: {ride_id}")
                # Fetch the specific ride data first
                ride_data = firebase_service.get_ride(ride_id)
                if ride_data:
                    success = sync_service.sync_single_ride(ride_id, ride_data)
                    if success:
                        self.stdout.write(self.style.SUCCESS(f'✓ Successfully synced ride {ride_id}'))
                        logger.info(f'Successfully synced ride {ride_id}')
                    else:
                        self.stdout.write(self.style.ERROR(f'✗ Failed to sync ride {ride_id}. Check logs.'))
                        logger.error(f'Failed to sync ride {ride_id}.')
                else:
                     self.stdout.write(self.style.ERROR(f'✗ Ride {ride_id} not found in Firebase.'))
                     logger.error(f'Ride {ride_id} not found in Firebase.')

            else:
                # Sync multiple rides (up to the limit)
                self.stdout.write(f"Attempting to sync multiple rides (limit: {limit})...")
                # Fetch rides data using Firebase service
                rides_data = firebase_service.list_rides(limit=limit)
                stats = {'total': len(rides_data), 'processed': 0, 'failed': 0}

                if not rides_data:
                    self.stdout.write(self.style.WARNING('No rides found in Firebase to sync.'))
                else:
                    self.stdout.write(f"Fetched {stats['total']} rides from Firebase. Beginning sync...")
                    for ride_data in rides_data:
                        current_ride_id = ride_data.get('firebase_id')
                        if current_ride_id:
                            if sync_service.sync_single_ride(current_ride_id, ride_data):
                                stats['processed'] += 1
                            else:
                                stats['failed'] += 1
                        else:
                            logger.warning("Found ride data without firebase_id during bulk sync.")
                            stats['failed'] += 1

                    self.stdout.write(
                        f"Bulk Sync Result: Fetched {stats['total']}, "
                        f"Processed {stats['processed']}, Failed {stats['failed']}."
                    )
                    if stats['failed'] > 0:
                        self.stdout.write(self.style.WARNING(f"Encountered {stats['failed']} failures. Check logs."))
                    self.stdout.write(self.style.SUCCESS('✓ Bulk ride sync finished.'))
                    logger.info(f"Bulk ride sync finished: {stats}")

        except Exception as e:
            logger.error(f"An unexpected error occurred during ride sync: {e}", exc_info=True)
            raise CommandError(f"Ride sync failed: {e}")

        final_message = "Ride sync process complete."
        self.stdout.write(self.style.SUCCESS(final_message))
        logger.info(final_message)