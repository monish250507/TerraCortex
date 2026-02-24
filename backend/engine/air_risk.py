"""
AEGIS Air Pollution Risk Model — Z-score deviation, rate of change, persistence.
"""
from typing import Optional
from datetime import datetime, timedelta, timezone
from sqlalchemy.orm import Session
from sqlalchemy import desc
from models import EnvironmentalReading
from engine.baseline import get_baseline, get_zscore, get_percentile_rank


def calculate_air_risk(
    db: Session, current_pm25: float, current_hour: int
) -> dict:
    """
    Calculate air pollution risk score (0–100) and confidence.

    Components:
    - Z-score deviation from baseline (40% weight)
    - Rate of change from previous reading (20% weight)
    - Persistence of elevated levels (25% weight)
    - Absolute PM2.5 level (15% weight)
    """
    baseline = get_baseline(db, current_hour, "pm25")

    # ── Z-score component ──
    zscore = get_zscore(current_pm25, baseline) if baseline else 0.0
    zscore_risk = min(100, max(0, abs(zscore) * 20))

    # ── Rate of change ──
    rate_risk = 0.0
    recent = (
        db.query(EnvironmentalReading)
        .order_by(desc(EnvironmentalReading.timestamp))
        .limit(2)
        .all()
    )
    rate_of_change = 0.0
    if len(recent) >= 2:
        prev_pm25 = recent[1].pm25
        rate_of_change = current_pm25 - prev_pm25
        rate_risk = min(100, max(0, abs(rate_of_change) * 2))

    # ── Persistence ──
    persistence_hours = _count_elevated_hours(db, threshold=35)
    persistence_risk = min(100, persistence_hours * 12)

    # ── Absolute level ──
    # WHO guideline: PM2.5 > 15 µg/m³ (24h), > 45 µg/m³ very unhealthy
    absolute_risk = min(100, max(0, (current_pm25 - 10) * 1.5))

    # ── Weighted composite ──
    score = (
        0.40 * zscore_risk
        + 0.20 * rate_risk
        + 0.25 * persistence_risk
        + 0.15 * absolute_risk
    )
    score = round(min(100, max(0, score)), 1)

    # ── Confidence ──
    confidence = _calculate_confidence(baseline)

    # ── Percentile ──
    percentile = get_percentile_rank(current_pm25, baseline) if baseline else 50.0

    return {
        "score": score,
        "confidence": confidence,
        "zscore": round(zscore, 3),
        "rate_of_change": round(rate_of_change, 2),
        "persistence_hours": persistence_hours,
        "percentile": round(percentile, 1),
        "baseline_mean": baseline["mean"] if baseline else None,
        "components": {
            "zscore_risk": round(zscore_risk, 1),
            "rate_risk": round(rate_risk, 1),
            "persistence_risk": round(persistence_risk, 1),
            "absolute_risk": round(absolute_risk, 1),
        },
    }


def _count_elevated_hours(db: Session, threshold: float = 35) -> int:
    """Count consecutive hours PM2.5 has been above threshold."""
    readings = (
        db.query(EnvironmentalReading)
        .order_by(desc(EnvironmentalReading.timestamp))
        .limit(24)
        .all()
    )
    count = 0
    for r in readings:
        if r.pm25 > threshold:
            count += 1
        else:
            break
    return count


def _calculate_confidence(baseline: Optional[dict]) -> float:
    """Confidence based on baseline data maturity."""
    if not baseline:
        return 35.0
    samples = baseline.get("sample_count", 0)
    if samples >= 168:  # Full week hourly
        return 95.0
    elif samples >= 48:
        return 80.0
    elif samples >= 24:
        return 65.0
    elif samples >= 6:
        return 50.0
    return 35.0
