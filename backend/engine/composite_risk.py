"""
AEGIS Composite Risk Model — Nonlinear amplified model with synergistic interaction.
"""
from config import (
    COMPOSITE_AIR_WEIGHT,
    COMPOSITE_HEAT_WEIGHT,
    AMPLIFICATION_COEFFICIENT,
)


def calculate_composite_risk(air_score: float, heat_score: float,
                              air_confidence: float, heat_confidence: float) -> dict:
    """
    Nonlinear Composite Risk Model.

    Formula:
        base_weighted = w_air × air_score + w_heat × heat_score
        interaction = (air_score / 100) × (heat_score / 100)
        composite = base_weighted × (1 + α × interaction)

    Where:
        w_air = 0.45, w_heat = 0.55
        α = 0.6 (amplification coefficient)

    This reflects synergistic environmental stress:
    when BOTH air pollution AND heat stress are elevated,
    the composite risk is amplified beyond a simple weighted average.
    """
    base_weighted = (
        COMPOSITE_AIR_WEIGHT * air_score
        + COMPOSITE_HEAT_WEIGHT * heat_score
    )

    # Interaction term: normalized product of both risks
    interaction = (air_score / 100.0) * (heat_score / 100.0)

    # Amplification factor
    amplification = 1.0 + AMPLIFICATION_COEFFICIENT * interaction

    # Final composite with amplification
    composite = base_weighted * amplification
    composite = round(min(100, max(0, composite)), 1)

    # Confidence: weighted average of both model confidences
    confidence = round(
        COMPOSITE_AIR_WEIGHT * air_confidence
        + COMPOSITE_HEAT_WEIGHT * heat_confidence,
        1,
    )

    return {
        "score": composite,
        "confidence": confidence,
        "base_weighted": round(base_weighted, 1),
        "interaction_term": round(interaction, 4),
        "amplification_factor": round(amplification, 4),
        "air_contribution": round(COMPOSITE_AIR_WEIGHT * air_score, 1),
        "heat_contribution": round(COMPOSITE_HEAT_WEIGHT * heat_score, 1),
        "amplification_boost": round(
            base_weighted * (amplification - 1.0), 1
        ),
    }
