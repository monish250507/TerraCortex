"""
AEGIS Public API — Unauthenticated endpoints for the Public Advisory Layer.
"""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import desc

from database import get_db
from models import RiskAssessment, Advisory, EnvironmentalReading, Zone

router = APIRouter(prefix="/api/public", tags=["Public"])


@router.get("/status")
def get_public_status(db: Session = Depends(get_db)):
    """
    Public environmental health status.
    Returns only risk LEVELS (LOW/MODERATE/HIGH) — no scores, no confidence, no formulas.
    """
    latest = (
        db.query(RiskAssessment)
        .order_by(desc(RiskAssessment.timestamp))
        .first()
    )

    if not latest:
        return {
            "overall": "LOW",
            "air_level": "LOW",
            "heat_level": "LOW",
            "vector_level": "LOW",
            "water_contamination_level": "LOW",
            "composite_level": "LOW",
            "last_updated": None,
        }

    return {
        "overall": _level(latest.composite_score),
        "air_level": _level(latest.air_score),
        "heat_level": _level(latest.heat_score),
        "vector_level": latest.vector_risk_level or "LOW",
        "water_contamination_level": latest.water_contamination_risk_level or "LOW",
        "composite_level": _level(latest.composite_score),
        "last_updated": latest.timestamp.isoformat() if latest.timestamp else None,
    }


@router.get("/advisory")
def get_public_advisory(db: Session = Depends(get_db)):
    """
    Latest approved and published advisory for public consumption.
    Only returns advisories that have been government-approved.
    """
    advisory = (
        db.query(Advisory)
        .filter(Advisory.approved == True, Advisory.published == True)
        .order_by(desc(Advisory.published_at))
        .first()
    )

    if not advisory:
        return {
            "has_advisory": False,
            "message": "Environmental conditions in Chennai are within normal parameters. No special precautions required.",
            "severity": "Normal",
            "published_at": None,
        }

    return {
        "has_advisory": True,
        "message": advisory.message,
        "severity": advisory.severity,
        "published_at": advisory.published_at.isoformat() if advisory.published_at else None,
    }


@router.get("/zones/risk")
def get_public_zones_risk(db: Session = Depends(get_db)):
    """
    Aggregated latest risk for all zones for the public interactive map.
    Keyed by Zone Name: { "North": { composite_score: 45, air_score: 30... }... }
    """
    zones = db.query(Zone).all()
    results = {}
    
    for z in zones:
        latest = (
            db.query(RiskAssessment)
            .filter(RiskAssessment.zone_id == z.id)
            .order_by(desc(RiskAssessment.timestamp))
            .first()
        )
        if latest:
            results[z.name] = {
                "composite_score": latest.composite_score,
                "air_score": latest.air_score,
                "heat_score": latest.heat_score,
                "smoke_score": latest.smoke_score or 0.0,
                "flood_score": latest.flood_score or 0.0,
                "vector_risk": latest.vector_risk or 0.0,
                "water_contamination_risk": latest.water_contamination_risk or 0.0,
            }
            
    return results


@router.get("/trends")
def get_public_trends(db: Session = Depends(get_db)):
    """
    Simplified daily trend data for public view.
    Only provides relative values, no raw scores.
    """
    readings = (
        db.query(EnvironmentalReading)
        .order_by(desc(EnvironmentalReading.timestamp))
        .limit(24)
        .all()
    )
    readings.reverse()

    assessments = (
        db.query(RiskAssessment)
        .order_by(desc(RiskAssessment.timestamp))
        .limit(24)
        .all()
    )
    assessments.reverse()

    return {
        "labels": [
            r.timestamp.strftime("%H:%M") if r.timestamp else ""
            for r in readings
        ],
        "air_trend": [
            _level_numeric(a.air_score) for a in assessments
        ],
        "heat_trend": [
            _level_numeric(a.heat_score) for a in assessments
        ],
    }


def _level(score: float) -> str:
    if score < 40:
        return "LOW"
    elif score < 70:
        return "MODERATE"
    return "HIGH"


def _level_numeric(score: float) -> int:
    """Convert score to simplified 1-3 level for public trend."""
    if score < 40:
        return 1
    elif score < 70:
        return 2
    return 3
