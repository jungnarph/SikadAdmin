"""
Geofence utility functions for point-in-polygon validation
"""
from typing import List, Tuple, Dict
from decimal import Decimal


def point_in_polygon(point: Tuple[float, float], polygon: List[Dict]) -> bool:
    """
    Check if a point is inside a polygon using the ray casting algorithm.

    Args:
        point: Tuple of (latitude, longitude)
        polygon: List of polygon points in format [{"latitude": lat, "longitude": lng}, ...]

    Returns:
        True if point is inside the polygon, False otherwise

    Algorithm:
        Uses ray casting algorithm - draws a ray from the point to infinity
        and counts how many times it intersects with polygon edges.
        Odd number of intersections = inside, even = outside
    """
    if not polygon or len(polygon) < 3:
        return False

    lat, lon = point
    inside = False

    n = len(polygon)
    p1_lat, p1_lon = polygon[0]['latitude'], polygon[0]['longitude']

    for i in range(1, n + 1):
        p2_lat, p2_lon = polygon[i % n]['latitude'], polygon[i % n]['longitude']

        # Check if point's longitude is between polygon edge's longitudes
        if lon > min(p1_lon, p2_lon):
            if lon <= max(p1_lon, p2_lon):
                if lat <= max(p1_lat, p2_lat):
                    # Calculate intersection point
                    if p1_lon != p2_lon:
                        x_intersection = (lon - p1_lon) * (p2_lat - p1_lat) / (p2_lon - p1_lon) + p1_lat

                    # Check if point is on the edge or if ray intersects edge
                    if p1_lon == p2_lon or lat <= x_intersection:
                        inside = not inside

        p1_lat, p1_lon = p2_lat, p2_lon

    return inside


def validate_geofence_exit(
    location: Tuple[float, float],
    polygon: List[Dict]
) -> bool:
    """
    Validate if a location point has actually exited a geofence.

    Args:
        location: Tuple of (latitude, longitude) of the violation point
        polygon: List of polygon points defining the geofence boundary

    Returns:
        True if point is OUTSIDE the polygon (valid exit), False if still inside
    """
    is_inside = point_in_polygon(location, polygon)
    return not is_inside  # Exit is valid if point is NOT inside


def convert_decimal_to_float(value) -> float:
    """Convert Decimal to float for calculations"""
    if isinstance(value, Decimal):
        return float(value)
    return value


def normalize_polygon_points(polygon_points) -> List[Dict]:
    """
    Normalize polygon points to consistent format.
    Handles both array and object formats from Firebase.

    Args:
        polygon_points: Can be:
            - List of dicts: [{"latitude": x, "longitude": y}, ...]
            - List of GeoPoint objects with _latitude and _longitude
            - JSONField from database

    Returns:
        List of normalized dicts: [{"latitude": float, "longitude": float}, ...]
    """
    if not polygon_points:
        return []

    normalized = []
    for point in polygon_points:
        if isinstance(point, dict):
            # Handle Firebase GeoPoint format stored in location field
            if 'location' in point and hasattr(point['location'], '_latitude'):
                normalized.append({
                    'latitude': float(point['location']._latitude),
                    'longitude': float(point['location']._longitude)
                })
            # Handle direct latitude/longitude dict
            elif 'latitude' in point and 'longitude' in point:
                normalized.append({
                    'latitude': convert_decimal_to_float(point['latitude']),
                    'longitude': convert_decimal_to_float(point['longitude'])
                })
        # Handle GeoPoint object directly
        elif hasattr(point, '_latitude') and hasattr(point, '_longitude'):
            normalized.append({
                'latitude': float(point._latitude),
                'longitude': float(point._longitude)
            })

    return normalized