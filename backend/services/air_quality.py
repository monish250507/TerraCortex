"""
AEGIS AirQualityService — Fetches PM2.5 data from OpenAQ API.
Implements retry logic, timeout handling, and error resilience.
"""
import logging
import asyncio
from typing import Optional
from datetime import datetime, timezone
import httpx

from config import OPENAQ_API_KEY, CITY_LAT, CITY_LON, CITY_NAME, API_TIMEOUT_SECONDS, API_MAX_RETRIES

logger = logging.getLogger("aegis.services.air_quality")

# Last known value cache for resilience
_last_known_pm25: Optional[float] = None
_last_known_used: bool = False


class AirQualityService:
    """Fetches PM2.5 data from OpenAQ v3 API with retry logic."""

    @staticmethod
    async def fetch_pm25(city: str = CITY_NAME) -> dict:
        """
        Fetch latest PM2.5 from OpenAQ API.

        Returns:
            {"timestamp": datetime, "city": str, "pm25": float, "source": "openaq"|"cache"|"simulated"}
        """
        global _last_known_pm25, _last_known_used

        if not OPENAQ_API_KEY:
            logger.warning("OPENAQ_API_KEY not set — cannot fetch real data")
            return _fallback_response(city, "no_key")

        for attempt in range(1, API_MAX_RETRIES + 1):
            try:
                async with httpx.AsyncClient(timeout=API_TIMEOUT_SECONDS) as client:
                    # Use bbox around Chennai (lat ±0.2, lon ±0.2)
                    bbox = f"{CITY_LON - 0.2},{CITY_LAT - 0.2},{CITY_LON + 0.2},{CITY_LAT + 0.2}"
                    resp = await client.get(
                        "https://api.openaq.org/v3/locations",
                        params={
                            "bbox": bbox,
                            "parameters_id": 2,  # PM2.5 parameter ID
                            "limit": 5,
                        },
                        headers={"X-API-Key": OPENAQ_API_KEY},
                    )

                    if resp.status_code == 200:
                        data = resp.json()
                        results = data.get("results", [])
                        if results:
                            # Find PM2.5 from first location with data
                            for loc in results:
                                sensors = loc.get("sensors", loc.get("parameters", []))
                                for s in sensors:
                                    param_name = s.get("parameter", {})
                                    if isinstance(param_name, dict):
                                        param_name = param_name.get("name", "")
                                    if "pm25" in str(param_name).lower() or s.get("parameter") == "pm25":
                                        last_val = s.get("lastValue") or s.get("latest", {}).get("value")
                                        if last_val is not None:
                                            pm25_val = float(last_val)
                                            _last_known_pm25 = pm25_val
                                            _last_known_used = False
                                            logger.info(
                                                "OpenAQ PM2.5 fetched: %.1f µg/m³ (attempt %d)",
                                                pm25_val, attempt,
                                            )
                                            return {
                                                "timestamp": datetime.now(timezone.utc),
                                                "city": city,
                                                "pm25": pm25_val,
                                                "source": "openaq",
                                            }

                        logger.warning("OpenAQ returned no PM2.5 results for %s", city)
                    else:
                        logger.warning(
                            "OpenAQ returned status %d on attempt %d: %s",
                            resp.status_code, attempt, resp.text[:200],
                        )

            except httpx.TimeoutException:
                logger.warning("OpenAQ timeout on attempt %d/%d", attempt, API_MAX_RETRIES)
            except Exception as e:
                logger.error("OpenAQ error on attempt %d/%d: %s", attempt, API_MAX_RETRIES, str(e))

            if attempt < API_MAX_RETRIES:
                await asyncio.sleep(1.5 * attempt)  # Backoff

        # All retries exhausted — use last known value (max 1 cycle)
        if _last_known_pm25 is not None and not _last_known_used:
            _last_known_used = True
            logger.warning("OpenAQ failed — using last known PM2.5: %.1f", _last_known_pm25)
            return {
                "timestamp": datetime.now(timezone.utc),
                "city": city,
                "pm25": _last_known_pm25,
                "source": "cache",
            }

        return _fallback_response(city, "failed")

    @staticmethod
    async def health_check() -> str:
        """Check OpenAQ API connectivity."""
        if not OPENAQ_API_KEY:
            return "no_key"
        try:
            async with httpx.AsyncClient(timeout=5) as client:
                resp = await client.get(
                    "https://api.openaq.org/v3/locations",
                    params={"limit": 1},
                    headers={"X-API-Key": OPENAQ_API_KEY},
                )
                return "connected" if resp.status_code == 200 else f"error_{resp.status_code}"
        except Exception:
            return "unreachable"


def _fallback_response(city: str, reason: str) -> dict:
    """Generate a fallback/simulated response."""
    import math, random
    hour = datetime.now().hour
    base_pm25 = 45 + 20 * math.sin((hour - 8) * math.pi / 12)
    pm25 = max(5, base_pm25 + random.gauss(0, 10))
    logger.info("Using simulated PM2.5 (reason: %s): %.1f", reason, pm25)
    return {
        "timestamp": datetime.now(timezone.utc),
        "city": city,
        "pm25": round(pm25, 2),
        "source": "simulated",
    }
