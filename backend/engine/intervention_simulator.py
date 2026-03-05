"""
AEGIS Intervention Simulator — Models hazard risk reductions from active interventions.
"""
from typing import List, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import desc
from models import RiskAssessment
import logging

logger = logging.getLogger("aegis.engine.interventions")

def simulate_intervention(db: Session, zone_id: int, interventions: List[str]) -> Dict[str, Any]:
    """
    Simulate the effect of various interventions on the latest risk assessment for a zone.
    
    Supported interventions:
    - cooling_centers: reduce heat risk by 25%
    - mask_distribution: reduce air exposure by 20%
    - drainage_activation: reduce flood risk by 40%
    - air_quality_advisory: reduce air risk by 10%
    """
    from engine.composite_risk import calculate_composite_risk # Import here to avoid circular imports dynamically

    # Fetch latest RiskAssessment for the zone
    latest_assessment = (
        db.query(RiskAssessment)
        .filter(RiskAssessment.zone_id == zone_id)
        .order_by(desc(RiskAssessment.timestamp))
        .first()
    )
    
    if not latest_assessment:
        return {"error": f"No baseline assessments found for zone {zone_id}"}
        
    baseline_composite_risk = latest_assessment.composite_score
    
    # Extract current components
    proj_air = latest_assessment.air_score or 0.0
    proj_heat = latest_assessment.heat_score or 0.0
    proj_smoke = latest_assessment.smoke_score or 0.0
    proj_flood = latest_assessment.flood_score or 0.0
    
    proj_air_conf = latest_assessment.air_confidence or 80.0
    proj_heat_conf = latest_assessment.heat_confidence or 80.0
    proj_smoke_conf = latest_assessment.smoke_confidence or 80.0
    
    # Apply modifications
    has_modifications = False
    
    for intervention in interventions:
        if intervention == "cooling_centers":
            proj_heat *= 0.75
            has_modifications = True
        elif intervention == "mask_distribution":
            proj_air *= 0.80
            has_modifications = True
        elif intervention == "drainage_activation":
            proj_flood *= 0.60
            has_modifications = True
        elif intervention == "air_quality_advisory":
            proj_air *= 0.90
            has_modifications = True
        else:
            logger.warning(f"Unknown intervention requested: {intervention}")
            
    # Cap values
    proj_heat = min(100.0, max(0.0, proj_heat))
    proj_air = min(100.0, max(0.0, proj_air))
    proj_smoke = min(100.0, max(0.0, proj_smoke))
    proj_flood = min(100.0, max(0.0, proj_flood))

    if not has_modifications:
        return {
            "baseline_composite_risk": baseline_composite_risk,
            "projected_risk": baseline_composite_risk,
            "risk_reduction_percentage": 0.0,
            "confidence_estimate": latest_assessment.composite_confidence
        }
        
    # Recalculate composite risk
    projected_result = calculate_composite_risk(
        air_score=proj_air,
        heat_score=proj_heat,
        smoke_score=proj_smoke,
        flood_score=proj_flood,
        air_confidence=proj_air_conf,
        heat_confidence=proj_heat_conf,
        smoke_confidence=proj_smoke_conf
    )
    
    projected_risk = projected_result["score"]
    
    # Calculate metrics
    reduction = baseline_composite_risk - projected_risk
    if baseline_composite_risk > 0:
        reduction_percentage = (reduction / baseline_composite_risk) * 100.0
    else:
        reduction_percentage = 0.0
        
    # The simulation naturally has lower confidence than empirical measurements
    confidence_estimate = max(0.0, projected_result["confidence"] - 15.0)
    
    return {
        "baseline_composite_risk": round(baseline_composite_risk, 1),
        "projected_risk": projected_risk,
        "risk_reduction_percentage": round(reduction_percentage, 1),
        "confidence_estimate": round(confidence_estimate, 1)
    }
