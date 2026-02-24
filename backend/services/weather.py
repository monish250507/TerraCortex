"""
AEGIS WeatherService — Fetches temperature + humidity from OpenWeather API.
Computes Heat Index using standard Rothfusz regression.
"""
import logging
import asyncio
import math
import random
from typing import Optional
from datetime import datetime, timezone
import httpx

from config import (
    OPENWEATHER_API_KEY, CITY_LAT, CITY_LON, CITY_NAME,
    API_TIMEOUT_SECONDS, API_MAX_RETRIES,
)

logger = logging.getLogger("aegis.services.weather")

# Last known value cache
_last_known_weather: Optional[dict] = None
_last_known_used: bool = False


def compute_heat_index(temp_c: float, humidity: float) -> float:
    """
    Compute Heat Index using Rothfusz regression.
    Input: temperature in Celsius, relative humidity %.
    Output: Heat Index in Celsius.
    """
    T = temp_c * 9.0 / 5.0 + 32.0
    RH = humidity

    HI = 0.5 * (T + 61.0 + ((T - 68.0) * 1.2) + (RH * 0.094))

    if HI >= 80:
        HI = (
            -42.379
            + 2.04901523 * T
            + 10.14333127 * RH
            - 0.22475541 * T * RH
            - 0.00683783 * T * T
            - 0.05481717 * RH * RH
            + 0.00122874 * T * T * RH
            + 0.00085282 * T * RH * RH
            - 0.00000199 * T * T * RH * RH
        )
        if RH < 13 and 80 < T < 112:
            HI -= ((13 - RH) / 4) * math.sqrt((17 - abs(T - 95)) / 17)
        elif RH > 85 and 80 < T < 87:
            HI += ((RH - 85) / 10) * ((87 - T) / 5)

    return round((HI - 32.0) * 5.0 / 9.0, 2)


class WeatherService:
    """Fetches weather data from OpenWeather API with retry logic."""

    @staticmethod
    async def fetch_weather(city: str = CITY_NAME) -> dict:
        """
        Fetch temperature + humidity from OpenWeather API.

        Returns:
            {"temperature": float, "humidity": float, "heat_index": float, "source": str}
        """
        global _last_known_weather, _last_known_used

        if not OPENWEATHER_API_KEY:
            logger.warning("OPENWEATHER_API_KEY not set — cannot fetch real data")
            return _fallback_weather("no_key")

        for attempt in range(1, API_MAX_RETRIES + 1):
            try:
                async with httpx.AsyncClient(timeout=API_TIMEOUT_SECONDS) as client:
                    resp = await client.get(
                        "https://api.openweathermap.org/data/2.5/weather",
                        params={
                            "lat": CITY_LAT,
                            "lon": CITY_LON,
                            "appid": OPENWEATHER_API_KEY,
                            "units": "metric",
                        },
                    )

                    if resp.status_code == 200:
                        data = resp.json()
                        temp = float(data["main"]["temp"])
                        hum = float(data["main"]["humidity"])
                        hi = compute_heat_index(temp, hum)

                        result = {
                            "temperature": temp,
                            "humidity": hum,
                            "heat_index": hi,
                            "source": "openweather",
                        }
                        _last_known_weather = result.copy()
                        _last_known_used = False

                        logger.info(
                            "OpenWeather fetched: %.1f°C, %d%% RH, HI=%.1f°C (attempt %d)",
                            temp, hum, hi, attempt,
                        )
                        return result
                    else:
                        logger.warning(
                            "OpenWeather returned status %d on attempt %d",
                            resp.status_code, attempt,
                        )

            except httpx.TimeoutException:
                logger.warning("OpenWeather timeout on attempt %d/%d", attempt, API_MAX_RETRIES)
            except Exception as e:
                logger.error("OpenWeather error on attempt %d/%d: %s", attempt, API_MAX_RETRIES, str(e))

            if attempt < API_MAX_RETRIES:
                await asyncio.sleep(1.5 * attempt)

        # Retries exhausted — use last known value (max 1 cycle)
        if _last_known_weather is not None and not _last_known_used:
            _last_known_used = True
            logger.warning("OpenWeather failed — using last known weather data")
            cached = _last_known_weather.copy()
            cached["source"] = "cache"
            return cached

        return _fallback_weather("failed")

    @staticmethod
    async def health_check() -> str:
        """Check OpenWeather API connectivity."""
        if not OPENWEATHER_API_KEY:
            return "no_key"
        try:
            async with httpx.AsyncClient(timeout=5) as client:
                resp = await client.get(
                    "https://api.openweathermap.org/data/2.5/weather",
                    params={
                        "lat": CITY_LAT,
                        "lon": CITY_LON,
                        "appid": OPENWEATHER_API_KEY,
                        "units": "metric",
                    },
                )
                return "connected" if resp.status_code == 200 else f"error_{resp.status_code}"
        except Exception:
            return "unreachable"


def _fallback_weather(reason: str) -> dict:
    """Generate simulated weather data for Chennai."""
    hour = datetime.now().hour
    base_temp = 30 + 5 * math.sin((hour - 14) * math.pi / 12)
    temp = base_temp + random.gauss(0, 2)
    hum = max(30, min(100, 65 + random.gauss(0, 10)))
    hi = compute_heat_index(temp, hum)
    logger.info("Using simulated weather (reason: %s): %.1f°C, %.0f%% RH", reason, temp, hum)
    return {
        "temperature": round(temp, 2),
        "humidity": round(hum, 2),
        "heat_index": hi,
        "source": "simulated",
    }
