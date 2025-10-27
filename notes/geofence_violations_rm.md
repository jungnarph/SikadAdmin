# Geofence Violation Monitoring System

This system monitors and processes geofence violations from Firebase, validates them using point-in-polygon algorithms, and records them to the ZoneViolation model in PostgreSQL.

## Overview

The geofence violation monitoring system consists of:

1. **Point-in-Polygon Validation** - Validates if a location actually exited a geofence
2. **Firebase Listener** - Real-time monitoring of `geofence_violations` collection
3. **Zone Detection** - Identifies which zone a bike should be in
4. **Violation Recording** - Creates validated ZoneViolation records in the database

## Firebase Structure

### Input Collection: `geofence_violations`

```javascript
{
  bike_id: "bike_001",
  location: new firebase.firestore.GeoPoint(14.40128517, 120.8920887),  // GeoPoint object
  timestamp: firebase.firestore.Timestamp,
  violation_type: "GEOFENCE EXIT"
}
```

**Note:** The `location` field should be a Firebase GeoPoint object with:

- `latitude: 14.40128517` (or `_latitude` private attribute)
- `longitude: 120.8920887` (or `_longitude` private attribute)

The system also supports alternative formats:

- Array: `[14.40128517, 120.8920887]`
- Dict: `{"latitude": 14.40128517, "longitude": 120.8920887}`

### Related Collections

- `bikes/{bike_id}/current_zone_id` - Current zone assignment for each bike
- `geofence/{zone_id}/points` - Polygon points defining zone boundaries

## Components

### 1. Geofence Utils (`geofence_utils.py`)

Utility functions for geofence validation:

- **`point_in_polygon(point, polygon)`** - Ray casting algorithm to check if point is inside polygon
- **`validate_geofence_exit(location, polygon)`** - Validates if location is outside the geofence
- **`normalize_polygon_points(polygon_points)`** - Normalizes different polygon formats

### 2. Violation Listener (`violation_listener.py`)

Main service class: `GeofenceViolationListener`

**Key Methods:**

- `process_violation(violation_id, violation_data)` - Processes a single violation

  - Validates location is outside zone polygon
  - Finds active rental information
  - Creates ZoneViolation record

- `listen_and_process(callback)` - Real-time listener for new violations

  - Monitors Firebase collection
  - Auto-processes new violations

- `process_existing_violations(limit)` - Batch process existing violations
  - Useful for initial sync or catch-up

**Validation Process:**

1. Extract bike_id and location from violation
2. Get bike's current zone assignment (`current_zone_id`)
3. Fetch zone polygon points
4. **Validate**: Use point-in-polygon to check if location is OUTSIDE zone
5. If OUTSIDE (valid exit):
   - Find active rental (customer_id, rental_id)
   - Create ZoneViolation record
6. If INSIDE (false positive):
   - Log warning and skip

### 3. Management Command (`listen_violations.py`)

Django management command for running the violation listener.

**Usage:**

```bash
# Start real-time listener (processes existing + monitors new)
python manage.py listen_violations

# Process only existing violations (no real-time monitoring)
python manage.py listen_violations --sync-only

# Process latest 50 violations
python manage.py listen_violations --limit 50 --sync-only
```

**Options:**

- `--sync-only` - Process existing violations only, don't start listener
- `--limit N` - Number of existing violations to process (default: 100)

### 4. Web Interface

**URL:** `/geofencing/violations/process/`

**Features:**

- View violation processing status
- Manually trigger batch processing
- See recent violations

**POST Parameters:**

- `limit` - Number of violations to process (default: 100)

## Installation & Setup

### 1. Ensure Firebase is Configured

Check `config/settings.py`:

```python
FIREBASE_CREDENTIALS_PATH = '/path/to/serviceAccountKey.json'
```

### 2. Run Migrations

```bash
python manage.py migrate geofencing
```

### 3. Sync Zones from Firebase

```bash
python manage.py sync_zones
```

## Usage Examples

### Example 1: Real-Time Monitoring (Recommended)

Start the listener to continuously monitor violations:

```bash
python manage.py listen_violations
```

Output:

```
============================================================
  Geofence Violation Listener
============================================================

Step 1: Processing existing violations...
✓ Processed: 45 violations
✓ Created: 12 new ZoneViolation records

Step 2: Starting real-time listener...
✓ Listener is active. Press Ctrl+C to stop.

Monitoring geofence_violations collection...
✓ New violation: bike_001 exited Zone Malolos at 2025-10-27 15:21:36
```

### Example 2: One-Time Batch Processing

Process recent violations without starting the listener:

```bash
python manage.py listen_violations --sync-only --limit 100
```

### Example 3: Manual Web Trigger

1. Navigate to `/geofencing/violations/process/`
2. Click "Process Violations" button
3. System processes latest 100 violations

## Violation Type Mapping

Firebase violations are mapped to Django model choices:

| Firebase Type        | Django Model Type    |
| -------------------- | -------------------- |
| GEOFENCE EXIT        | EXIT_ZONE            |
| EXIT_ZONE            | EXIT_ZONE            |
| UNAUTHORIZED_PARKING | UNAUTHORIZED_PARKING |
| SPEED_LIMIT          | SPEED_LIMIT          |

## Database Schema

### ZoneViolation Model

```python
class ZoneViolation(models.Model):
    zone = ForeignKey(Zone)              # Which zone was violated
    bike_id = CharField                  # Firebase bike ID
    customer_id = CharField              # Firebase customer ID
    rental_id = CharField                # Firebase rental ID (nullable)
    violation_type = CharField           # EXIT_ZONE, UNAUTHORIZED_PARKING, etc.
    latitude = DecimalField              # Violation location
    longitude = DecimalField
    violation_time = DateTimeField       # When violation occurred
    resolved = BooleanField              # Resolution status
    resolved_at = DateTimeField
    notes = TextField
```

## Point-in-Polygon Algorithm

The system uses the **Ray Casting Algorithm**:

1. Draw a horizontal ray from the test point to infinity
2. Count how many times it intersects polygon edges
3. **Odd intersections** = point is INSIDE polygon
4. **Even intersections** = point is OUTSIDE polygon

**Implementation:** `geofence_utils.py:point_in_polygon()`

## Error Handling

The system handles various error cases:

- **Missing zone assignment** - Logs warning, skips violation
- **Invalid polygon** - Logs error, creates violation without validation
- **False positives** - Detected via validation, logged but not recorded
- **Duplicate violations** - Checks for existing records before creating

## Logging

All operations are logged with appropriate levels:

```python
logger.info("Validated: Location is OUTSIDE zone. Recording violation.")
logger.warning("No zone found for bike. Cannot process violation.")
logger.error("Error creating ZoneViolation: ...")
```

View logs:

```bash
# Django logs
tail -f logs/django.log

# Or check console output when running management command
```

## Testing

### Manual Test with Sample Data

1. Create a test violation in Firebase:

```javascript
// Firebase Console > geofence_violations collection
{
  bike_id: "bike_001",
  location: new firebase.firestore.GeoPoint(14.40128517, 120.8920887),
  timestamp: firebase.firestore.FieldValue.serverTimestamp(),
  violation_type: "GEOFENCE EXIT"
}
```

2. Run the listener:

```bash
python manage.py listen_violations
```

3. Check if violation was processed:

```bash
python manage.py shell
>>> from apps.geofencing.models import ZoneViolation
>>> ZoneViolation.objects.filter(bike_id='bike_001').latest('created_at')
```

### Validate Point-in-Polygon

```python
from apps.geofencing.geofence_utils import validate_geofence_exit

polygon = [
    {"latitude": 14.65, "longitude": 120.98},
    {"latitude": 14.65, "longitude": 121.05},
    {"latitude": 14.71, "longitude": 121.05},
    {"latitude": 14.71, "longitude": 120.98},
]

# Point inside (should return False - not an exit)
inside_point = (14.68, 121.00)
print(validate_geofence_exit(inside_point, polygon))  # False

# Point outside (should return True - valid exit)
outside_point = (14.75, 121.10)
print(validate_geofence_exit(outside_point, polygon))  # True
```

## Production Deployment

### Option 1: Run as Background Service (systemd)

Create `/etc/systemd/system/geofence-listener.service`:

```ini
[Unit]
Description=Geofence Violation Listener
After=network.target postgresql.service

[Service]
Type=simple
User=www-data
WorkingDirectory=/path/to/SikadAdmin
Environment="PATH=/path/to/venv/bin"
ExecStart=/path/to/venv/bin/python manage.py listen_violations
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Enable and start:

```bash
sudo systemctl enable geofence-listener
sudo systemctl start geofence-listener
sudo systemctl status geofence-listener
```

### Option 2: Run with Supervisor

Create `/etc/supervisor/conf.d/geofence-listener.conf`:

```ini
[program:geofence-listener]
command=/path/to/venv/bin/python manage.py listen_violations
directory=/path/to/SikadAdmin
user=www-data
autostart=true
autorestart=true
redirect_stderr=true
stdout_logfile=/var/log/geofence-listener.log
```

### Option 3: Cron Job (Batch Processing)

For periodic batch processing instead of real-time:

```cron
# Process violations every 5 minutes
*/5 * * * * /path/to/venv/bin/python /path/to/SikadAdmin/manage.py listen_violations --sync-only --limit 50
```

## Location Format Handling

The violation listener supports multiple location formats from Firebase:

### Priority Order (checked in this sequence):

1. **Firebase GeoPoint** (most common, recommended format)

   ```python
   location._latitude  # 14.40128517
   location._longitude # 120.8920887
   ```

2. **Public attributes**

   ```python
   location.latitude   # 14.40128517
   location.longitude  # 120.8920887
   ```

3. **List/Array format**

   ```python
   location = [14.40128517, 120.8920887]
   ```

4. **Dictionary format**
   ```python
   location = {"latitude": 14.40128517, "longitude": 120.8920887}
   ```

### Creating GeoPoint in Firebase

**Firestore Console:**

```javascript
location: new firebase.firestore.GeoPoint(14.40128517, 120.8920887);
```

**Python Admin SDK:**

```python
from google.cloud.firestore import GeoPoint
location = GeoPoint(14.40128517, 120.8920887)
```

**JavaScript/TypeScript:**

```javascript
import { GeoPoint } from "firebase/firestore";
const location = new GeoPoint(14.40128517, 120.8920887);
```

## Troubleshooting

### Issue: "Invalid location format for violation"

**Cause:** Location field is not in a recognized format

**Solution:**

```javascript
// Ensure location is a GeoPoint object in Firebase:
db.collection("geofence_violations").add({
  bike_id: "bike_001",
  location: new firebase.firestore.GeoPoint(14.40128517, 120.8920887),
  timestamp: firebase.firestore.FieldValue.serverTimestamp(),
  violation_type: "GEOFENCE EXIT",
});
```

### Issue: "No zone found for bike"

**Cause:** Bike doesn't have `current_zone_id` set in Firebase

**Solution:**

```bash
# Sync bikes from Firebase
python manage.py sync_bikes

# Or manually set in Firebase Console:
bikes/bike_001/current_zone_id = "zone_malolos"
```

### Issue: "Zone polygon not found"

**Cause:** Zone not synced to PostgreSQL or missing polygon points

**Solution:**

```bash
# Sync zones from Firebase
python manage.py sync_zones --zone-id zone_malolos

# Or sync all zones
python manage.py sync_zones
```

### Issue: False positives being recorded

**Cause:** Polygon points may be incorrect or in wrong order

**Solution:**

1. Check zone polygon in Firebase
2. Ensure points form a closed polygon (at least 3 points)
3. Verify coordinate order (clockwise or counter-clockwise)

### Issue: Listener stops unexpectedly

**Cause:** Network issues or Firebase connection lost

**Solution:**

- Use systemd/supervisor for auto-restart
- Check Firebase credentials
- Review logs for specific errors

## API Reference

### GeofenceViolationListener

```python
from apps.geofencing.violation_listener import GeofenceViolationListener

listener = GeofenceViolationListener()

# Process single violation
violation = listener.process_violation(
    violation_id='abc123',
    violation_data={
        'bike_id': 'bike_001',
        'location': [14.40128517, 120.8920887],
        'timestamp': datetime.now(),
        'violation_type': 'GEOFENCE EXIT'
    }
)

# Process existing violations
processed, created = listener.process_existing_violations(limit=100)

# Start real-time listener
watch = listener.listen_and_process(callback=lambda v: print(f"New: {v}"))
```

## Performance Considerations

- **Real-time listener**: Uses Firestore snapshots (efficient for real-time updates)
- **Batch processing**: Fetches violations in order, limited by `limit` parameter
- **Database queries**: Optimized with select_related and indexes
- **Polygon validation**: O(n) complexity where n = number of polygon points

## Security

- Views require staff or super admin permissions (`@staff_or_super_admin_required`)
- Firebase credentials stored securely in environment variables
- No sensitive data exposed in violation records

## Future Enhancements

- [ ] Add webhook support for external notifications
- [ ] Implement violation severity levels
- [ ] Add automatic resolution for false positives
- [ ] Generate violation reports and analytics
- [ ] SMS/Email alerts for critical violations

## Support

For issues or questions:

1. Check logs: `tail -f logs/django.log`
2. Review Firebase Console for data integrity
3. Test validation with known coordinates
4. Contact development team

---

**Last Updated:** 2025-10-27
**Version:** 1.0.0
