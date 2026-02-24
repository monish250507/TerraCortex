"""
AEGIS Alert Logic — Threshold-based alert triggers with severity classification.
"""
from datetime import datetime, timedelta, timezone
from sqlalchemy.orm import Session
from sqlalchemy import desc
from models import Alert, IntelligenceFeedEntry
from config import (
    AIR_RISK_THRESHOLD, HEAT_RISK_THRESHOLD, COMPOSITE_RISK_THRESHOLD,
    SEVERITY_NORMAL_MAX, SEVERITY_MODERATE_MAX, ALERT_COOLDOWN_MINUTES,
)


def classify_severity(score: float) -> str:
    """Classify severity from risk score."""
    if score <= SEVERITY_NORMAL_MAX:
        return "Normal"
    elif score <= SEVERITY_MODERATE_MAX:
        return "Moderate"
    return "High"


def evaluate_alerts(
    db: Session,
    air_score: float,
    heat_score: float,
    composite_score: float,
    anomaly_data: dict,
) -> list[Alert]:
    """
    Evaluate all risk scores and anomaly flags. Generate alerts where thresholds
    are exceeded. Applies cooldown de-duplication.
    """
    alerts = []
    now = datetime.now(timezone.utc)
    cooldown_cutoff = now - timedelta(minutes=ALERT_COOLDOWN_MINUTES)

    # ── Air Risk Alert ──
    if air_score >= AIR_RISK_THRESHOLD:
        severity = classify_severity(air_score)
        if not _recent_alert_exists(db, "air_risk", cooldown_cutoff):
            alert = Alert(
                severity=severity,
                alert_type="air_risk",
                message=f"Air Pollution Risk elevated to {air_score:.1f}/100 — Severity: {severity}",
                risk_score=air_score,
            )
            db.add(alert)
            alerts.append(alert)

    # ── Heat Risk Alert ──
    if heat_score >= HEAT_RISK_THRESHOLD:
        severity = classify_severity(heat_score)
        if not _recent_alert_exists(db, "heat_risk", cooldown_cutoff):
            alert = Alert(
                severity=severity,
                alert_type="heat_risk",
                message=f"Heat Stress Risk elevated to {heat_score:.1f}/100 — Severity: {severity}",
                risk_score=heat_score,
            )
            db.add(alert)
            alerts.append(alert)

    # ── Composite Risk Alert ──
    if composite_score >= COMPOSITE_RISK_THRESHOLD:
        severity = classify_severity(composite_score)
        if not _recent_alert_exists(db, "composite_risk", cooldown_cutoff):
            alert = Alert(
                severity=severity,
                alert_type="composite_risk",
                message=(
                    f"Composite Environmental Risk elevated to {composite_score:.1f}/100 "
                    f"— Synergistic amplification detected — Severity: {severity}"
                ),
                risk_score=composite_score,
            )
            db.add(alert)
            alerts.append(alert)

    # ── Anomaly Alert ──
    if anomaly_data.get("is_anomaly"):
        if not _recent_alert_exists(db, "anomaly", cooldown_cutoff):
            flag_summary = "; ".join(anomaly_data.get("descriptions", [])[:3])
            alert = Alert(
                severity="Moderate" if len(anomaly_data.get("flags", [])) < 3 else "High",
                alert_type="anomaly",
                message=f"Environmental Anomaly Detected: {flag_summary}",
                risk_score=None,
            )
            db.add(alert)
            alerts.append(alert)

    # Log alerts to intelligence feed
    for a in alerts:
        feed_entry = IntelligenceFeedEntry(
            entry_type="alert",
            title=f"⚠ {a.severity} Alert: {a.alert_type.replace('_', ' ').title()}",
            content=a.message,
            severity=a.severity.lower(),
        )
        db.add(feed_entry)

    if alerts:
        db.commit()

    return alerts


def _recent_alert_exists(
    db: Session, alert_type: str, cutoff: datetime
) -> bool:
    """Check if a similar alert was raised within cooldown period."""
    return (
        db.query(Alert)
        .filter(Alert.alert_type == alert_type, Alert.timestamp >= cutoff)
        .first()
        is not None
    )
