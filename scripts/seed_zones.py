"""
AEGIS Zone Seeder — Injects default zones into the database.
"""
import sys
import os
import logging

# Add backend directory to path so we can import modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database import SessionLocal, init_db
from models import Zone

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("aegis.seeder")

def seed_zones():
    """Seed the database with 5 zones for Chennai."""
    db = SessionLocal()
    try:
        existing_zones = db.query(Zone).count()
        if existing_zones > 0:
            logger.info(f"Database already has {existing_zones} zones. Skipping seed.")
            return

        logger.info("Seeding 5 zones for Chennai...")

        zones_data = [
            {
                "name": "North",
                "population": 1500000,
                "area_km2": 45.5,
                "geojson_boundary": {
                    "type": "Polygon",
                    "coordinates": [[[80.25, 13.15], [80.30, 13.15], [80.30, 13.10], [80.25, 13.10], [80.25, 13.15]]]
                }
            },
            {
                "name": "Central",
                "population": 2200000,
                "area_km2": 60.2,
                "geojson_boundary": {
                    "type": "Polygon",
                    "coordinates": [[[80.20, 13.10], [80.28, 13.10], [80.28, 13.02], [80.20, 13.02], [80.20, 13.10]]]
                }
            },
            {
                "name": "South",
                "population": 3100000,
                "area_km2": 110.8,
                "geojson_boundary": {
                    "type": "Polygon",
                    "coordinates": [[[80.15, 13.02], [80.25, 13.02], [80.25, 12.90], [80.15, 12.90], [80.15, 13.02]]]
                }
            },
            {
                "name": "East",
                "population": 1800000,
                "area_km2": 35.4,
                "geojson_boundary": {
                    "type": "Polygon",
                    "coordinates": [[[80.25, 13.10], [80.30, 13.10], [80.30, 12.95], [80.25, 12.95], [80.25, 13.10]]]
                }
            },
            {
                "name": "West",
                "population": 2500000,
                "area_km2": 174.1,
                "geojson_boundary": {
                    "type": "Polygon",
                    "coordinates": [[[80.05, 13.12], [80.20, 13.12], [80.20, 12.98], [80.05, 12.98], [80.05, 13.12]]]
                }
            }
        ]

        for data in zones_data:
            zone = Zone(**data)
            db.add(zone)

        db.commit()
        logger.info("Successfully seeded 5 zones.")

    except Exception as e:
        logger.error(f"Error seeding zones: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    init_db()  # Ensure tables exist
    seed_zones()
