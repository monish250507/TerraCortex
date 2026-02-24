"""
AEGIS Configuration — Environment variables and system constants.
"""
import os
import logging
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger("aegis.config")

# ── API Keys ──────────────────────────────────────────────
OPENAQ_API_KEY = os.getenv("OPENAQ_API_KEY", "")
OPENWEATHER_API_KEY = os.getenv("OPENWEATHER_API_KEY", "")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")

# ── Database ──────────────────────────────────────────────
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./aegis.db")

# ── JWT Auth ──────────────────────────────────────────────
JWT_SECRET = os.getenv("JWT_SECRET", "aegis-secret-key-change-in-production")
JWT_ALGORITHM = "HS256"
JWT_EXPIRATION_HOURS = 24

# ── Default Admin ─────────────────────────────────────────
DEFAULT_ADMIN_USER = "admin"
DEFAULT_ADMIN_PASS = "aegis_admin_2026"

# ── Observer Config ───────────────────────────────────────
CITY_NAME = "Chennai"
CITY_LAT = 13.0827
CITY_LON = 80.2707
OBSERVATION_INTERVAL_MINUTES = 60

# ── Baseline Config ───────────────────────────────────────
BASELINE_WINDOW_DAYS = 7
PERCENTILE_BANDS = [25, 50, 75, 90, 95]

# ── Risk Thresholds ──────────────────────────────────────
AIR_RISK_THRESHOLD = 60
HEAT_RISK_THRESHOLD = 60
COMPOSITE_RISK_THRESHOLD = 70

# ── Composite Model ──────────────────────────────────────
COMPOSITE_AIR_WEIGHT = 0.45
COMPOSITE_HEAT_WEIGHT = 0.55
AMPLIFICATION_COEFFICIENT = 0.6

# ── Anomaly Detection ────────────────────────────────────
ANOMALY_ZSCORE_THRESHOLD = 2.5
ANOMALY_PERCENTILE_THRESHOLD = 95
ANOMALY_RATE_MULTIPLIER = 2.0

# ── Alert Cooldown ────────────────────────────────────────
ALERT_COOLDOWN_MINUTES = 30

# ── Severity Bands ────────────────────────────────────────
SEVERITY_NORMAL_MAX = 40
SEVERITY_MODERATE_MAX = 70

# ── Simulation Mode ───────────────────────────────────────
USE_SIMULATED_DATA = not (OPENAQ_API_KEY and OPENWEATHER_API_KEY)

# ── API Timeouts ──────────────────────────────────────────
API_TIMEOUT_SECONDS = 10
API_MAX_RETRIES = 3

# ── OpenRouter / Claude Config ────────────────────────────
OPENROUTER_MODEL = "anthropic/claude-3.5-sonnet"
OPENROUTER_ENDPOINT = "https://openrouter.ai/api/v1/chat/completions"


def validate_api_keys():
    """Validate that required API keys are present. Log warnings for missing ones."""
    missing = []
    if not OPENAQ_API_KEY:
        missing.append("OPENAQ_API_KEY")
    if not OPENWEATHER_API_KEY:
        missing.append("OPENWEATHER_API_KEY")
    if not OPENROUTER_API_KEY:
        missing.append("OPENROUTER_API_KEY")

    if missing:
        logger.warning(
            "Missing API keys: %s — system will use fallback/simulation mode",
            ", ".join(missing),
        )
        return False
    logger.info("All API keys loaded successfully")
    return True
