"""
AEGIS Anomaly Detection Layer — Multi-method environmental anomaly detection.
"""
from engine.baseline import get_baseline, get_zscore, get_percentile_rank
from config import ANOMALY_ZSCORE_THRESHOLD, ANOMALY_PERCENTILE_THRESHOLD, ANOMALY_RATE_MULTIPLIER
from sqlalchemy.orm import Session
from sqlalchemy import desc
from models import EnvironmentalReading


def detect_anomalies(
    db: Session,
    pm25: float,
    heat_index: float,
    current_hour: int,
) -> dict:
    """
    Detect abnormal environmental states using multiple methods:
    1. Z-score threshold (|z| > 2.5)
    2. Historical percentile rarity (above 95th percentile)
    3. Rate-of-change spike detection (delta > 2× std_dev)
    4. Cross-factor rarity (both PM2.5 and Heat Index anomalous)

    Returns anomaly flags and descriptions.
    """
    flags = []
    descriptions = []
    is_anomaly = False

    pm25_baseline = get_baseline(db, current_hour, "pm25")
    heat_baseline = get_baseline(db, current_hour, "heat_index")

    # ── 1. Z-score threshold ──
    pm25_zscore = get_zscore(pm25, pm25_baseline) if pm25_baseline else 0.0
    heat_zscore = get_zscore(heat_index, heat_baseline) if heat_baseline else 0.0

    pm25_z_anomaly = abs(pm25_zscore) > ANOMALY_ZSCORE_THRESHOLD
    heat_z_anomaly = abs(heat_zscore) > ANOMALY_ZSCORE_THRESHOLD

    if pm25_z_anomaly:
        flags.append("pm25_zscore_anomaly")
        descriptions.append(
            f"PM2.5 z-score {pm25_zscore:.2f} exceeds ±{ANOMALY_ZSCORE_THRESHOLD} threshold"
        )
        is_anomaly = True

    if heat_z_anomaly:
        flags.append("heat_zscore_anomaly")
        descriptions.append(
            f"Heat Index z-score {heat_zscore:.2f} exceeds ±{ANOMALY_ZSCORE_THRESHOLD} threshold"
        )
        is_anomaly = True

    # ── 2. Percentile rarity ──
    pm25_pct = get_percentile_rank(pm25, pm25_baseline) if pm25_baseline else 50.0
    heat_pct = get_percentile_rank(heat_index, heat_baseline) if heat_baseline else 50.0

    if pm25_pct > ANOMALY_PERCENTILE_THRESHOLD:
        flags.append("pm25_percentile_rare")
        descriptions.append(
            f"PM2.5 value at {pm25_pct:.1f}th percentile (above {ANOMALY_PERCENTILE_THRESHOLD}th)"
        )
        is_anomaly = True

    if heat_pct > ANOMALY_PERCENTILE_THRESHOLD:
        flags.append("heat_percentile_rare")
        descriptions.append(
            f"Heat Index at {heat_pct:.1f}th percentile (above {ANOMALY_PERCENTILE_THRESHOLD}th)"
        )
        is_anomaly = True

    # ── 3. Rate-of-change spike ──
    recent = (
        db.query(EnvironmentalReading)
        .order_by(desc(EnvironmentalReading.timestamp))
        .limit(2)
        .all()
    )
    if len(recent) >= 2:
        pm25_delta = abs(pm25 - recent[1].pm25)
        heat_delta = abs(heat_index - recent[1].heat_index)

        pm25_spike_threshold = (
            pm25_baseline["std_dev"] * ANOMALY_RATE_MULTIPLIER
            if pm25_baseline and pm25_baseline["std_dev"] > 0
            else 30.0
        )
        heat_spike_threshold = (
            heat_baseline["std_dev"] * ANOMALY_RATE_MULTIPLIER
            if heat_baseline and heat_baseline["std_dev"] > 0
            else 5.0
        )

        if pm25_delta > pm25_spike_threshold:
            flags.append("pm25_rate_spike")
            descriptions.append(
                f"PM2.5 rate-of-change spike: Δ{pm25_delta:.1f} µg/m³ "
                f"(threshold: {pm25_spike_threshold:.1f})"
            )
            is_anomaly = True

        if heat_delta > heat_spike_threshold:
            flags.append("heat_rate_spike")
            descriptions.append(
                f"Heat Index rate-of-change spike: Δ{heat_delta:.1f}°C "
                f"(threshold: {heat_spike_threshold:.1f})"
            )
            is_anomaly = True

    # ── 4. Cross-factor rarity ──
    pm25_elevated = pm25_z_anomaly or pm25_pct > ANOMALY_PERCENTILE_THRESHOLD
    heat_elevated = heat_z_anomaly or heat_pct > ANOMALY_PERCENTILE_THRESHOLD

    if pm25_elevated and heat_elevated:
        flags.append("cross_factor_anomaly")
        descriptions.append(
            "Cross-factor rarity: Both PM2.5 and Heat Index are simultaneously "
            "in anomalous territory — compound environmental stress detected"
        )

    # ── Policy thresholds (WHO / national standards) ──
    if pm25 > 60:  # India NAAQS 24-hr limit
        flags.append("pm25_policy_breach")
        descriptions.append(
            f"PM2.5 ({pm25:.1f} µg/m³) exceeds India NAAQS 24-hr limit (60 µg/m³)"
        )
        is_anomaly = True

    if heat_index > 41:  # NWS Danger level
        flags.append("heat_danger_level")
        descriptions.append(
            f"Heat Index ({heat_index:.1f}°C) at NWS Danger level (>41°C)"
        )
        is_anomaly = True

    return {
        "is_anomaly": is_anomaly,
        "flags": flags,
        "descriptions": descriptions,
        "pm25_zscore": round(pm25_zscore, 3),
        "heat_zscore": round(heat_zscore, 3),
        "pm25_percentile": round(pm25_pct, 1),
        "heat_percentile": round(heat_pct, 1),
    }
