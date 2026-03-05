"""
AEGIS Water Contamination Risk Engine — Assesses risk of waterborne disease outbreaks after flooding.
"""
from typing import Dict, Any
from sqlalchemy.orm import Session
from models import ZoneObservation


def calculate_water_contamination_risk(
    db: Session, zone_obs: ZoneObservation, current_hour: int
) -> Dict[str, Any]:
    """
    Compute water contamination risk per zone based on flooding and environmental conditions.
    
    Inputs:
    - flood_risk
    - rainfall
    - temperature
    - humidity
    
    Formula:
    contamination_risk = 0.5 * flood_risk + 0.2 * rainfall_index + 
                        0.2 * temperature_factor + 0.1 * humidity_factor
    """
    zid = zone_obs.zone_id
    
    # Get current values
    rainfall = zone_obs.rainfall or 0.0
    temperature = zone_obs.temperature or 0.0
    humidity = zone_obs.humidity or 0.0
    
    # Get flood risk
    from engine.flood_risk import calculate_flood_risk
    flood_result = calculate_flood_risk(db, zone_obs, current_hour)
    flood_risk = flood_result.get("flood_score", 0.0)
    
    # Calculate rainfall index (normalized, threshold: 100mm for max risk)
    rainfall_threshold = 100.0
    rainfall_index = min(rainfall / rainfall_threshold, 1.0)
    
    # Calculate temperature factor (higher temp increases bacterial growth)
    if temperature > 28.0:
        temperature_factor = 1.0
    else:
        temperature_factor = 0.5
    
    # Calculate humidity factor
    humidity_factor = min(humidity / 100.0, 1.0)
    
    # Compute contamination risk score
    contamination_risk = (
        0.5 * flood_risk +
        0.2 * rainfall_index +
        0.2 * temperature_factor +
        0.1 * humidity_factor
    )
    
    # Ensure bounds
    contamination_risk = min(1.0, max(0.0, contamination_risk))
    
    # Determine risk level
    if contamination_risk >= 0.7:
        risk_level = "HIGH"
    elif contamination_risk >= 0.4:
        risk_level = "MEDIUM"
    else:
        risk_level = "LOW"
    
    return {
        "zone_id": zid,
        "contamination_risk_score": contamination_risk,
        "risk_level": risk_level,
        "flood_risk_contribution": flood_risk,
        "rainfall_index": rainfall_index,
        "temperature_factor": temperature_factor,
        "humidity_factor": humidity_factor
    }
