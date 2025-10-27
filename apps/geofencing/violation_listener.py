"""
Firebase Geofence Violation Listener Service

Monitors the geofence_violations collection in Firebase and processes violations:
1. Validates if the location actually exited the geofence
2. Identifies the active zone
3. Records violations to the ZoneViolation model
"""

import logging
from datetime import datetime
from typing import Dict, Optional, Tuple
from decimal import Decimal

from django.utils import timezone
from firebase_admin import firestore

from apps.geofencing.models import Zone, ZoneViolation
from apps.geofencing.geofence_utils import validate_geofence_exit, normalize_polygon_points
from apps.bikes.models import Bike
from apps.rides.models import Ride

logger = logging.getLogger(__name__)


class GeofenceViolationListener:
    """
    Listens to Firebase geofence_violations collection and processes violations
    """

    def __init__(self):
        self.db = firestore.client()
        self.violations_ref = self.db.collection('geofence_violations')

    def _get_bike_zone(self, bike_id: str) -> Optional[str]:
        """
        Get the current zone ID for a bike from Firebase.

        Args:
            bike_id: The Firebase bike ID

        Returns:
            Zone firebase_id or None
        """
        try:
            bike_ref = self.db.collection('bikes').document(bike_id)
            bike_doc = bike_ref.get()

            if bike_doc.exists:
                bike_data = bike_doc.to_dict()
                return bike_data.get('current_zone_id')
        except Exception as e:
            logger.error(f"Error fetching bike zone for {bike_id}: {e}")

        # Fallback to PostgreSQL if Firebase fetch fails
        try:
            bike = Bike.objects.filter(firebase_id=bike_id).first()
            if bike:
                return bike.current_zone_id
        except Exception as e:
            logger.error(f"Error fetching bike zone from DB for {bike_id}: {e}")

        return None

    def _get_zone_polygon(self, zone_firebase_id: str) -> Optional[list]:
        """
        Get zone polygon points from Firebase or PostgreSQL.

        Args:
            zone_firebase_id: The Firebase zone ID

        Returns:
            List of polygon points or None
        """
        # Try Firebase first
        try:
            zone_ref = self.db.collection('geofence').document(zone_firebase_id)
            zone_doc = zone_ref.get()

            if zone_doc.exists:
                zone_data = zone_doc.to_dict()
                points = zone_data.get('points', [])
                return normalize_polygon_points(points)
        except Exception as e:
            logger.error(f"Error fetching zone polygon from Firebase for {zone_firebase_id}: {e}")

        # Fallback to PostgreSQL
        try:
            zone = Zone.objects.filter(firebase_id=zone_firebase_id, is_active=True).first()
            if zone and zone.polygon_points:
                return normalize_polygon_points(zone.polygon_points)
        except Exception as e:
            logger.error(f"Error fetching zone polygon from DB for {zone_firebase_id}: {e}")

        return None

    def _get_active_rental(self, bike_id: str) -> Optional[Tuple[str, str]]:
        """
        Get active rental information for a bike.

        Args:
            bike_id: The Firebase bike ID

        Returns:
            Tuple of (customer_firebase_id, rental_firebase_id) or (None, None)
        """
        try:
            # Check for active rides
            ride = Ride.objects.filter(
                bike__firebase_id=bike_id,
                rental_status='ACTIVE'
            ).select_related('customer').first()

            if ride:
                customer_id = ride.customer.firebase_id if ride.customer else None
                return customer_id, ride.firebase_id

        except Exception as e:
            logger.error(f"Error fetching active rental for bike {bike_id}: {e}")

        return None, None

    def _map_violation_type(self, firebase_type: str) -> str:
        """
        Map Firebase violation type to Django model choices.

        Args:
            firebase_type: Violation type from Firebase (e.g., "GEOFENCE EXIT")

        Returns:
            Mapped violation type for Django model
        """
        type_mapping = {
            'GEOFENCE_EXIT': 'EXIT_ZONE',
            'EXIT_ZONE': 'EXIT_ZONE',
            'UNAUTHORIZED_PARKING': 'UNAUTHORIZED_PARKING',
            'SPEED_LIMIT': 'SPEED_LIMIT',
        }
        return type_mapping.get(firebase_type, 'EXIT_ZONE')

    def _convert_firebase_timestamp(self, timestamp) -> datetime:
        """
        Convert Firebase timestamp to Django timezone-aware datetime.

        Args:
            timestamp: Firebase timestamp object

        Returns:
            Timezone-aware datetime
        """
        if hasattr(timestamp, 'timestamp'):
            # Firebase Timestamp object
            return timezone.make_aware(
                datetime.fromtimestamp(timestamp.timestamp())
            )
        elif isinstance(timestamp, datetime):
            # Already a datetime
            return timezone.make_aware(timestamp) if timezone.is_naive(timestamp) else timestamp
        else:
            # Default to now
            return timezone.now()

    def process_violation(self, violation_id: str, violation_data: Dict) -> Optional[ZoneViolation]:
        """
        Process a single geofence violation and create ZoneViolation record if valid.

        Args:
            violation_id: Firebase document ID
            violation_data: Violation data from Firebase

        Returns:
            Created ZoneViolation instance or None if validation fails
        """
        bike_id = violation_data.get('bike_id')
        location = violation_data.get('location')  # GeoPoint or [latitude, longitude]
        timestamp = violation_data.get('timestamp')
        violation_type = violation_data.get('violation_type', 'GEOFENCE EXIT')

        logger.info(f"Processing violation {violation_id} for bike {bike_id}")

        # Extract coordinates - Check GeoPoint FIRST (most common format)
        latitude = None
        longitude = None

        # Try Firebase GeoPoint (has _latitude and _longitude attributes)
        if hasattr(location, '_latitude') and hasattr(location, '_longitude'):
            latitude = float(location._latitude)
            longitude = float(location._longitude)
            logger.debug(f"Parsed GeoPoint: ({latitude}, {longitude})")
        # Try public latitude/longitude attributes
        elif hasattr(location, 'latitude') and hasattr(location, 'longitude'):
            latitude = float(location.latitude)
            longitude = float(location.longitude)
            logger.debug(f"Parsed location object: ({latitude}, {longitude})")
        # Try list/array format [lat, lng]
        elif isinstance(location, (list, tuple)) and len(location) >= 2:
            latitude = float(location[0])
            longitude = float(location[1])
            logger.debug(f"Parsed list: ({latitude}, {longitude})")
        # Try dict format {"latitude": ..., "longitude": ...}
        elif isinstance(location, dict) and 'latitude' in location and 'longitude' in location:
            latitude = float(location['latitude'])
            longitude = float(location['longitude'])
            logger.debug(f"Parsed dict: ({latitude}, {longitude})")
        else:
            logger.error(
                f"Invalid location format for violation {violation_id}. "
                f"Type: {type(location)}, Value: {location}, "
                f"Attributes: {dir(location) if hasattr(location, '__dict__') else 'N/A'}"
            )
            return None

        if latitude is None or longitude is None:
            logger.error(f"Could not extract coordinates for violation {violation_id}")
            return None

        # Get bike's current zone
        zone_firebase_id = self._get_bike_zone(bike_id)
        if not zone_firebase_id:
            logger.warning(f"No zone found for bike {bike_id}. Cannot process violation.")
            return None

        # Get zone polygon for validation
        polygon_points = self._get_zone_polygon(zone_firebase_id)
        if not polygon_points:
            logger.warning(f"No polygon points found for zone {zone_firebase_id}. Skipping validation.")
            # Still create violation but without validation
        else:
            # Validate if the point is actually outside the geofence
            is_valid_exit = validate_geofence_exit((latitude, longitude), polygon_points)
            if not is_valid_exit:
                logger.info(
                    f"Location ({latitude}, {longitude}) is still inside zone {zone_firebase_id}. "
                    f"Violation {violation_id} is FALSE POSITIVE - not recording."
                )
                return None

            logger.info(f"Validated: Location is OUTSIDE zone {zone_firebase_id}. Recording violation.")

        # Get Zone model instance
        try:
            zone = Zone.objects.get(firebase_id=zone_firebase_id, is_active=True)
        except Zone.DoesNotExist:
            logger.error(f"Zone {zone_firebase_id} not found in database. Cannot create violation.")
            return None

        # Get active rental information
        customer_id, rental_id = self._get_active_rental(bike_id)

        # Convert timestamp
        violation_time = self._convert_firebase_timestamp(timestamp)

        # Map violation type
        mapped_violation_type = self._map_violation_type(violation_type)

        # Check if violation already exists (avoid duplicates)
        existing = ZoneViolation.objects.filter(
            bike_id=bike_id,
            latitude=Decimal(str(latitude)),
            longitude=Decimal(str(longitude)),
            violation_time=violation_time
        ).first()

        if existing:
            logger.info(f"Violation already recorded: {existing.id}")
            return existing

        # Create ZoneViolation record
        try:
            zone_violation = ZoneViolation.objects.create(
                zone=zone,
                bike_id=bike_id,
                customer_id=customer_id or 'UNKNOWN',
                rental_id=rental_id,
                violation_type=mapped_violation_type,
                latitude=Decimal(str(latitude)),
                longitude=Decimal(str(longitude)),
                violation_time=violation_time,
                resolved=False,
                notes=f"Auto-recorded from Firebase violation {violation_id}"
            )

            logger.info(
                f"✓ Created ZoneViolation {zone_violation.id} for bike {bike_id} "
                f"in zone {zone.name} at ({latitude}, {longitude})"
            )

            return zone_violation

        except Exception as e:
            logger.error(f"Error creating ZoneViolation: {e}", exc_info=True)
            return None

    def listen_and_process(self, callback=None):
        """
        Listen to geofence_violations collection and process new violations in real-time.

        Args:
            callback: Optional callback function to call after processing each violation
        """
        logger.info("Starting geofence violation listener...")

        def on_snapshot(col_snapshot, changes, read_time):
            """Handle Firestore snapshot changes"""
            for change in changes:
                if change.type.name in ['ADDED', 'MODIFIED']:
                    violation_id = change.document.id
                    violation_data = change.document.to_dict()

                    logger.info(f"New/Updated violation detected: {violation_id}")

                    try:
                        zone_violation = self.process_violation(violation_id, violation_data)

                        if zone_violation and callback:
                            callback(zone_violation)

                    except Exception as e:
                        logger.error(f"Error processing violation {violation_id}: {e}", exc_info=True)

        # Set up Firestore listener
        watch = self.violations_ref.on_snapshot(on_snapshot)

        logger.info("✓ Geofence violation listener is active")

        return watch

    def process_existing_violations(self, limit: int = 100):
        """
        Process existing violations from Firebase (useful for initial sync or catch-up).

        Args:
            limit: Maximum number of violations to process
        """
        logger.info(f"Processing existing violations (limit: {limit})...")

        violations = self.violations_ref.order_by(
            'timestamp',
            direction=firestore.Query.DESCENDING
        ).limit(limit).stream()

        processed_count = 0
        created_count = 0

        for doc in violations:
            violation_id = doc.id
            violation_data = doc.to_dict()

            try:
                zone_violation = self.process_violation(violation_id, violation_data)
                processed_count += 1

                if zone_violation:
                    created_count += 1

            except Exception as e:
                logger.error(f"Error processing violation {violation_id}: {e}", exc_info=True)

        logger.info(
            f"✓ Processed {processed_count} violations, created {created_count} new ZoneViolation records"
        )

        return processed_count, created_count