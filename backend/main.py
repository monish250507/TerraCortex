"""
AEGIS — Autonomous Environmental Guardian & Intelligence System
Main Application Entry Point

FastAPI server with:
- APScheduler for hourly autonomous observation cycles
- Government + Public API routers
- Static file serving for frontend
- Database initialization and admin seeding
"""
import asyncio
import logging
from contextlib import asynccontextmanager
from datetime import datetime, timezone

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, HTMLResponse
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from database import init_db, SessionLocal
from auth import seed_admin
from routers import government, public as public_router
from engine.observer import run_observation_cycle
from engine.baseline import update_baselines
from engine.air_risk import calculate_air_risk
from engine.heat_risk import calculate_heat_risk
from engine.composite_risk import calculate_composite_risk
from engine.anomaly import detect_anomalies
from engine.alert import evaluate_alerts, classify_severity
from engine.explainer import generate_intelligence_summary
from models import RiskAssessment, IntelligenceFeedEntry

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("AEGIS")

scheduler = AsyncIOScheduler()


async def autonomous_cycle():
    """
    Complete autonomous intelligence cycle:
    1. Observe — fetch environmental data
    2. Baseline — update rolling baselines
    3. Analyze — compute risk scores
    4. Detect — check for anomalies
    5. Alert — trigger alerts if thresholds exceeded
    6. Explain — generate intelligence summary
    """
    db = SessionLocal()
    try:
        logger.info("═══ AEGIS Autonomous Cycle Started ═══")

        # 1. Observe
        reading = await run_observation_cycle(db)
        if not reading:
            logger.warning("Observation cycle returned no data")
            return
        logger.info(f"Observed: PM2.5={reading.pm25:.1f}, Temp={reading.temperature:.1f}°C, "
                     f"HI={reading.heat_index:.1f}°C")

        # 2. Update baselines
        update_baselines(db)

        # 3. Calculate risk scores
        current_hour = datetime.now().hour

        air_result = calculate_air_risk(db, reading.pm25, current_hour)
        heat_result = calculate_heat_risk(db, reading.heat_index, current_hour)
        composite_result = calculate_composite_risk(
            air_result["score"], heat_result["score"],
            air_result["confidence"], heat_result["confidence"]
        )

        logger.info(f"Risk Scores — Air: {air_result['score']:.1f}, "
                     f"Heat: {heat_result['score']:.1f}, "
                     f"Composite: {composite_result['score']:.1f}")

        # 4. Detect anomalies
        anomaly_data = detect_anomalies(db, reading.pm25, reading.heat_index, current_hour)

        # 5. Determine trends
        air_trend = _compute_trend(db, "air")
        heat_trend = _compute_trend(db, "heat")
        composite_trend = _compute_trend(db, "composite")

        # 6. Generate intelligence summary
        risk_data = {
            "air_score": air_result["score"],
            "heat_score": heat_result["score"],
            "composite_score": composite_result["score"],
            "pm25": reading.pm25,
            "heat_index": reading.heat_index,
            "pm25_zscore": air_result["zscore"],
            "heat_zscore": heat_result["zscore"],
            "amplification_factor": composite_result["amplification_factor"],
            "anomaly_flags": anomaly_data.get("flags", []),
        }
        summary = await generate_intelligence_summary(risk_data)

        # Store assessment
        assessment = RiskAssessment(
            air_score=air_result["score"],
            air_confidence=air_result["confidence"],
            heat_score=heat_result["score"],
            heat_confidence=heat_result["confidence"],
            composite_score=composite_result["score"],
            composite_confidence=composite_result["confidence"],
            air_trend=air_trend,
            heat_trend=heat_trend,
            composite_trend=composite_trend,
            anomaly_flags=anomaly_data.get("flags"),
            anomaly_description="; ".join(anomaly_data.get("descriptions", [])),
            pm25_value=reading.pm25,
            temperature=reading.temperature,
            humidity=reading.humidity,
            heat_index=reading.heat_index,
            pm25_zscore=air_result["zscore"],
            heat_zscore=heat_result["zscore"],
            pm25_baseline_mean=air_result.get("baseline_mean"),
            heat_baseline_mean=heat_result.get("baseline_mean"),
            pm25_percentile=air_result.get("percentile"),
            heat_percentile=heat_result.get("percentile"),
            amplification_factor=composite_result["amplification_factor"],
            intelligence_summary=summary,
        )
        db.add(assessment)

        # Intelligence feed entry
        feed = IntelligenceFeedEntry(
            entry_type="risk_update",
            title="Risk Assessment Updated",
            content=(
                f"Air Risk: {air_result['score']:.1f}/100 ({classify_severity(air_result['score'])}) | "
                f"Heat Risk: {heat_result['score']:.1f}/100 ({classify_severity(heat_result['score'])}) | "
                f"Composite: {composite_result['score']:.1f}/100 ({classify_severity(composite_result['score'])})"
            ),
            severity=classify_severity(composite_result["score"]).lower(),
        )
        db.add(feed)
        db.commit()

        # 7. Evaluate alerts
        evaluate_alerts(
            db,
            air_result["score"],
            heat_result["score"],
            composite_result["score"],
            anomaly_data,
        )

        logger.info("═══ AEGIS Autonomous Cycle Complete ═══")

    except Exception as e:
        logger.error(f"Autonomous cycle error: {e}", exc_info=True)
    finally:
        db.close()


def _compute_trend(db, risk_type: str) -> str:
    """Compute trend direction from last 3 assessments."""
    from sqlalchemy import desc
    recent = (
        db.query(RiskAssessment)
        .order_by(desc(RiskAssessment.timestamp))
        .limit(3)
        .all()
    )
    if len(recent) < 2:
        return "stable"

    if risk_type == "air":
        scores = [r.air_score for r in recent]
    elif risk_type == "heat":
        scores = [r.heat_score for r in recent]
    else:
        scores = [r.composite_score for r in recent]

    # Compare newest to oldest
    diff = scores[0] - scores[-1]
    if diff > 3:
        return "up"
    elif diff < -3:
        return "down"
    return "stable"


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan: startup and shutdown."""
    # ── Startup ──
    logger.info("╔════════════════════════════════════════╗")
    logger.info("║   AEGIS — System Initializing...       ║")
    logger.info("╚════════════════════════════════════════╝")

    init_db()
    logger.info("Database initialized")

    db = SessionLocal()
    seed_admin(db)
    db.close()
    logger.info("Admin user seeded")

    # Run initial observation cycle
    await autonomous_cycle()
    logger.info("Initial observation cycle completed")

    # Schedule hourly autonomous cycles
    scheduler.add_job(
        autonomous_cycle,
        "interval",
        minutes=60,
        id="aegis_autonomous_cycle",
        replace_existing=True,
    )
    scheduler.start()
    logger.info("APScheduler started — hourly autonomous cycles enabled")

    logger.info("╔════════════════════════════════════════╗")
    logger.info("║   AEGIS — System Online                ║")
    logger.info("╚════════════════════════════════════════╝")

    yield

    # ── Shutdown ──
    scheduler.shutdown(wait=False)
    logger.info("AEGIS shutting down")


# ── App Creation ─────────────────────────────────────────

app = FastAPI(
    title="AEGIS",
    description="Autonomous Environmental Guardian & Intelligence System",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount routers
app.include_router(government.router)
app.include_router(public_router.router)

# Serve frontend static files
import os
FRONTEND_DIR = os.path.join(os.path.dirname(__file__), "..", "frontend")

if os.path.isdir(FRONTEND_DIR):
    app.mount("/static", StaticFiles(directory=FRONTEND_DIR), name="static")


@app.get("/", response_class=HTMLResponse)
async def serve_root():
    """Serve root page - redirect to government login."""
    return HTMLResponse("""
    <html>
        <head>
            <meta http-equiv="refresh" content="0; url=/admin/aegis_admin_2026">
            <title>AEGIS - Redirecting...</title>
        </head>
        <body>
            <p>Redirecting to <a href="/admin/aegis_admin_2026">Government Login</a>...</p>
        </body>
    </html>
    """)


@app.get("/admin/aegis_admin_2026", response_class=HTMLResponse)
async def serve_government():
    """Serve Government Intelligence Command Center."""
    index_path = os.path.join(FRONTEND_DIR, "index.html")
    if os.path.exists(index_path):
        return FileResponse(index_path)
    return HTMLResponse("<h1>AEGIS — Frontend not found</h1>")


@app.get("/public", response_class=HTMLResponse)
async def serve_public():
    """Serve Public Advisory Layer."""
    public_path = os.path.join(FRONTEND_DIR, "public.html")
    if os.path.exists(public_path):
        return FileResponse(public_path)
    return HTMLResponse("<h1>AEGIS Public — Not found</h1>")


@app.get("/health")
async def health_check():
    return {"status": "operational", "system": "AEGIS", "version": "1.0.0"}


# ── Manual trigger for testing ───────────────────────────

@app.post("/api/trigger-cycle")
async def trigger_cycle():
    """Manually trigger an autonomous cycle (for testing/demo)."""
    await autonomous_cycle()
    return {"status": "cycle_complete"}
