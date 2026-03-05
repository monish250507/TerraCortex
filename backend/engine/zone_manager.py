"""
AEGIS Zone Manager — Manages zone boundaries and aggregates readings per zone.
"""
from typing import List
import random
from sqlalchemy.orm import Session
from models import Zone, EnvironmentalReading, ZoneObservation

def load_all_zones(db: Session) -> List[Zone]:
    """Load all active zones from the database."""
    return db.query(Zone).all()

def generate_zone_observations(db: Session, global_reading: EnvironmentalReading, zones: List[Zone]) -> List[ZoneObservation]:
    """
    Takes a single global city-wide reading and derives localized ZoneObservations 
    for each active zone, simulating micro-climate variations.
    """
    observations = []
    
    # Use hour to seed pseudo-randomness so variations are consistent within the hour
    hour = global_reading.timestamp.hour if global_reading.timestamp else 0
    
    for idx, zone in enumerate(zones):
        # Create deterministic variation based on zone ID and hour
        # Central zones might be hotter/more polluted, coastal zones cooler, etc.
        # Here we just apply a simple mathematical variance.
        
        random.seed(hour + zone.id * 10) 
        
        # Base variance ranges: ±15% for PM2.5, ±5% for Temp/Humidity
        pm25_var = global_reading.pm25 * random.uniform(-0.15, 0.15)
        temp_var = global_reading.temperature * random.uniform(-0.05, 0.05)
        hum_var = global_reading.humidity * random.uniform(-0.05, 0.05)
        hi_var = global_reading.heat_index * random.uniform(-0.05, 0.05)
        
        z_obs = ZoneObservation(
            zone_id=zone.id,
            pm25=max(0, global_reading.pm25 + pm25_var),
            temperature=global_reading.temperature + temp_var,
            humidity=max(0, min(100, global_reading.humidity + hum_var)),
            heat_index=global_reading.heat_index + hi_var,
            rainfall=0.0, # Placeholder
            timestamp=global_reading.timestamp
        )
        
        db.add(z_obs)
        observations.append(z_obs)
        
    db.commit()
    for obs in observations:
        db.refresh(obs)
        
    return observations
