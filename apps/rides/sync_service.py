# Updated content for apps/rides/sync_service.py
"""
Ride Sync Service
Syncs ride data from Firebase ride_logs collection to the PostgreSQL Ride model.
"""
import logging
from datetime import datetime
from django.utils.timezone import make_aware, is_aware
from django.apps import apps
from dateutil import parser as dateutil_parser

# Import necessary Firebase services
from .firebase_service import RideFirebaseService
from apps.payments.firebase_service import PaymentFirebaseService # Import Payment service

from .models import Ride
# String references for related models
CUSTOMER_MODEL_PATH = 'customers.Customer'
# PAYMENT_MODEL_PATH = 'payments.Payment' # Not directly needed for FK here now
BIKE_MODEL_PATH = 'bikes.Bike'

logger = logging.getLogger(__name__)

class RideSyncService:
    """Service to sync rides from Firebase to PostgreSQL"""

    def __init__(self):
        self.firebase_service = RideFirebaseService()
        # Initialize PaymentFirebaseService to fetch payment details
        self.payment_firebase_service = PaymentFirebaseService()
        self.CustomerModel = apps.get_model(CUSTOMER_MODEL_PATH.split('.')[0], CUSTOMER_MODEL_PATH.split('.')[1])
        self.BikeModel = apps.get_model(BIKE_MODEL_PATH.split('.')[0], BIKE_MODEL_PATH.split('.')[1])
        # Payment model linking might need adjustment based on final Payment model structure
        # self.PaymentModel = apps.get_model(PAYMENT_MODEL_PATH.split('.')[0], PAYMENT_MODEL_PATH.split('.')[1])

    def _parse_firebase_timestamp(self, timestamp_data, ride_id, field_name):
        """
        Safely parse various timestamp formats from Firebase.

        IMPORTANT: Check for datetime objects FIRST before other types.
        Firebase often returns DatetimeWithNanoseconds which is a datetime subclass.
        """
        if not timestamp_data:
            return None

        # Method 1: Already a datetime object (includes DatetimeWithNanoseconds)
        # THIS MUST BE CHECKED FIRST!
        if isinstance(timestamp_data, datetime):
            logger.debug(f"✓ Field '{field_name}' is already a datetime object for ride {ride_id}")
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
                logger.debug(f"✓ Converted Firestore Timestamp for ride {ride_id}, field {field_name}")
                return dt
            except Exception as e:
                logger.error(f"Error converting Firestore Timestamp for ride {ride_id}, field {field_name}: {e}")
                return None

        # Method 3: String format
        if isinstance(timestamp_data, str):
            try:
                dt = dateutil_parser.parse(timestamp_data)
                if not is_aware(dt):
                    dt = make_aware(dt)
                logger.debug(f"✓ Converted string timestamp for ride {ride_id}, field {field_name}")
                return dt
            except (ValueError, TypeError, dateutil_parser.ParserError) as e:
                logger.warning(f"Could not parse date string '{timestamp_data}' for ride {ride_id}, field {field_name}: {e}")
                return None

        # Method 4: Numeric (Unix timestamp)
        if isinstance(timestamp_data, (int, float)):
            try:
                if timestamp_data > 10000000000: # Likely milliseconds
                    dt = datetime.fromtimestamp(timestamp_data / 1000.0)
                else: # Likely seconds
                    dt = datetime.fromtimestamp(timestamp_data)
                dt = make_aware(dt)
                logger.debug(f"✓ Converted numeric timestamp for ride {ride_id}, field {field_name}")
                return dt
            except Exception as e:
                logger.error(f"Error converting numeric timestamp {timestamp_data} for ride {ride_id}, field {field_name}: {e}")
                return None

        logger.warning(f"Unrecognized timestamp format for ride {ride_id}, field {field_name}: type {type(timestamp_data).__name__}")
        return None

    def _parse_point_timestamp(self, timestamp_data):
        """
        Parse timestamp from a point. Handles datetime objects and strings.
        Returns ISO format string or None.
        """
        if not timestamp_data:
            return None

        # Already a datetime object (including DatetimeWithNanoseconds)
        if isinstance(timestamp_data, datetime):
            return timestamp_data.isoformat()

        # Firestore Timestamp
        if hasattr(timestamp_data, 'to_datetime') and callable(timestamp_data.to_datetime):
            try:
                return timestamp_data.to_datetime().isoformat()
            except Exception:
                return None

        # String - parse and convert to ISO
        if isinstance(timestamp_data, str):
            try:
                return dateutil_parser.parse(timestamp_data).isoformat()
            except (ValueError, TypeError, dateutil_parser.ParserError):
                return None

        # Numeric timestamp
        if isinstance(timestamp_data, (int, float)):
            try:
                if timestamp_data > 10000000000:
                    return datetime.fromtimestamp(timestamp_data / 1000.0).isoformat()
                else:
                    return datetime.fromtimestamp(timestamp_data).isoformat()
            except Exception:
                return None

        return None

    def _format_ride_points(self, points_data, ride_id: str) -> list:
        """
        Convert Firebase points map to a sorted list of dicts.
        Handles both Map and Array structures from Firebase for points.
        """
        if not points_data:
            logger.debug(f"No points data for ride {ride_id}")
            return []

        points_input = []
        if isinstance(points_data, dict):
            # Handle map structure { "0": {...}, "1": {...} }
            points_input = points_data.values()
            logger.debug(f"Processing points data as dictionary for ride {ride_id}")
        elif isinstance(points_data, list):
            # Handle array structure [ {...}, {...} ]
            points_input = points_data
            logger.debug(f"Processing points data as list for ride {ride_id}")
        else:
            logger.warning(f"Points data for ride {ride_id} is neither a list nor a dict (type: {type(points_data).__name__}). Skipping points.")
            return []

        if not points_input:
            logger.debug(f"Empty points data after type check for ride {ride_id}")
            return []

        logger.debug(f"Processing {len(points_input)} points for ride {ride_id}")

        points_list = []
        for idx, point in enumerate(points_input):
            try:
                # Validate that point is a dict/map
                if not isinstance(point, dict):
                    logger.warning(f"Point {idx} for ride {ride_id} is not a dict (type: {type(point).__name__}). Skipping.")
                    continue

                # Extract latitude and longitude
                lat = point.get('latitude')
                lng = point.get('longitude')

                if lat is None or lng is None:
                    logger.warning(f"Point {idx} for ride {ride_id} missing latitude or longitude. Skipping.")
                    continue

                # Convert to float
                try:
                    lat = float(lat)
                    lng = float(lng)
                except (ValueError, TypeError) as e:
                    logger.warning(f"Point {idx} for ride {ride_id} has invalid lat/lng values: {e}. Skipping.")
                    continue

                # Extract speed (optional)
                speed = point.get('speed')
                if speed is not None:
                    try:
                        speed = float(speed)
                    except (ValueError, TypeError):
                        speed = None

                # Parse timestamp
                timestamp_raw = point.get('timestamp')
                timestamp_iso = self._parse_point_timestamp(timestamp_raw)

                # Create point dict
                point_dict = {
                    "latitude": lat,
                    "longitude": lng,
                    "timestamp": timestamp_iso
                }

                # Optionally include speed if available
                if speed is not None:
                    point_dict["speed"] = speed

                points_list.append(point_dict)

            except Exception as e:
                logger.warning(f"Error processing point {idx} for ride {ride_id}: {e}", exc_info=True) # Added exc_info
                continue

        # Sort points by timestamp
        if points_list:
            try:
                # Filter out points without timestamps before sorting if necessary
                points_with_ts = [p for p in points_list if p.get('timestamp')]
                points_without_ts = [p for p in points_list if not p.get('timestamp')]
                points_with_ts.sort(key=lambda p: p['timestamp'])
                points_list = points_with_ts + points_without_ts # Append points without timestamp at the end
                logger.debug(f"✓ Successfully formatted and sorted {len(points_list)} points for ride {ride_id}")
            except Exception as e:
                logger.warning(f"Could not sort points for ride {ride_id}: {e}")

        invalid_points_count = len(points_input) - len(points_list)
        if invalid_points_count > 0:
            logger.info(f"Note: {invalid_points_count} invalid points were skipped for ride {ride_id}")

        return points_list


    def _map_firebase_to_django(self, firebase_data: dict) -> dict:
        """Maps Firebase ride_logs data to Django Ride model fields."""
        mapped_data = {}
        ride_id = firebase_data.get('firebase_id', 'unknown')

        # --- Relationships ---
        customer_firebase_id = firebase_data.get('userId')
        if customer_firebase_id:
            try:
                customer_instance = self.CustomerModel.objects.filter(firebase_id=customer_firebase_id).first()
                mapped_data['customer'] = customer_instance
                if not customer_instance:
                    logger.warning(f"Customer {customer_firebase_id} not found in DB for ride {ride_id}.")
            except Exception as e:
                logger.error(f"Error linking customer {customer_firebase_id} for ride {ride_id}: {e}")
        else:
            logger.warning(f"No userId found for ride {ride_id}")

        bike_firebase_id = firebase_data.get('bikeId')
        if bike_firebase_id:
            try:
                bike_instance = self.BikeModel.objects.filter(firebase_id=bike_firebase_id).first()
                mapped_data['bike'] = bike_instance
                if not bike_instance:
                     logger.warning(f"Bike {bike_firebase_id} not found in DB for ride {ride_id}.")
            except Exception as e:
                 logger.error(f"Error linking bike {bike_firebase_id} for ride {ride_id}: {e}")
        else:
             logger.warning(f"No bikeId found for ride {ride_id}")

        # --- Timestamps ---
        mapped_data['start_time'] = firebase_data.get('startTime_dt') # Use pre-parsed if available
        if not mapped_data['start_time']: # Fallback parsing
             mapped_data['start_time'] = self._parse_firebase_timestamp(firebase_data.get('startTime'), ride_id, 'startTime')

        mapped_data['end_time'] = firebase_data.get('endTime_dt') # Use pre-parsed if available
        if not mapped_data['end_time'] and 'endTime' in firebase_data: # Fallback parsing only if endTime key exists
             mapped_data['end_time'] = self._parse_firebase_timestamp(firebase_data.get('endTime'), ride_id, 'endTime')

        if not mapped_data['start_time']:
            logger.warning(f"No valid start_time found/parsed for ride {ride_id}")
        if 'endTime' in firebase_data and not mapped_data['end_time']:
             logger.warning(f"endTime field exists but could not be parsed for ride {ride_id}")

        # --- Duration (Calculate if possible) ---
        if mapped_data['start_time'] and mapped_data['end_time']:
            try:
                duration = mapped_data['end_time'] - mapped_data['start_time']
                mapped_data['duration_minutes'] = max(0, int(duration.total_seconds() / 60))
            except TypeError: # Handle cases where one timestamp might be None after parsing attempts
                 logger.warning(f"Cannot calculate duration due to invalid timestamps for ride {ride_id}")
                 mapped_data['duration_minutes'] = firebase_data.get('duration_minutes', 0)
        else:
             mapped_data['duration_minutes'] = firebase_data.get('duration_minutes', 0)

        # --- Ride Path & Start/End Location ---
        points_data = firebase_data.get('points')
        points_list = self._format_ride_points(points_data, ride_id)
        mapped_data['ride_path_points'] = points_list

        if points_list:
            try:
                # Ensure points actually have lat/lon keys after formatting
                if 'latitude' in points_list[0] and 'longitude' in points_list[0]:
                    mapped_data['start_latitude'] = points_list[0]['latitude']
                    mapped_data['start_longitude'] = points_list[0]['longitude']
                if 'latitude' in points_list[-1] and 'longitude' in points_list[-1]:
                    mapped_data['end_latitude'] = points_list[-1]['latitude']
                    mapped_data['end_longitude'] = points_list[-1]['longitude']
                logger.debug(f"✓ Extracted start/end coordinates from {len(points_list)} points for ride {ride_id}")
            except (IndexError, KeyError, TypeError) as e:
                logger.warning(f"Could not extract start/end coordinates from points for ride {ride_id}: {e}")
        else:
            logger.debug(f"No valid points data available for ride {ride_id}, using fallback coordinates if available")
            # Fallback if no points data
            mapped_data['start_latitude'] = firebase_data.get('start_latitude')
            mapped_data['start_longitude'] = firebase_data.get('start_longitude')
            mapped_data['end_latitude'] = firebase_data.get('end_latitude')
            mapped_data['end_longitude'] = firebase_data.get('end_longitude')

        mapped_data['start_zone_id'] = firebase_data.get('start_zone_id', '')
        mapped_data['end_zone_id'] = firebase_data.get('end_zone_id', '')

        # --- Metrics & Payment ---
        try:
             mapped_data['distance_km'] = float(firebase_data.get('distance_km', 0.0))
        except (ValueError, TypeError):
             mapped_data['distance_km'] = 0.0

        # --- Fetch Amount and Status from Payment Collection ---
        payment_id = firebase_data.get('paymentId')
        ride_amount = 0.0
        ride_payment_status = 'UNKNOWN' # Default if no payment found

        if payment_id:
            logger.debug(f"Ride {ride_id} has paymentId: {payment_id}. Fetching payment details...")
            payment_data = self.payment_firebase_service.get_payment(payment_id)
            if payment_data:
                try:
                    ride_amount = float(payment_data.get('amount', 0.0))
                    logger.debug(f"✓ Found amount {ride_amount} for payment {payment_id}")
                except (ValueError, TypeError):
                    logger.warning(f"Invalid amount found for payment {payment_id}. Defaulting to 0.0")
                    ride_amount = 0.0

                fb_payment_status = str(payment_data.get('paymentStatus', 'UNKNOWN')).upper()
                ride_payment_status = fb_payment_status if fb_payment_status in dict(Ride.PAYMENT_STATUS_CHOICES) else 'UNKNOWN'
                logger.debug(f"✓ Found status '{ride_payment_status}' for payment {payment_id}")
            else:
                logger.warning(f"Payment document {payment_id} linked to ride {ride_id} not found in Firebase.")
                # Keep default 'UNKNOWN' status, amount remains 0.0
        else:
            logger.debug(f"No paymentId linked to ride {ride_id}. Setting amount to 0.0 and status to PENDING/UNKNOWN.")
            # If no paymentId, maybe the status should be PENDING? Or keep UNKNOWN?
            # Let's default to PENDING if no payment ID is present, assuming payment might happen later.
            ride_payment_status = 'PENDING'

        mapped_data['amount_charged'] = ride_amount
        mapped_data['payment_status'] = ride_payment_status
        # --- End Fetch ---

        # --- Status ---
        fb_rental_status = str(firebase_data.get('rental_status', 'UNKNOWN')).upper()
        # Infer status if missing: If endTime exists, likely COMPLETED, else ACTIVE
        if fb_rental_status in ['UNKNOWN', '']:
            fb_rental_status = 'COMPLETED' if mapped_data['end_time'] else 'ACTIVE'

        mapped_data['rental_status'] = fb_rental_status if fb_rental_status in dict(Ride.RENTAL_STATUS_CHOICES) else 'UNKNOWN'

        mapped_data['cancellation_reason'] = firebase_data.get('cancellation_reason', '')

        # Clean None values from lat/lon before saving if needed, although model allows null=True
        for key in ['start_latitude', 'start_longitude', 'end_latitude', 'end_longitude']:
             if mapped_data.get(key) is None:
                  mapped_data.pop(key, None) # Remove if None, DB will handle default/null

        return mapped_data

    def sync_single_ride(self, ride_id: str, firebase_data: dict = None) -> bool:
        """
        Sync a single ride from Firebase to PostgreSQL.
        Can optionally accept pre-fetched firebase_data.
        """
        try:
            if not firebase_data:
                # Fetch from Firebase
                firebase_data = self.firebase_service.get_ride(ride_id)

            if not firebase_data:
                logger.warning(f"Ride {ride_id} not found in Firebase (or fetch failed).")
                return False

            # Ensure firebase_id is in the data dict
            firebase_data['firebase_id'] = ride_id

            defaults = self._map_firebase_to_django(firebase_data)

            # Update or create in PostgreSQL
            ride, created = Ride.objects.update_or_create(
                firebase_id=ride_id,
                defaults=defaults
            )

            action = "created" if created else "updated"
            points_count = len(defaults.get('ride_path_points', []))
            logger.info(
                f"Ride {ride_id} {action} in PostgreSQL. "
                f"Status: {defaults.get('rental_status')}, "
                f"Amount: {defaults.get('amount_charged')}, "
                f"PayStatus: {defaults.get('payment_status')}, "
                f"Points: {points_count}, "
                f"Start: {defaults.get('start_time')}"
            )
            return True

        except Exception as e:
            logger.error(f"Error syncing ride {ride_id}: {e}", exc_info=True)
            return False

    def sync_all_rides(self, limit: int = 1000) -> dict:
        """
        Sync multiple rides from Firebase to PostgreSQL.
        """
        stats = {'total': 0, 'processed': 0, 'failed': 0}
        try:
            logger.info(f"Starting bulk ride sync with limit {limit}")
            rides_data = self.firebase_service.list_rides(limit=limit)

            stats['total'] = len(rides_data)
            logger.info(f"Fetched {stats['total']} rides from Firebase. Beginning sync...")

            for ride_data in rides_data:
                ride_id = ride_data.get('firebase_id')
                if ride_id:
                    if self.sync_single_ride(ride_id, ride_data):
                        stats['processed'] += 1
                    else:
                        stats['failed'] += 1
                else:
                    logger.warning("Found ride data without firebase_id during bulk sync.")
                    stats['failed'] += 1

            logger.info(f"Ride sync completed: Processed {stats['processed']}, Failed {stats['failed']} out of {stats['total']} fetched.")
            return stats

        except Exception as e:
            logger.error(f"Error during bulk ride sync: {e}", exc_info=True)
            return stats

    def sync_rides_for_customer(self, customer_firebase_id: str, limit: int = 100) -> dict:
        """Syncs rides for a specific customer."""
        stats = {'total': 0, 'processed': 0, 'failed': 0}
        try:
            logger.info(f"Starting ride sync for customer {customer_firebase_id} with limit {limit}")

            rides_data = self.firebase_service.get_rides_for_customer(customer_firebase_id, limit=limit)
            stats['total'] = len(rides_data)

            logger.info(f"Fetched {stats['total']} rides for customer {customer_firebase_id}")

            for ride_data in rides_data:
                ride_id = ride_data.get('firebase_id')
                if ride_id and self.sync_single_ride(ride_id, ride_data):
                    stats['processed'] += 1
                else:
                    stats['failed'] += 1

            logger.info(f"Synced rides for customer {customer_firebase_id}: Processed {stats['processed']}, Failed {stats['failed']}")
            return stats
        except Exception as e:
            logger.error(f"Error syncing rides for customer {customer_firebase_id}: {e}", exc_info=True)
            return stats

    def sync_rides_for_bike(self, bike_firebase_id: str, limit: int = 100) -> dict:
        """Syncs rides for a specific bike."""
        stats = {'total': 0, 'processed': 0, 'failed': 0}
        try:
            logger.info(f"Starting ride sync for bike {bike_firebase_id} with limit {limit}")

            rides_data = self.firebase_service.get_rides_for_bike(bike_firebase_id, limit=limit)
            stats['total'] = len(rides_data)

            logger.info(f"Fetched {stats['total']} rides for bike {bike_firebase_id}")

            for ride_data in rides_data:
                ride_id = ride_data.get('firebase_id')
                if ride_id and self.sync_single_ride(ride_id, ride_data):
                    stats['processed'] += 1
                else:
                    stats['failed'] += 1

            logger.info(f"Synced rides for bike {bike_firebase_id}: Processed {stats['processed']}, Failed {stats['failed']}")
            return stats
        except Exception as e:
            logger.error(f"Error syncing rides for bike {bike_firebase_id}: {e}", exc_info=True)
            return stats