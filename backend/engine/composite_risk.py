"""
AEGIS Composite Risk Model — Nonlinear amplified model with synergistic interaction.
"""
from config import (
    COMPOSITE_AIR_WEIGHT,
    COMPOSITE_HEAT_WEIGHT,
    AMPLIFICATION_COEFFICIENT,
)
from engine.hazard_interactions import compute_hazard_interactions


def calculate_composite_risk(air_score: float, heat_score: float, smoke_score: float, flood_score: float,
                              vector_score: float, water_contamination_score: float,
                              air_confidence: float, heat_confidence: float, smoke_confidence: float) -> dict:
    """
    Nonlinear Composite Risk Model.

    Formula:
        base_weighted = w_air × air_score + w_heat × heat_score
        interaction = (air_score / 100) × (heat_score / 100)
        composite = base_weighted × (1 + α × interaction)

    Where:
        w_air = 0.45, w_heat = 0.45, w_smoke = 0.10 (adjusted for wildcard)
        α = 0.6 (amplification coefficient)

    This reflects synergistic environmental stress:
    when air pollution, heat stress, and smoke risk are elevated,
    the composite risk is amplified beyond a simple weighted average.
    """
    
    # Dynamic weights for 6 hazards
    w_air = 0.25
    w_heat = 0.25 
    w_smoke = 0.10
    w_flood = 0.15
    w_vector = 0.15
    w_water = 0.10
    
    base_weighted = (
        w_air * air_score
        + w_heat * heat_score
        + w_smoke * smoke_score
        + w_flood * flood_score
        + w_vector * vector_score
        + w_water * water_contamination_score
    )

    # Compute Interaction terms
    interactions = compute_hazard_interactions(
        air_score / 100.0,
        heat_score / 100.0,
        smoke_score / 100.0,
        flood_score / 100.0,
        vector_score / 100.0,
        water_contamination_score / 100.0
    )
    
    # Take the total interaction sum to drive the amplifier
    interaction = interactions["total_amplification"]

    # Amplification factor
    amplification = 1.0 + AMPLIFICATION_COEFFICIENT * interaction

    # Final composite with amplification
    composite = base_weighted * amplification
    composite = round(min(100, max(0, composite)), 1)

    # Confidence: weighted average of all model confidences
    confidence = round(
        w_air * air_confidence
        + w_heat * heat_confidence
        + w_smoke * smoke_confidence,
        1,
    )

    return {
        "score": composite,
        "confidence": confidence,
        "base_weighted": round(base_weighted, 1),
        "interaction_term": round(interaction, 4),
        "amplification_factor": round(amplification, 4),
        "air_contribution": round(w_air * air_score, 1),
        "heat_contribution": round(w_heat * heat_score, 1),
        "smoke_contribution": round(w_smoke * smoke_score, 1),
        "flood_contribution": round(w_flood * flood_score, 1),
        "vector_contribution": round(w_vector * vector_score, 1),
        "water_contamination_contribution": round(w_water * water_contamination_score, 1),
        "interactions": interactions,
        "amplification_boost": round(
            base_weighted * (amplification - 1.0), 1
        ),
    }
