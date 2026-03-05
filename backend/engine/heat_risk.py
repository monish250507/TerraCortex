"""
AEGIS Heat Stress Risk Model — Heat Index deviation, persistence, seasonal baseline.
"""
from typing import Optional
from sqlalchemy.orm import Session
from sqlalchemy import desc
from models import ZoneObservation
from engine.baseline import get_baseline, get_zscore, get_percentile_rank


def calculate_heat_risk(
    db: Session, zone_obs: ZoneObservation, current_hour: int
) -> dict:
    """
    Calculate heat stress risk score (0–100) and confidence.

    Components:
    - Heat Index absolute danger level (30% weight)
    - Z-score deviation from seasonal baseline (30% weight)
    - Persistence of elevated heat (25% weight)
    - Rate of temperature change (15% weight)
    """
    heat_index = zone_obs.heat_index
    baseline = get_baseline(db, zone_obs.zone_id, current_hour, "heat_index")

    # ── Heat Index danger level ──
    # Caution starts at 27°C HI, Extreme above 54°C HI
    if heat_index < 27:
        absolute_risk = max(0, (heat_index - 20) * 3)
    elif heat_index < 32:
        absolute_risk = 20 + (heat_index - 27) * 6
    elif heat_index < 40:
        absolute_risk = 50 + (heat_index - 32) * 4
    elif heat_index < 54:
        absolute_risk = 82 + (heat_index - 40) * 1.3
    else:
        absolute_risk = 100

    absolute_risk = min(100, max(0, absolute_risk))

    # ── Z-score deviation ──
    zscore = get_zscore(heat_index, baseline) if baseline else 0.0
    zscore_risk = min(100, max(0, abs(zscore) * 18))

    # ── Persistence ──
    persistence_hours = _count_heat_elevated_hours(db, zone_obs.zone_id, threshold=32)
    persistence_risk = min(100, persistence_hours * 10)

    # ── Rate of change ──
    rate_risk = 0.0
    rate_of_change = 0.0
    recent = (
        db.query(ZoneObservation)
        .filter(ZoneObservation.zone_id == zone_obs.zone_id)
        .order_by(desc(ZoneObservation.timestamp))
        .limit(2)
        .all()
    )
    if len(recent) >= 2:
        rate_of_change = heat_index - recent[1].heat_index
        rate_risk = min(100, max(0, abs(rate_of_change) * 8))

    # ── Weighted composite ──
    score = (
        0.30 * absolute_risk
        + 0.30 * zscore_risk
        + 0.25 * persistence_risk
        + 0.15 * rate_risk
    )
    score = round(min(100, max(0, score)), 1)

    # ── Confidence ──
    confidence = _calculate_confidence(baseline)

    # ── Percentile ──
    percentile = get_percentile_rank(heat_index, baseline) if baseline else 50.0

    return {
        "score": score,
        "confidence": confidence,
        "zscore": round(zscore, 3),
        "rate_of_change": round(rate_of_change, 2),
        "persistence_hours": persistence_hours,
        "percentile": round(percentile, 1),
        "baseline_mean": baseline["mean"] if baseline else None,
        "components": {
            "absolute_risk": round(absolute_risk, 1),
            "zscore_risk": round(zscore_risk, 1),
            "persistence_risk": round(persistence_risk, 1),
            "rate_risk": round(rate_risk, 1),
        },
    }


def _count_heat_elevated_hours(db: Session, zone_id: int, threshold: float = 32) -> int:
    """Count consecutive hours heat index has been above threshold in this zone."""
    readings = (
        db.query(ZoneObservation)
        .filter(ZoneObservation.zone_id == zone_id)
        .order_by(desc(ZoneObservation.timestamp))
        .limit(24)
        .all()
    )
    count = 0
    for r in readings:
        if r.heat_index > threshold:
            count += 1
        else:
            break
    return count


def _calculate_confidence(baseline: Optional[dict]) -> float:
    """Confidence based on baseline data maturity."""
    if not baseline:
        return 35.0
    samples = baseline.get("sample_count", 0)
    if samples >= 168:
        return 95.0
    elif samples >= 48:
        return 80.0
    elif samples >= 24:
        return 65.0
    elif samples >= 6:
        return 50.0
    return 35.0
