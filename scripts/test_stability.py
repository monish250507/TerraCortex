"""
AEGIS Stability Test Suite
Simulates 5 consecutive iterations of the autonomous cycle, monitoring memory
and timing to detect leaks or overlapping job conditions.
"""
import sys
import os
import time
import logging
import asyncio
import tracemalloc
import psutil
from unittest import mock

backend_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'backend'))
sys.path.append(backend_path)

from main import autonomous_cycle
from database import SessionLocal, init_db, engine
from scripts.seed_zones import seed_zones
from models import Base, ZoneObservation, RiskAssessment

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger("aegis.tests.stability")

async def run_cycles(num_cycles=5):
    # Setup test environment
    logger.info("Initializing Stability Test Database...")
    Base.metadata.drop_all(bind=engine)
    init_db()
    seed_zones()
    
    db = SessionLocal()
    
    report = {
        "cycles": [],
        "total_errors": 0,
        "memory_trend_mb": [],
        "total_records_inserted": 0
    }
    
    process = psutil.Process(os.getpid())
    tracemalloc.start()
    
    # We will simulate the system over 5 cycles, including 1 failure cycle
    for i in range(1, num_cycles + 1):
        logger.info(f"=== Starting Cycle {i}/{num_cycles} ===")
        start_time = time.time()
        
        cycle_errors = 0
        inserted_this_cycle = 0
        
        # Get DB counts before
        obs_before = db.query(ZoneObservation).count()
        risk_before = db.query(RiskAssessment).count()
        
        try:
            # Simulate a failure on cycle 3 to ensure resilient handling
            if i == 3:
                with mock.patch('services.air_quality.AirQualityService.fetch_pm25', side_effect=Exception("Simulated API Drop")):
                    await autonomous_cycle()
            else:
                 await autonomous_cycle()
        except Exception as e:
            logger.error(f"Cycle {i} crashed: {e}")
            cycle_errors += 1
            report["total_errors"] += 1
            
        exec_time = time.time() - start_time
        
        # Get DB counts after
        obs_after = db.query(ZoneObservation).count()
        risk_after = db.query(RiskAssessment).count()
        
        inserted_this_cycle = (obs_after - obs_before) + (risk_after - risk_before)
        report["total_records_inserted"] += inserted_this_cycle
        
        # Measure Memory
        current, peak = tracemalloc.get_traced_memory()
        mem_mb = process.memory_info().rss / (1024 * 1024)
        report["memory_trend_mb"].append(round(mem_mb, 2))
        
        cycle_data = {
            "cycle_number": i,
            "duration": round(exec_time, 2),
            "errors": cycle_errors,
            "data_inserted": inserted_this_cycle,
            "memory_usage_mb": round(mem_mb, 2)
        }
        report["cycles"].append(cycle_data)
        
        logger.info(f"Cycle {i} complete: {exec_time:.2f}s | Inserted: {inserted_this_cycle} | Mem: {mem_mb:.2f}MB")
        
        # Artificial delay to ensure no overlap and allow GC
        await asyncio.sleep(0.5)
        
    tracemalloc.stop()
    db.close()
    
    # Output Health Report
    print("="*50)
    print("AEGIS STABILITY TEST HEALTH REPORT")
    print("="*50)
    
    for c in report["cycles"]:
        print(f"Cycle {c['cycle_number']}: Duration: {c['duration']}s | Errors: {c['errors']} | "
              f"Data Inserted: {c['data_inserted']} | Memory: {c['memory_usage_mb']}MB")
              
    print("-" * 50)
    print(f"Total Records Inserted: {report['total_records_inserted']}")
    print(f"Total Unhandled Crashes: {report['total_errors']}")
    
    memory_drift = report['memory_trend_mb'][-1] - report['memory_trend_mb'][0]
    print(f"Memory Drift: {memory_drift:.2f}MB (Stable if near zero)")
    
    if report["total_errors"] == 0 and memory_drift < 20:
        print("STABILITY RATING: PASS")
        return True
    else:
        print("STABILITY RATING: FAIL")
        return False

if __name__ == "__main__":
    success = asyncio.run(run_cycles())
    if success:
        sys.exit(0)
    else:
        sys.exit(1)
