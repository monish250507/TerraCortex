"""
AEGIS Spatial Mapper — Maps environmental readings and external data to zones.
"""
from typing import List, Optional
import math
from models import Zone

def haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculate the great circle distance between two points on the earth in km."""
    R = 6371.0 # Radius of earth in km
    
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    
    a = math.sin(dlat / 2)**2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    
    distance = R * c
    return distance

def get_zone_center(zone: Zone) -> tuple[float, float]:
    """Extract approximate center of a zone from its GeoJSON boundary."""
    if not zone.geojson_boundary or "coordinates" not in zone.geojson_boundary:
        return (0.0, 0.0)
    
    # Assuming simple Polygon: [[[lon, lat], [lon, lat], ...]]
    coords = zone.geojson_boundary["coordinates"][0]
    
    sum_lon = sum(c[0] for c in coords)
    sum_lat = sum(c[1] for c in coords)
    
    center_lon = sum_lon / len(coords)
    center_lat = sum_lat / len(coords)
    
    return (center_lat, center_lon)

def assign_reading_to_zone(lat: Optional[float], lon: Optional[float], zones: List[Zone], fallback_hour: int = 0) -> Zone:
    """
    Map an observation (with lat/lon) to the nearest zone.
    If lat/lon are not provided, uses a deterministic fallback based on the hour
    to simulate varying conditions across zones.
    """
    if not zones:
        raise ValueError("No zones available in the system")

    if lat is not None and lon is not None:
        # Find nearest zone by center point distance
        nearest_zone = None
        min_distance = float('inf')
        
        for zone in zones:
            z_lat, z_lon = get_zone_center(zone)
            if z_lat == 0.0 and z_lon == 0.0:
                continue # Skip zones with no valid geometry
                
            dist = haversine_distance(lat, lon, z_lat, z_lon)
            if dist < min_distance:
                min_distance = dist
                nearest_zone = zone
                
        if nearest_zone:
            return nearest_zone
            
    # Fallback if no coordinates or no valid zone geometries: 
    # Determine zone pseudo-randomly but deterministically based on hour
    zone_index = fallback_hour % len(zones)
    return zones[zone_index]
