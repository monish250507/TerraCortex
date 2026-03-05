"""
AEGIS Flood Risk Engine — Assesses localized flood risks.
"""
from typing import Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import desc
from datetime import datetime, timedelta, timezone
from models import ZoneObservation

def calculate_flood_risk(
    db: Session, zone_obs: ZoneObservation, current_hour: int
) -> Dict[str, Any]:
    """
    Compute flood risk per zone.
    
    Inputs:
    - rain_3h (normalized)
    - rain_24h (normalized)
    - humidity_index
    
    Formula:
    flood_score = 0.5 * normalized_rain_3h + 0.3 * normalized_rain_24h + 0.2 * humidity_index
    """
    zid = zone_obs.zone_id
    
    # Fetch recent readings to compute 3h and 24h rainfall
    now = zone_obs.timestamp or datetime.now(timezone.utc)
    cutoff_24h = now - timedelta(hours=24)
    
    recent_readings = (
        db.query(ZoneObservation)
        .filter(ZoneObservation.zone_id == zid)
        .filter(ZoneObservation.timestamp >= cutoff_24h)
        .order_by(desc(ZoneObservation.timestamp))
        .all()
    )
    
    # Calculate accumulated rainfall
    rain_3h = 0.0
    rain_24h = 0.0
    
    # Ensure current observation's rainfall is included
    current_rain = zone_obs.rainfall or 0.0
    
    cutoff_3h = now - timedelta(hours=3)
    
    # We add current observation since it might not be in DB yet during evaluation
    rain_3h += current_rain
    rain_24h += current_rain
    
    for r in recent_readings:
        # Avoid double-counting if the current observation is already in DB
        if r.id == zone_obs.id:
            continue
            
        rain_val = r.rainfall or 0.0
        rain_24h += rain_val
        if r.timestamp and r.timestamp >= cutoff_3h:
            rain_3h += rain_val

    # Normalize rainfall (assuming 50mm in 3h is max risk, 150mm in 24h is max risk)
    # Adjust thresholds based on regional climate if needed
    normalized_rain_3h = min(1.0, rain_3h / 50.0)
    normalized_rain_24h = min(1.0, rain_24h / 150.0)
    
    # Humidity index (0-1)
    humidity_index = min(1.0, max(0.0, zone_obs.humidity / 100.0))
    
    # Compute score
    flood_score = (
        0.5 * normalized_rain_3h +
        0.3 * normalized_rain_24h +
        0.2 * humidity_index
    )
    
    # Ensure bounds
    flood_score = min(1.0, max(0.0, flood_score))
    
    # Determine alert level
    if flood_score >= 0.8:
        level = "Critical"
    elif flood_score >= 0.6:
        level = "High"
    elif flood_score >= 0.4:
        level = "Warning"
    else:
        level = "Normal"
        
    return {
        "zone_id": zid,
        "flood_score": flood_score,
        "flood_alert_level": level,
        "rain_3h": rain_3h,
        "rain_24h": rain_24h,
        "humidity_index": humidity_index
    }
