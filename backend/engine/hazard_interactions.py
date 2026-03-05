"""
AEGIS Hazard Interactions Engine — Models deterministic synergistic effects between hazards.
"""
from typing import Dict, Any

def compute_hazard_interactions(
    air_risk: float, # 0-1 (if 0-100 is passed, normalize first)
    heat_risk: float, # 0-1
    smoke_risk: float, # 0-1
    flood_risk: float # 0-1
) -> Dict[str, float]:
    """
    Compute interaction terms and return total amplification.
    
    Expected inputs are in the [0, 1] range.
    Returns individual amplification components and the sum of interaction terms.
    
    Interactions:
    - air + heat
    - smoke + air
    - smoke + heat
    - flood + heat
    """
    
    # Example deterministic scale rules
    heat_air_amplification = air_risk * heat_risk * 0.3
    smoke_air_amplification = smoke_risk * air_risk * 0.4
    smoke_heat_amplification = smoke_risk * heat_risk * 0.25
    flood_heat_amplification = flood_risk * heat_risk * 0.15
    
    total_interaction = (
        heat_air_amplification + 
        smoke_air_amplification + 
        smoke_heat_amplification + 
        flood_heat_amplification
    )
    
    return {
        "heat_air": heat_air_amplification,
        "smoke_air": smoke_air_amplification,
        "smoke_heat": smoke_heat_amplification,
        "flood_heat": flood_heat_amplification,
        "total_amplification": total_interaction
    }
