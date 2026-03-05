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
from engine.zone_manager import load_all_zones, generate_zone_observations
from engine.smoke_risk import fetch_firms_hotspots, compute_zone_smoke_risk
from engine.flood_risk import calculate_flood_risk
from engine.vector_risk import calculate_vector_risk
from engine.water_contamination_risk import calculate_water_contamination_risk
from models import RiskAssessment, IntelligenceFeedEntry, Zone

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

        # 1. Observe (Global)
        global_reading = await run_observation_cycle(db)
        if not global_reading:
            logger.warning("Observation cycle returned no data")
            return
        logger.info(f"Observed Global: PM2.5={global_reading.pm25:.1f}, Temp={global_reading.temperature:.1f}°C, "
                     f"HI={global_reading.heat_index:.1f}°C")

        # 2. Zone Mapping
        zones = load_all_zones(db)
        if not zones:
            logger.error("No zones found in database. Please run seeder.")
            return
            
        zone_observations = generate_zone_observations(db, global_reading, zones)
        
        # 3. Fetch Smoke Data
        hotspots = await fetch_firms_hotspots()
        smoke_risks = compute_zone_smoke_risk(hotspots, zones)

        # 4. Process Each Zone
        current_hour = datetime.now().hour
        
        # Update zone baselines (now handled internally per zone in baseline.py but called here)
        update_baselines(db)

        for z_obs in zone_observations:
            zid = z_obs.zone_id
            
            air_result = calculate_air_risk(db, z_obs, current_hour)
            heat_result = calculate_heat_risk(db, z_obs, current_hour)
            flood_result = calculate_flood_risk(db, z_obs, current_hour)
            vector_result = calculate_vector_risk(db, z_obs, current_hour)
            water_contamination_result = calculate_water_contamination_risk(db, z_obs, current_hour)
            
            s_risk = smoke_risks[zid]
            
            composite_result = calculate_composite_risk(
                air_result["score"], heat_result["score"], s_risk["smoke_risk"] * 100.0, flood_result["flood_score"] * 100.0,
                vector_result["vector_risk_score"] * 100.0, water_contamination_result["contamination_risk_score"] * 100.0,
                air_result["confidence"], heat_result["confidence"], s_risk["confidence_score"]
            )

            # Detect anomalies per zone
            anomaly_data = detect_anomalies(db, z_obs, current_hour)

            # Determine trends per zone
            air_trend = _compute_trend(db, "air", zid)
            heat_trend = _compute_trend(db, "heat", zid)
            composite_trend = _compute_trend(db, "composite", zid)

            # 5. Generate intelligence summary (only if needed/anomalous to save tokens, but for now we generate per zone if anomalous or >40)
            risk_data = {
                "air_score": air_result["score"],
                "heat_score": heat_result["score"],
                "smoke_score": s_risk["smoke_risk"] * 100.0,
                "flood_score": flood_result["flood_score"] * 100.0,
                "vector_score": vector_result["vector_risk_score"] * 100.0,
                "water_contamination_score": water_contamination_result["contamination_risk_score"] * 100.0,
                "composite_score": composite_result["score"],
                "pm25": z_obs.pm25,
                "heat_index": z_obs.heat_index,
            "pm25_zscore": air_result["zscore"],
            "heat_zscore": heat_result["zscore"],
            "amplification_factor": composite_result["amplification_factor"],
            "anomaly_flags": anomaly_data.get("flags", []),
        }
            summary = await generate_intelligence_summary(risk_data)
    
            # Store assessment
            assessment = RiskAssessment(
                zone_id=zid,
                air_score=air_result["score"],
                air_confidence=air_result["confidence"],
                heat_score=heat_result["score"],
                heat_confidence=heat_result["confidence"],
                composite_score=composite_result["score"],
                composite_confidence=composite_result["confidence"],
                smoke_score=s_risk["smoke_risk"] * 100.0,
                smoke_confidence=s_risk["confidence_score"],
                flood_score=flood_result["flood_score"] * 100.0,
                flood_alert_level=flood_result["flood_alert_level"],
                vector_risk=vector_result["vector_risk_score"] * 100.0,
                vector_risk_level=vector_result["risk_level"],
                water_contamination_risk=water_contamination_result["contamination_risk_score"] * 100.0,
                water_contamination_risk_level=water_contamination_result["risk_level"],
                hotspot_count=s_risk["hotspot_count"],
                air_trend=air_trend,
                heat_trend=heat_trend,
                composite_trend=composite_trend,
                anomaly_flags=anomaly_data.get("flags"),
                anomaly_description="; ".join(anomaly_data.get("descriptions", [])),
                pm25_value=z_obs.pm25,
                temperature=z_obs.temperature,
                humidity=z_obs.humidity,
                heat_index=z_obs.heat_index,
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
    
            # Intelligence feed entry per zone if severe
            if composite_result["score"] >= 70 or anomaly_data.get("flags"):
                zone_name = next((z.name for z in zones if z.id == zid), f"Zone {zid}")
                feed = IntelligenceFeedEntry(
                    entry_type="risk_update",
                    title=f"Risk Alert: {zone_name}",
                    content=(
                        f"Air: {air_result['score']:.1f} | Heat: {heat_result['score']:.1f} | "
                        f"Smoke: {s_risk['smoke_risk']*100:.1f} | Flood: {flood_result['flood_score']*100:.1f} | "
                        f"Composite: {composite_result['score']:.1f}"
                    ),
                    severity=classify_severity(composite_result["score"]).lower(),
                )
                db.add(feed)
                
            db.commit()
    
            # 6. Evaluate alerts (passing zone data)
            # Adapting global alerts for now, but ideally alerts are zone specific
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


def _compute_trend(db, risk_type: str, zone_id: int) -> str:
    """Compute trend direction from last 3 assessments for a zone."""
    from sqlalchemy import desc
    recent = (
        db.query(RiskAssessment)
        .filter(RiskAssessment.zone_id == zone_id)
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
