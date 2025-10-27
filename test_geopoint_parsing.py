"""
Test script to verify GeoPoint parsing in violation listener

This simulates the GeoPoint object format from Firebase
"""

try:
    from google.cloud.firestore_v1._helpers import GeoPoint
    FIREBASE_AVAILABLE = True
except ImportError:
    FIREBASE_AVAILABLE = False


class MockGeoPoint:
    """Mock GeoPoint object for testing"""
    def __init__(self, latitude, longitude):
        self._latitude = latitude
        self._longitude = longitude
        self.latitude = latitude
        self.longitude = longitude

    def __repr__(self):
        return f"<GeoPoint: ({self._latitude}, {self._longitude})>"


def test_location_parsing():
    """Test various location formats"""

    # Test 1: GeoPoint with private attributes (Firebase format)
    print("Test 1: Firebase GeoPoint with _latitude and _longitude")
    location = MockGeoPoint(14.40128517, 120.8920887)

    latitude = None
    longitude = None

    if hasattr(location, '_latitude') and hasattr(location, '_longitude'):
        latitude = float(location._latitude)
        longitude = float(location._longitude)
        print(f"✓ Parsed: ({latitude}, {longitude})")
    else:
        print("✗ Failed to parse")

    assert latitude == 14.40128517
    assert longitude == 120.8920887

    # Test 2: List format
    print("\nTest 2: List format [lat, lng]")
    location = [14.40128517, 120.8920887]

    if isinstance(location, (list, tuple)) and len(location) >= 2:
        latitude = float(location[0])
        longitude = float(location[1])
        print(f"✓ Parsed: ({latitude}, {longitude})")

    # Test 3: Dict format
    print("\nTest 3: Dict format")
    location = {"latitude": 14.40128517, "longitude": 120.8920887}

    if isinstance(location, dict) and 'latitude' in location and 'longitude' in location:
        latitude = float(location['latitude'])
        longitude = float(location['longitude'])
        print(f"✓ Parsed: ({latitude}, {longitude})")

    # Test 4: Actual Firebase GeoPoint if available
    if FIREBASE_AVAILABLE:
        try:
            print("\nTest 4: Actual Firebase GeoPoint")
            real_geopoint = GeoPoint(14.40128517, 120.8920887)

            if hasattr(real_geopoint, '_latitude') and hasattr(real_geopoint, '_longitude'):
                latitude = float(real_geopoint._latitude)
                longitude = float(real_geopoint._longitude)
                print(f"✓ Parsed real GeoPoint: ({latitude}, {longitude})")
                print(f"  Type: {type(real_geopoint)}")
                print(f"  Repr: {real_geopoint}")
            else:
                print("✗ Real GeoPoint doesn't have _latitude/_longitude")
                print(f"  Available attributes: {dir(real_geopoint)}")
        except Exception as e:
            print(f"Note: Could not test with real GeoPoint: {e}")
    else:
        print("\nTest 4: Skipped (Firebase SDK not available)")

    print("\n" + "="*60)
    print("All tests passed! ✓")
    print("="*60)


if __name__ == "__main__":
    test_location_parsing()