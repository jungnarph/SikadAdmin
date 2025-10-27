"""
Management command to listen for geofence violations from Firebase

Usage:
    python manage.py listen_violations              # Start real-time listener
    python manage.py listen_violations --sync-only   # Process existing violations only
    python manage.py listen_violations --limit 50    # Process latest 50 violations
"""

import logging
import time
from django.core.management.base import BaseCommand
from apps.geofencing.violation_listener import GeofenceViolationListener

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Listen to Firebase geofence_violations collection and record to ZoneViolation model'

    def add_arguments(self, parser):
        parser.add_argument(
            '--sync-only',
            action='store_true',
            help='Only process existing violations, do not start real-time listener'
        )
        parser.add_argument(
            '--limit',
            type=int,
            default=100,
            help='Number of existing violations to process (default: 100)'
        )

    def handle(self, *args, **options):
        sync_only = options['sync_only']
        limit = options['limit']

        self.stdout.write(self.style.SUCCESS('=' * 60))
        self.stdout.write(self.style.SUCCESS('  Geofence Violation Listener'))
        self.stdout.write(self.style.SUCCESS('=' * 60))

        listener = GeofenceViolationListener()

        if sync_only:
            # Process existing violations only
            self.stdout.write(self.style.WARNING(f'\nProcessing existing violations (limit: {limit})...'))
            processed, created = listener.process_existing_violations(limit=limit)

            self.stdout.write(self.style.SUCCESS(f'\n✓ Processed: {processed} violations'))
            self.stdout.write(self.style.SUCCESS(f'✓ Created: {created} new ZoneViolation records'))

        else:
            # Process existing violations first
            self.stdout.write(self.style.WARNING('\nStep 1: Processing existing violations...'))
            processed, created = listener.process_existing_violations(limit=limit)

            self.stdout.write(self.style.SUCCESS(f'✓ Processed: {processed} violations'))
            self.stdout.write(self.style.SUCCESS(f'✓ Created: {created} new ZoneViolation records'))

            # Start real-time listener
            self.stdout.write(self.style.WARNING('\nStep 2: Starting real-time listener...'))

            def on_violation_created(zone_violation):
                """Callback when a new violation is created"""
                self.stdout.write(
                    self.style.SUCCESS(
                        f'✓ New violation: {zone_violation.bike_id} exited {zone_violation.zone.name} '
                        f'at {zone_violation.violation_time.strftime("%Y-%m-%d %H:%M:%S")}'
                    )
                )

            watch = listener.listen_and_process(callback=on_violation_created)

            self.stdout.write(self.style.SUCCESS('✓ Listener is active. Press Ctrl+C to stop.'))
            self.stdout.write(self.style.WARNING('\nMonitoring geofence_violations collection...'))

            try:
                # Keep the listener running
                while True:
                    time.sleep(1)

            except KeyboardInterrupt:
                self.stdout.write(self.style.WARNING('\n\nStopping listener...'))
                watch.unsubscribe()
                self.stdout.write(self.style.SUCCESS('✓ Listener stopped successfully'))

        self.stdout.write(self.style.SUCCESS('\n' + '=' * 60))