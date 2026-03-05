"""
AEGIS Baseline Engine — Rolling historical baselines per hour-of-day.
"""
import numpy as np
from typing import Optional, Dict, List
from datetime import datetime, timedelta, timezone
from sqlalchemy.orm import Session
from sqlalchemy import and_
from models import ZoneObservation, BaselineRecord
from config import BASELINE_WINDOW_DAYS, PERCENTILE_BANDS


def update_baselines(db: Session):
    """
    Recalculate baselines from recent readings.
    Maintains rolling 7-day window per hour-of-day for PM2.5 and Heat Index.
    """
    cutoff = datetime.now(timezone.utc) - timedelta(days=BASELINE_WINDOW_DAYS)
    readings = (
        db.query(ZoneObservation)
        .filter(ZoneObservation.timestamp >= cutoff)
        .all()
    )

    if not readings:
        return

    # Group by zone_id, then hour-of-day
    hourly_pm25: Dict[int, Dict[int, List[float]]] = {}
    hourly_heat: Dict[int, Dict[int, List[float]]] = {}

    for r in readings:
        zid = r.zone_id
        hour = r.timestamp.hour if r.timestamp else 0
        
        if zid not in hourly_pm25:
            hourly_pm25[zid] = {}
        if zid not in hourly_heat:
            hourly_heat[zid] = {}
            
        hourly_pm25[zid].setdefault(hour, []).append(r.pm25)
        hourly_heat[zid].setdefault(hour, []).append(r.heat_index)

    # Update baselines for each zone and hour
    for zid in set(list(hourly_pm25.keys()) + list(hourly_heat.keys())):
        for hour in range(24):
            _update_metric_baseline(db, zid, hour, "pm25", hourly_pm25.get(zid, {}).get(hour, []))
            _update_metric_baseline(db, zid, hour, "heat_index", hourly_heat.get(zid, {}).get(hour, []))

    db.commit()


def _update_metric_baseline(
    db: Session, zone_id: int, hour: int, metric: str, values: List[float]
):
    """Update or create baseline record for a specific hour and metric."""
    if not values:
        return

    arr = np.array(values, dtype=float)
    mean = float(np.mean(arr))
    std_dev = float(np.std(arr)) if len(arr) > 1 else 0.0
    percentiles = {
        str(p): float(np.percentile(arr, p)) for p in PERCENTILE_BANDS
    }

    existing = (
        db.query(BaselineRecord)
        .filter(
            and_(
                BaselineRecord.hour_of_day == hour,
                BaselineRecord.metric == metric,
            )
        )
        .first()
    )

    if existing:
        existing.mean = mean
        existing.std_dev = std_dev
        existing.percentile_bands = percentiles
        existing.sample_count = len(values)
    else:
        record = BaselineRecord(
            zone_id=zone_id,
            hour_of_day=hour,
            metric=metric,
            mean=mean,
            std_dev=std_dev,
            percentile_bands=percentiles,
            sample_count=len(values),
        )
        db.add(record)


def get_baseline(db: Session, zone_id: int, hour: int, metric: str) -> Optional[dict]:
    """Retrieve baseline for a given zone, hour and metric."""
    record = (
        db.query(BaselineRecord)
        .filter(
            and_(
                BaselineRecord.hour_of_day == hour,
                BaselineRecord.metric == metric,
            )
        )
        .first()
    )
    if record:
        return {
            "mean": record.mean,
            "std_dev": record.std_dev,
            "percentile_bands": record.percentile_bands or {},
            "sample_count": record.sample_count,
        }
    return None


def get_zscore(value: float, baseline: dict) -> float:
    """Calculate z-score of a value against its baseline."""
    if baseline and baseline["std_dev"] > 0:
        return (value - baseline["mean"]) / baseline["std_dev"]
    return 0.0


def get_percentile_rank(value: float, baseline: dict) -> float:
    """Estimate percentile rank of a value against baseline bands."""
    if not baseline or not baseline.get("percentile_bands"):
        return 50.0

    bands = baseline["percentile_bands"]
    sorted_pcts = sorted(bands.items(), key=lambda x: float(x[0]))

    if value <= float(sorted_pcts[0][1]):
        return float(sorted_pcts[0][0])
    if value >= float(sorted_pcts[-1][1]):
        return min(99.9, float(sorted_pcts[-1][0]) + 4.0)

    # Linear interpolation between bands
    for i in range(len(sorted_pcts) - 1):
        p1, v1 = float(sorted_pcts[i][0]), float(sorted_pcts[i][1])
        p2, v2 = float(sorted_pcts[i + 1][0]), float(sorted_pcts[i + 1][1])
        if v1 <= value <= v2:
            ratio = (value - v1) / (v2 - v1) if v2 != v1 else 0
            return p1 + ratio * (p2 - p1)

    return 50.0
