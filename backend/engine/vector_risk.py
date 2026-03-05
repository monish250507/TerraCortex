"""
AEGIS Vector Disease Risk Engine — Assesses mosquito breeding suitability for diseases like dengue, malaria, chikungunya.
"""
from typing import Dict, Any
from sqlalchemy.orm import Session
from models import ZoneObservation


def calculate_vector_risk(
    db: Session, zone_obs: ZoneObservation, current_hour: int
) -> Dict[str, Any]:
    """
    Compute vector disease risk per zone based on mosquito breeding suitability.
    
    Inputs:
    - rainfall
    - temperature  
    - humidity
    - flood_risk
    
    Formula:
    vector_risk = 0.35 * rainfall_index + 0.25 * humidity_index + 
                  0.25 * temperature_suitability + 0.15 * flood_risk
    """
    zid = zone_obs.zone_id
    
    # Get current values
    rainfall = zone_obs.rainfall or 0.0
    temperature = zone_obs.temperature or 0.0
    humidity = zone_obs.humidity or 0.0
    
    # Calculate rainfall index (threshold: 50mm for max risk)
    rainfall_threshold = 50.0
    rainfall_index = min(rainfall / rainfall_threshold, 1.0)
    
    # Calculate temperature suitability (optimal: 24-32°C)
    if 24.0 <= temperature <= 32.0:
        temperature_suitability = 1.0
    else:
        temperature_suitability = 0.5
    
    # Calculate humidity index
    humidity_index = min(humidity / 100.0, 1.0)
    
    # Get flood risk (we'll need to import and calculate this)
    # For now, assume flood_risk is available or calculate it
    from engine.flood_risk import calculate_flood_risk
    flood_result = calculate_flood_risk(db, zone_obs, current_hour)
    flood_risk = flood_result.get("flood_score", 0.0)
    
    # Compute vector risk score
    vector_risk = (
        0.35 * rainfall_index +
        0.25 * humidity_index +
        0.25 * temperature_suitability +
        0.15 * flood_risk
    )
    
    # Ensure bounds
    vector_risk = min(1.0, max(0.0, vector_risk))
    
    # Determine risk level
    if vector_risk >= 0.7:
        risk_level = "HIGH"
    elif vector_risk >= 0.4:
        risk_level = "MEDIUM"
    else:
        risk_level = "LOW"
    
    return {
        "zone_id": zid,
        "vector_risk_score": vector_risk,
        "risk_level": risk_level,
        "rainfall_index": rainfall_index,
        "humidity_index": humidity_index,
        "temperature_suitability": temperature_suitability,
        "flood_risk_contribution": flood_risk
    }
