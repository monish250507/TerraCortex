"""
AEGIS Integration Test Suite
Validates the entire environmental intelligence pipeline, per-zone processing,
database persistence, and resilience to simulated API failures.
"""

import sys
import os
import time
import logging
import asyncio
import traceback
from unittest import mock

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger("aegis.tests")

def run_integration_test():
    """Runs the full autonomous pipeline and validates the outputs."""
    # Ensure backend path is in sys.path
    backend_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'backend'))
    sys.path.append(backend_path)
    
    from database import SessionLocal, engine
    from models import Zone, ZoneObservation, RiskAssessment, IntelligenceFeedEntry, Base
    from main import autonomous_cycle
    
    # 1. Setup Database
    logger.info("Setting up test database...")
    Base.metadata.drop_all(bind=engine) # Start fresh for deterministic counts
    Base.metadata.create_all(bind=engine)
    
    db = SessionLocal()
    
    # Seed Zones
    from scripts.seed_zones import seed_zones
    seed_zones()
    
    expected_zones = db.query(Zone).count()
    if expected_zones != 5:
        logger.error(f"Failed to seed 5 zones. Found {expected_zones}.")
        return False
        
    logger.info(f"Successfully configured {expected_zones} zones.")

    # 2. Run Pipeline - Normal Conditions
    logger.info("Executing normal autonomous cycle...")
    start_time = time.time()
    
    # Force use of simulated data or mock the APIs since we don't have real keys
    with mock.patch('engine.spatial_mapper.assign_reading_to_zone') as mock_spatial, \
         mock.patch('config.USE_SIMULATED_DATA', True):
        # We don't strictly mock fetch functions since USE_SIMULATED_DATA handles OpenAQ/OpenWeather
        # But we need to ensure smoke_risk doesn't crash without NASA keys
        try:
            asyncio.run(autonomous_cycle())
            success_normal = True
        except Exception as e:
            tb = traceback.format_exc()
            logger.error(f"Pipeline crashed during normal execution: {e}\n{tb}")
            with open("traceback_dump.txt", "w", encoding="utf-8") as f:
                f.write(tb)
            success_normal = False
            
    exec_time_normal = time.time() - start_time
    logger.info(f"Normal cycle execution took {exec_time_normal:.2f} seconds.")

    # 3. Verify Database Persistence (Normal)
    if success_normal:
        obs_count = db.query(ZoneObservation).count()
        risk_count = db.query(RiskAssessment).count()
        feed_count = db.query(IntelligenceFeedEntry).count()
        
        logger.info(f"Database Records -> ZoneObservations: {obs_count}, RiskAssessments: {risk_count}, Feed Entries: {feed_count}")
        print(f"DEBUG: obs={obs_count}, risk={risk_count}, feed={feed_count}")
        
        if obs_count < 5 or risk_count < 5:
            logger.error(f"Failed to generate observations or assessments for all 5 zones. (obs: {obs_count}, risk: {risk_count})")
            success_normal = False
            
    # 4. Run Pipeline - API Failures
    logger.info("Executing API failure simulation cycle...")
    start_time = time.time()
    
    # Mock network fetching to raise exceptions
    with mock.patch('services.air_quality.AirQualityService.fetch_pm25', side_effect=Exception("OpenAQ Timeout")), \
         mock.patch('services.weather.WeatherService.fetch_weather', side_effect=Exception("Weather API Timeout")), \
         mock.patch('engine.smoke_risk.fetch_firms_hotspots', side_effect=Exception("NASA FIRMS Error")):
        
        try:
            asyncio.run(autonomous_cycle())
            success_failures = True
            logger.info("Pipeline gracefully handled API failures without crashing.")
        except Exception as e:
            tb = traceback.format_exc()
            logger.error(f"Pipeline crashed during API failure simulation: {e}\n{tb}")
            with open("traceback_dump.txt", "a", encoding="utf-8") as f:
                f.write("\n\n" + tb)
            success_failures = False
            
    exec_time_failures = time.time() - start_time
    logger.info(f"Failure simulation cycle took {exec_time_failures:.2f} seconds.")

    # 5. Output Report
    print("=" * 50)
    print("AEGIS INTEGRATION TEST REPORT")
    print("=" * 50)
    print(f"Normal Cycle Status:      {'PASS' if success_normal else 'FAIL'} ({exec_time_normal:.2f}s)")
    print(f"Failure Handling Status:  {'PASS' if success_failures else 'FAIL'} ({exec_time_failures:.2f}s)")
    print(f"Zones Populated:          {expected_zones}/5")
    
    db.close()
    
    total_success = success_normal and success_failures
    return total_success

if __name__ == "__main__":
    if run_integration_test():
        logger.info("All integration tests passed successfully.")
        sys.exit(0)
    else:
        logger.error("Integration tests failed.")
        sys.exit(1)
