"""
AEGIS ExplanationService — Generates intelligence summaries via OpenRouter / Claude 3.5 Sonnet.
Only called when risk >= moderate OR anomaly detected. Template fallback on failure.
"""
import logging
import asyncio
import time
from typing import Optional
import httpx

from config import (
    OPENROUTER_API_KEY, OPENROUTER_MODEL, OPENROUTER_ENDPOINT,
    API_TIMEOUT_SECONDS, API_MAX_RETRIES,
    SEVERITY_NORMAL_MAX,
)

logger = logging.getLogger("aegis.services.explanation")

# Rate limiting — minimum seconds between OpenRouter calls
_RATE_LIMIT_SECONDS = 10
_last_call_time: float = 0


class ExplanationService:
    """Generates intelligence summaries via OpenRouter + Claude 3.5 Sonnet."""

    @staticmethod
    async def generate_explanation(risk_data: dict, tone: str = "government") -> str:
        """
        Generate an intelligence explanation for risk data.

        Only calls Claude when:
        - Risk level >= moderate (composite_score >= 40), OR
        - Anomaly detected

        Args:
            risk_data: dict with air_score, heat_score, composite_score, pm25, heat_index, etc.
            tone: "government" for technical, "public" for calm advisory

        Returns:
            str: explanation text
        """
        composite = risk_data.get("composite_score", 0)
        anomaly_flags = risk_data.get("anomaly_flags", [])

        # Only call Claude for moderate+ risk or anomaly
        if composite < SEVERITY_NORMAL_MAX and not anomaly_flags:
            logger.info("Risk below threshold (%.1f) — using template", composite)
            return _template_explanation(risk_data, tone)

        # Try OpenRouter / Claude
        if not OPENROUTER_API_KEY:
            logger.info("OPENROUTER_API_KEY not set — using template")
            return _template_explanation(risk_data, tone)

        # Rate limiting
        global _last_call_time
        elapsed = time.time() - _last_call_time
        if elapsed < _RATE_LIMIT_SECONDS:
            wait = _RATE_LIMIT_SECONDS - elapsed
            logger.debug("Rate limiting — waiting %.1fs", wait)
            await asyncio.sleep(wait)

        prompt = _build_prompt(risk_data, tone)

        for attempt in range(1, API_MAX_RETRIES + 1):
            try:
                async with httpx.AsyncClient(timeout=API_TIMEOUT_SECONDS + 15) as client:
                    resp = await client.post(
                        OPENROUTER_ENDPOINT,
                        headers={
                            "Authorization": f"Bearer {OPENROUTER_API_KEY}",
                            "Content-Type": "application/json",
                        },
                        json={
                            "model": OPENROUTER_MODEL,
                            "messages": [
                                {
                                    "role": "system",
                                    "content": _system_prompt(tone),
                                },
                                {
                                    "role": "user",
                                    "content": prompt,
                                },
                            ],
                            "max_tokens": 400,
                            "temperature": 0.3,
                        },
                    )

                    _last_call_time = time.time()

                    if resp.status_code == 200:
                        data = resp.json()
                        choices = data.get("choices", [])
                        if choices:
                            content = choices[0].get("message", {}).get("content", "")
                            if content and len(content) > 20:
                                logger.info("Claude explanation generated (attempt %d, %d chars)", attempt, len(content))
                                return content.strip()

                        logger.warning("OpenRouter returned empty/invalid response")
                    else:
                        logger.warning(
                            "OpenRouter returned status %d on attempt %d",
                            resp.status_code, attempt,
                        )

            except httpx.TimeoutException:
                logger.warning("OpenRouter timeout on attempt %d/%d", attempt, API_MAX_RETRIES)
            except Exception as e:
                logger.error("OpenRouter error on attempt %d/%d: %s", attempt, API_MAX_RETRIES, str(e))

            if attempt < API_MAX_RETRIES:
                await asyncio.sleep(2 * attempt)

        # All retries exhausted — fallback
        logger.warning("OpenRouter failed after %d attempts — using template fallback", API_MAX_RETRIES)
        return _template_explanation(risk_data, tone)

    @staticmethod
    async def health_check() -> str:
        """Check OpenRouter API connectivity."""
        if not OPENROUTER_API_KEY:
            return "no_key"
        try:
            async with httpx.AsyncClient(timeout=5) as client:
                resp = await client.get(
                    "https://openrouter.ai/api/v1/models",
                    headers={"Authorization": f"Bearer {OPENROUTER_API_KEY}"},
                )
                return "connected" if resp.status_code == 200 else f"error_{resp.status_code}"
        except Exception:
            return "unreachable"


def _system_prompt(tone: str) -> str:
    if tone == "public":
        return (
            "You are an environmental health advisory writer for a government-operated "
            "public information system in Chennai, India. Write calm, measured, and "
            "directive advisories. No dramatic language. No panic-inducing statements. "
            "Be concise — 2-3 sentences maximum."
        )
    return (
        "You are an environmental intelligence analyst for AEGIS, an autonomous "
        "environmental monitoring system operated by the Government of Chennai, India. "
        "Write precise, technical intelligence assessments. Use evidence-based language. "
        "Reference specific metrics and thresholds. Be concise but comprehensive."
    )


def _build_prompt(risk_data: dict, tone: str) -> str:
    air = risk_data.get("air_score", 0)
    heat = risk_data.get("heat_score", 0)
    comp = risk_data.get("composite_score", 0)
    pm25 = risk_data.get("pm25", 0)
    hi = risk_data.get("heat_index", 0)
    amp = risk_data.get("amplification_factor", 1.0)
    anomalies = risk_data.get("anomaly_flags", [])

    base = (
        f"Current environmental assessment for Chennai:\n"
        f"- PM2.5: {pm25:.1f} µg/m³\n"
        f"- Heat Index: {hi:.1f}°C\n"
        f"- Air Risk Score: {air:.1f}/100\n"
        f"- Heat Risk Score: {heat:.1f}/100\n"
        f"- Composite Risk Score: {comp:.1f}/100\n"
        f"- Amplification Factor: {amp:.3f}\n"
    )

    if anomalies:
        base += f"- Active Anomaly Flags: {', '.join(anomalies)}\n"

    if tone == "public":
        base += "\nGenerate a calm public health advisory (2-3 sentences)."
    else:
        base += "\nGenerate a technical intelligence summary (3-5 sentences)."

    return base


def _template_explanation(risk_data: dict, tone: str) -> str:
    """Template-based fallback explanation."""
    air = risk_data.get("air_score", 0)
    heat = risk_data.get("heat_score", 0)
    comp = risk_data.get("composite_score", 0)
    pm25 = risk_data.get("pm25", 0)
    hi = risk_data.get("heat_index", 0)
    amp = risk_data.get("amplification_factor", 1.0)

    def level(s):
        return "LOW" if s < 40 else "MODERATE" if s < 70 else "HIGH"

    if tone == "public":
        if comp >= 70:
            if heat > air:
                return (
                    "High heat conditions are currently affecting Chennai. "
                    "Avoid prolonged outdoor exposure, especially between 11 AM and 4 PM. "
                    "Stay hydrated and seek air-conditioned spaces where possible."
                )
            return (
                "Air quality in Chennai is currently poor. "
                "Reduce outdoor physical activity and use respiratory protection if outdoors. "
                "Keep windows closed and use air purifiers if available."
            )
        elif comp >= 40:
            return (
                "Environmental conditions in Chennai require moderate caution. "
                "Sensitive groups should limit prolonged outdoor exposure. "
                "Stay informed of updates from local health authorities."
            )
        return (
            "Environmental conditions in Chennai are within normal parameters. "
            "No special precautions are required at this time."
        )

    # Government tone
    summary = (
        f"AEGIS Intelligence Assessment — "
        f"Air pollution risk is classified {level(air)} at {air:.1f}/100 "
        f"with PM2.5 readings at {pm25:.1f} µg/m³. "
        f"Heat stress risk is {level(heat)} at {heat:.1f}/100 "
        f"with a Heat Index of {hi:.1f}°C. "
        f"Composite environmental risk stands at {comp:.1f}/100 ({level(comp)})"
    )
    if amp and amp > 1.05:
        summary += (
            f", reflecting synergistic amplification (factor: {amp:.3f}) "
            f"due to concurrent elevation in both risk domains"
        )
    anomalies = risk_data.get("anomaly_flags", [])
    if anomalies:
        summary += f". Active anomaly flags: {', '.join(anomalies[:3])}"
    summary += "."
    return summary
