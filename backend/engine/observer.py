"""
AEGIS Observer Agent — Fetches PM2.5 and weather data via service classes.
Stores time-series readings. Runs hourly via APScheduler.
"""
import logging
from datetime import datetime, timezone
from sqlalchemy.orm import Session
from models import EnvironmentalReading, IntelligenceFeedEntry
from services.air_quality import AirQualityService
from services.weather import WeatherService
from config import CITY_NAME

logger = logging.getLogger("aegis.observer")


async def run_observation_cycle(db: Session):
    """
    Complete observation cycle:
    1. Fetch PM2.5 via AirQualityService
    2. Fetch weather via WeatherService
    3. Store reading
    4. Log to intelligence feed
    
    Returns: EnvironmentalReading or None
    """
    # Fetch via isolated service classes
    air_data = await AirQualityService.fetch_pm25(CITY_NAME)
    weather_data = await WeatherService.fetch_weather(CITY_NAME)

    pm25_val = air_data["pm25"]
    temperature = weather_data["temperature"]
    humidity = weather_data["humidity"]
    heat_idx = weather_data["heat_index"]
    air_source = air_data["source"]
    weather_source = weather_data["source"]

    reading = EnvironmentalReading(
        pm25=pm25_val,
        temperature=temperature,
        humidity=humidity,
        heat_index=heat_idx,
    )
    db.add(reading)

    # Log to intelligence feed
    source_info = f"[air:{air_source}, weather:{weather_source}]"
    feed_entry = IntelligenceFeedEntry(
        entry_type="observation",
        title="Environmental Observation Recorded",
        content=(
            f"PM2.5: {pm25_val:.1f} µg/m³ | "
            f"Temperature: {temperature:.1f}°C | "
            f"Humidity: {humidity:.0f}% | "
            f"Heat Index: {heat_idx:.1f}°C {source_info}"
        ),
        severity="info",
        metadata_json={
            "pm25": pm25_val,
            "temperature": temperature,
            "humidity": humidity,
            "heat_index": heat_idx,
            "air_source": air_source,
            "weather_source": weather_source,
        },
    )
    db.add(feed_entry)
    db.commit()
    db.refresh(reading)

    logger.info(
        "Observation recorded — PM2.5: %.1f, Temp: %.1f, HI: %.1f %s",
        pm25_val, temperature, heat_idx, source_info,
    )
    return reading
