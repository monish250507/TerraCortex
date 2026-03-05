"""
AEGIS API Integration Test Suite
Validates public and government endpoints, authentication, and structured outputs.
"""
import sys
import os
import json
import logging
from fastapi.testclient import TestClient

backend_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'backend'))
sys.path.append(backend_path)

from main import app
from database import SessionLocal, init_db, engine
from models import Base
from auth import seed_admin
from config import DEFAULT_ADMIN_USER, DEFAULT_ADMIN_PASS
from scripts.seed_zones import seed_zones

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(message)s")
logger = logging.getLogger("aegis.tests.api")

client = TestClient(app)

def run_api_tests():
    # Setup test environment
    Base.metadata.drop_all(bind=engine)
    init_db()
    
    db = SessionLocal()
    seed_admin(db)
    db.close()
    
    seed_zones()
    
    # We need to run the autonomous cycle once to populate RiskAssessment and Feed, else some endpoints will return None structures
    # However we can just test the structure of the empty endpoints or run the autonomous_cycle using the client.
    # We will trigger the cycle via the API!
    
    success = True
    errors = []
    
    # ── 1. Admin Login ──
    logger.info("Testing Admin Login...")
    resp = client.post("/api/gov/login", json={"username": DEFAULT_ADMIN_USER, "password": DEFAULT_ADMIN_PASS})
    if resp.status_code != 200:
        logger.error(f"Login failed: {resp.text}")
        errors.append(f"Login failed: {resp.status_code} {resp.text}")
        with open("api_test_results.json", "w") as f:
            json.dump({"overall_success": False, "errors": errors}, f)
        return False
        
    token = resp.json().get("access_token")
    headers = {"Authorization": f"Bearer {token}"}
    logger.info("Admin Login: PASS")
    
    # Trigger a cycle so data exists
    logger.info("Triggering autonomous cycle to populate datastore...")
    cycle_resp = client.post("/api/trigger-cycle", headers=headers)
    
    # ── 2. Public Endpoints ──
    logger.info("Testing Public Endpoints...")
    # Zones Risk
    resp = client.get("/api/public/zones/risk")
    if resp.status_code == 200:
        data = resp.json()
        if not data:
            logger.warning("Zones risk data is empty")
        else:
            # Check structure of the first zone
            z_data = list(data.values())[0]
            required_keys = {"composite_score", "air_score", "heat_score", "smoke_score", "flood_score"}
            if not required_keys.issubset(set(z_data.keys())):
                logger.error(f"Missing keys in zone risk payload. Found: {z_data.keys()}")
                errors.append(f"Missing keys in /zones/risk. Found: {z_data.keys()}")
                success = False
        logger.info("Public /zones/risk: PASS")
    else:
        logger.error(f"Public /zones/risk failed: {resp.status_code}")
        errors.append(f"Public /zones/risk failed: {resp.status_code} {resp.text}")
        success = False
        
    # Additional public endpoints
    for route in ["/api/public/status", "/api/public/trends", "/api/public/advisory"]:
        r = client.get(route)
        if r.status_code == 200:
            logger.info(f"Public {route}: PASS")
        else:
            logger.error(f"Public {route} failed: {r.status_code}")
            errors.append(f"Public {route} failed: {r.status_code} {r.text}")
            success = False

    # ── 3. Admin Endpoints ──
    logger.info("Testing Admin Endpoints...")
    
    # Dashboard
    resp = client.get("/api/gov/dashboard", headers=headers)
    if resp.status_code == 200:
        logger.info("Admin Dashboard: PASS")
    else:
        logger.error(f"Admin Dashboard failed: {resp.status_code}")
        errors.append(f"Admin Dashboard failed: {resp.status_code} {resp.text}")
        success = False
        
    # Simulate Intervention
    logger.info("Testing /api/gov/simulate...")
    resp = client.post(
        "/api/gov/simulate", 
        json={"zone_id": 1, "interventions": ["cooling_centers", "mask_distribution"]},
        headers=headers
    )
    if resp.status_code == 200:
        data = resp.json()
        if "projected_risk" in data and "risk_reduction_percentage" in data:
            logger.info("Intervention Simulation: PASS (Contains projected_risk)")
        else:
            logger.error(f"Intervention Simulation payload invalid: {data}")
            errors.append(f"Simulate payload invalid: {data}")
            success = False
    else:
        logger.error(f"Intervention Simulation failed: {resp.status_code}")
        errors.append(f"Simulate failed: {resp.status_code} {resp.text}")
        success = False
        
    # Optimize Resources
    logger.info("Testing /api/gov/optimize-resources...")
    resp = client.post(
        "/api/gov/optimize-resources",
        json={"total_budget": 500000},
        headers=headers
    )
    if resp.status_code == 200:
        data = resp.json()
        if "allocation_matrix" in data and "status" in data:
            logger.info("Resource Optimization: PASS (Contains allocation_matrix)")
        else:
            logger.error(f"Resource Optimization payload invalid: {data}")
            errors.append(f"Optimize payload invalid: {data}")
            success = False
    else:
        logger.error(f"Resource Optimization failed: {resp.status_code} - {resp.text}")
        errors.append(f"Optimize failed: {resp.status_code} {resp.text}")
        success = False
        
    # ── Report Generation ──
    print("="*40)
    print("AEGIS API VALIDATION REPORT")
    print("="*40)
    print(f"Overall Status: {'PASS' if success else 'FAIL'}")
    
    with open("api_test_results.json", "w") as f:
        json.dump({"overall_success": success, "errors": errors}, f)
    
    return success

if __name__ == "__main__":
    if run_api_tests():
        sys.exit(0)
    else:
        sys.exit(1)
