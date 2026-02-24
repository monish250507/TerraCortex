"""
AEGIS Explainer — Delegates to ExplanationService for Claude / template explanations.
"""
from services.explanation import ExplanationService


async def generate_intelligence_summary(risk_data: dict) -> str:
    """Generate government-tone intelligence summary."""
    return await ExplanationService.generate_explanation(risk_data, tone="government")


async def generate_public_advisory(risk_data: dict) -> str:
    """Generate calm public advisory."""
    return await ExplanationService.generate_explanation(risk_data, tone="public")
