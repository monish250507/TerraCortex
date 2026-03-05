"""
AEGIS Government API — Protected endpoints for Intelligence Command Center.
"""
from typing import Optional
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import desc

from database import get_db
from auth import get_current_user, verify_password, create_access_token
from models import (
    GovernmentUser, RiskAssessment, Alert, Advisory,
    IntelligenceFeedEntry, EnvironmentalReading,
)
from engine.explainer import generate_public_advisory
from engine.intervention_simulator import simulate_intervention
from engine.resource_optimizer import optimize_resources

router = APIRouter(prefix="/api/gov", tags=["Government"])


# ── Request/Response Models ──────────────────────────────

class LoginRequest(BaseModel):
    username: str
    password: str


class AdvisoryRequest(BaseModel):
    message: Optional[str] = None
    severity: str = "Moderate"

class SimulateRequest(BaseModel):
    zone_id: int
    interventions: list[str]

class OptimizeRequest(BaseModel):
    total_budget: float


# ── Auth ─────────────────────────────────────────────────

@router.post("/login")
def login(req: LoginRequest, db: Session = Depends(get_db)):
    user = db.query(GovernmentUser).filter(
        GovernmentUser.username == req.username
    ).first()
    if not user or not verify_password(req.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
        )
    token = create_access_token(user.username)
    return {"access_token": token, "token_type": "bearer", "username": user.username}


# ── Dashboard ────────────────────────────────────────────

@router.get("/dashboard")
def get_dashboard(
    db: Session = Depends(get_db),
    user: GovernmentUser = Depends(get_current_user),
):
    latest = (
        db.query(RiskAssessment)
        .order_by(desc(RiskAssessment.timestamp))
        .first()
    )
    if not latest:
        return {
            "air": {"score": 0, "confidence": 0, "trend": "stable", "status": "No Data", "value": 0},
            "heat": {"score": 0, "confidence": 0, "trend": "stable", "status": "No Data", "value": 0},
            "composite": {"score": 0, "confidence": 0, "trend": "stable", "status": "No Data", "value": 0},
            "last_updated": None,
            "active_alerts": 0,
        }

    active_alerts = db.query(Alert).filter(Alert.acknowledged == False).count()

    return {
        "air": {
            "score": latest.air_score,
            "confidence": latest.air_confidence,
            "trend": latest.air_trend,
            "status": _status_label(latest.air_score),
            "value": latest.pm25_value,
            "unit": "µg/m³",
        },
        "heat": {
            "score": latest.heat_score,
            "confidence": latest.heat_confidence,
            "trend": latest.heat_trend,
            "status": _status_label(latest.heat_score),
            "value": latest.heat_index,
            "unit": "°C",
        },
        "composite": {
            "score": latest.composite_score,
            "confidence": latest.composite_confidence,
            "trend": latest.composite_trend,
            "status": _status_label(latest.composite_score),
            "amplification": latest.amplification_factor,
        },
        "last_updated": latest.timestamp.isoformat() if latest.timestamp else None,
        "active_alerts": active_alerts,
    }


# ── Simulation ───────────────────────────────────────────

@router.post("/simulate")
def simulate(
    req: SimulateRequest,
    db: Session = Depends(get_db),
    user: GovernmentUser = Depends(get_current_user),
):
    """Admin endpoint to simulate the effect of interventions."""
    result = simulate_intervention(db, req.zone_id, req.interventions)
    if "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])
    return result

@router.post("/optimize-resources")
def optimize_resource_allocation(
    req: OptimizeRequest,
    db: Session = Depends(get_db),
    user: GovernmentUser = Depends(get_current_user),
):
    """Admin endpoint to recommend resource allocation using PuLP."""
    result = optimize_resources(db, req.total_budget)
    if "error" in result:
        raise HTTPException(status_code=500, detail=result["error"])
    return result


# ── Detailed Intelligence ────────────────────────────────

@router.get("/risk/{risk_type}/detail")
def get_risk_detail(
    risk_type: str,
    db: Session = Depends(get_db),
    user: GovernmentUser = Depends(get_current_user),
):
    if risk_type not in ("air", "heat", "composite"):
        raise HTTPException(status_code=400, detail="Invalid risk type")

    latest = (
        db.query(RiskAssessment)
        .order_by(desc(RiskAssessment.timestamp))
        .first()
    )
    if not latest:
        raise HTTPException(status_code=404, detail="No assessment data available")

    base = {
        "timestamp": latest.timestamp.isoformat() if latest.timestamp else None,
        "intelligence_summary": latest.intelligence_summary,
        "anomaly_flags": latest.anomaly_flags,
        "anomaly_description": latest.anomaly_description,
    }

    if risk_type == "air":
        base.update({
            "score": latest.air_score,
            "confidence": latest.air_confidence,
            "trend": latest.air_trend,
            "current_value": latest.pm25_value,
            "unit": "µg/m³",
            "baseline_mean": latest.pm25_baseline_mean,
            "zscore": latest.pm25_zscore,
            "percentile": latest.pm25_percentile,
            "deviation": round(latest.pm25_value - latest.pm25_baseline_mean, 2) if latest.pm25_value and latest.pm25_baseline_mean else None,
        })
    elif risk_type == "heat":
        base.update({
            "score": latest.heat_score,
            "confidence": latest.heat_confidence,
            "trend": latest.heat_trend,
            "current_value": latest.heat_index,
            "unit": "°C",
            "temperature": latest.temperature,
            "humidity": latest.humidity,
            "baseline_mean": latest.heat_baseline_mean,
            "zscore": latest.heat_zscore,
            "percentile": latest.heat_percentile,
            "deviation": round(latest.heat_index - latest.heat_baseline_mean, 2) if latest.heat_index and latest.heat_baseline_mean else None,
        })
    else:  # composite
        base.update({
            "score": latest.composite_score,
            "confidence": latest.composite_confidence,
            "trend": latest.composite_trend,
            "amplification_factor": latest.amplification_factor,
            "air_score": latest.air_score,
            "heat_score": latest.heat_score,
            "air_contribution": round(0.45 * latest.air_score, 1),
            "heat_contribution": round(0.55 * latest.heat_score, 1),
            "synergistic_boost": round(
                (0.45 * latest.air_score + 0.55 * latest.heat_score)
                * (latest.amplification_factor - 1.0), 1
            ) if latest.amplification_factor else 0,
        })

    return base


# ── Alerts ───────────────────────────────────────────────

@router.get("/alerts")
def get_alerts(
    db: Session = Depends(get_db),
    user: GovernmentUser = Depends(get_current_user),
):
    active = (
        db.query(Alert)
        .filter(Alert.acknowledged == False)
        .order_by(desc(Alert.timestamp))
        .limit(50)
        .all()
    )
    past = (
        db.query(Alert)
        .filter(Alert.acknowledged == True)
        .order_by(desc(Alert.timestamp))
        .limit(50)
        .all()
    )

    def serialize(a):
        return {
            "id": a.id,
            "severity": a.severity,
            "type": a.alert_type,
            "message": a.message,
            "risk_score": a.risk_score,
            "acknowledged": a.acknowledged,
            "timestamp": a.timestamp.isoformat() if a.timestamp else None,
        }

    return {
        "active": [serialize(a) for a in active],
        "past": [serialize(a) for a in past],
    }


@router.post("/alerts/{alert_id}/acknowledge")
def acknowledge_alert(
    alert_id: int,
    db: Session = Depends(get_db),
    user: GovernmentUser = Depends(get_current_user),
):
    alert = db.query(Alert).filter(Alert.id == alert_id).first()
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")
    alert.acknowledged = True
    alert.acknowledged_at = datetime.now(timezone.utc)
    db.commit()
    return {"status": "acknowledged", "id": alert_id}


# ── Advisory ─────────────────────────────────────────────

@router.post("/advisory/generate")
async def generate_advisory(
    db: Session = Depends(get_db),
    user: GovernmentUser = Depends(get_current_user),
):
    latest = (
        db.query(RiskAssessment)
        .order_by(desc(RiskAssessment.timestamp))
        .first()
    )
    if not latest:
        raise HTTPException(status_code=404, detail="No assessment data")

    risk_data = {
        "air_score": latest.air_score,
        "heat_score": latest.heat_score,
        "composite_score": latest.composite_score,
        "pm25": latest.pm25_value,
        "heat_index": latest.heat_index,
    }

    message = await generate_public_advisory(risk_data)
    severity = _status_label(latest.composite_score)

    advisory = Advisory(message=message, severity=severity)
    db.add(advisory)
    db.commit()
    db.refresh(advisory)

    return {
        "id": advisory.id,
        "message": advisory.message,
        "severity": advisory.severity,
        "approved": False,
    }


@router.post("/advisory/{advisory_id}/approve")
def approve_advisory(
    advisory_id: int,
    db: Session = Depends(get_db),
    user: GovernmentUser = Depends(get_current_user),
):
    advisory = db.query(Advisory).filter(Advisory.id == advisory_id).first()
    if not advisory:
        raise HTTPException(status_code=404, detail="Advisory not found")
    advisory.approved = True
    advisory.approved_at = datetime.now(timezone.utc)
    advisory.published = True
    advisory.published_at = datetime.now(timezone.utc)
    db.commit()

    # Log to feed
    entry = IntelligenceFeedEntry(
        entry_type="advisory",
        title="Public Advisory Published",
        content=advisory.message,
        severity=advisory.severity.lower(),
    )
    db.add(entry)
    db.commit()

    return {"status": "approved_and_published", "id": advisory_id}


# ── Intelligence Feed ────────────────────────────────────

@router.get("/feed")
def get_feed(
    limit: int = 50,
    db: Session = Depends(get_db),
    user: GovernmentUser = Depends(get_current_user),
):
    entries = (
        db.query(IntelligenceFeedEntry)
        .order_by(desc(IntelligenceFeedEntry.timestamp))
        .limit(limit)
        .all()
    )
    return [
        {
            "id": e.id,
            "type": e.entry_type,
            "title": e.title,
            "content": e.content,
            "severity": e.severity,
            "timestamp": e.timestamp.isoformat() if e.timestamp else None,
        }
        for e in entries
    ]


# ── Trends ───────────────────────────────────────────────

@router.get("/trends")
def get_trends(
    hours: int = 24,
    db: Session = Depends(get_db),
    user: GovernmentUser = Depends(get_current_user),
):
    assessments = (
        db.query(RiskAssessment)
        .order_by(desc(RiskAssessment.timestamp))
        .limit(hours)
        .all()
    )
    assessments.reverse()

    return {
        "labels": [a.timestamp.strftime("%H:%M") if a.timestamp else "" for a in assessments],
        "air_scores": [a.air_score for a in assessments],
        "heat_scores": [a.heat_score for a in assessments],
        "composite_scores": [a.composite_score for a in assessments],
        "pm25_values": [a.pm25_value for a in assessments],
        "heat_index_values": [a.heat_index for a in assessments],
    }


# ── System Health ────────────────────────────────────────

@router.get("/system-health")
def get_system_health(
    db: Session = Depends(get_db),
    user: GovernmentUser = Depends(get_current_user),
):
    latest_reading = (
        db.query(EnvironmentalReading)
        .order_by(desc(EnvironmentalReading.timestamp))
        .first()
    )
    latest_assessment = (
        db.query(RiskAssessment)
        .order_by(desc(RiskAssessment.timestamp))
        .first()
    )

    return {
        "observer_agent": {
            "status": "Active" if latest_reading else "Waiting",
            "last_run": latest_reading.timestamp.isoformat() if latest_reading and latest_reading.timestamp else None,
        },
        "detection_engine": {
            "status": "Running" if latest_assessment else "Idle",
            "last_run": latest_assessment.timestamp.isoformat() if latest_assessment and latest_assessment.timestamp else None,
        },
        "investigation_engine": {"status": "Operational"},
        "explanation_engine": {"status": "Connected"},
        "autonomy_mode": {"status": "Enabled"},
    }


def _status_label(score: float) -> str:
    if score < 40:
        return "Normal"
    elif score < 70:
        return "Moderate"
    return "High"
