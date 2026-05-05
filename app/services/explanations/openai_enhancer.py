"""
SquadMind – OpenAI Enhancement Layer
Takes rule-based ExplanationResult and enriches it with GPT.
Architecture: rule-based runs first (always fast, zero cost), then
this layer optionally enriches if API key exists and context warrants it.

Design: graceful degradation — if OpenAI is unavailable, the rule-based
explanation is returned as-is. Frontend never knows the difference.
"""

from __future__ import annotations

import json
from typing import Any, Dict, Optional

from app.core.config import settings
from app.core.logging import get_logger
from app.services.explanations.templates import ExplanationResult

log = get_logger(__name__)


# ── System prompts per explanation type ───────────────────────────────────────
SYSTEM_PROMPTS: Dict[str, str] = {
    "fraud": """You are SquadMind's AI CFO advisor for Nigerian SMEs.
Your role: explain fraud alerts clearly to business owners who are NOT finance experts.
Voice: warm, direct, slightly urgent when needed. Like a trusted CFO friend on WhatsApp.
Rules:
- Start with the most important fact (the risk)
- Use Nigerian business context (mention naira, typical Nigerian payment patterns)
- Never use jargon without explanation
- End with ONE clear action the owner should take NOW
- Keep it under 80 words for the summary version
- Include a Pidgin version that sounds natural, not translated
""",
    "revenue": """You are SquadMind's AI CFO advisor for Nigerian SMEs.
Your role: explain revenue changes in plain English to small business owners.
Voice: like a smart friend who understands both finance and the Nigerian market.
Rules:
- Lead with the number, then explain why
- Reference real Nigerian business context (public holidays, salary dates, seasonal patterns)
- Be specific — say "₦320K gap" not "significant shortfall"
- One action recommendation, concrete and achievable
- Keep summary under 80 words
- Include natural Pidgin version
""",
    "health_score": """You are SquadMind's AI CFO advisor for Nigerian SMEs.
Your role: explain a business health score like a doctor explains a test result.
Voice: reassuring but honest. Like a doctor who gives you the full picture without panic.
Rules:
- Grade in context (what does 78/100 actually mean for a Nigerian SME?)
- Identify the ONE thing that would move the score most
- Be encouraging even when the score is bad — there's always a path forward
- Concrete improvement steps, not vague advice
- Under 80 words for summary, natural Pidgin version
""",
    "forecast": """You are SquadMind's AI CFO advisor for Nigerian SMEs.
Your role: explain cash flow forecasts so owners can make real decisions.
Voice: practical and clear. Like a financial advisor who knows Nigerian market conditions.
Rules:
- Lead with what the forecast means for their DECISIONS, not just numbers
- Call out risks specific to Nigerian business (FX, power costs, seasonal patterns)
- Confidence score context — what should they trust?
- One specific action to protect the projected income
- Under 80 words for summary, natural Pidgin version
""",
    "customer_behavior": """You are SquadMind's AI CFO advisor for Nigerian SMEs.
Your role: explain customer analytics in a way that drives action.
Voice: like a wise business mentor who understands Nigerian customer behaviour.
Rules:
- Focus on what the data MEANS for their business health
- Call out concentration risk if it exists
- Nigerian customer context: WhatsApp communication, loyalty patterns, referral culture
- One action that would have the biggest revenue impact
- Under 80 words for summary, natural Pidgin version
""",
}


async def enhance_explanation(
    base_explanation: ExplanationResult,
    additional_context: Optional[Dict[str, Any]] = None,
    force_enhance: bool = False,
) -> ExplanationResult:
    """
    Optionally enhance a rule-based explanation with OpenAI GPT.

    When to call:
    - Critical severity alerts (always worth the API cost)
    - When force_enhance=True (demo mode or explicit request)
    - When the explanation type warrants richer narrative

    Falls back to base_explanation on any error.
    """
    if not settings.OPENAI_API_KEY:
        log.debug("openai_not_configured_skipping_enhancement")
        return base_explanation

    # Only enhance for high-severity or forced
    if not force_enhance and base_explanation.severity not in ("critical", "high"):
        return base_explanation

    try:
        enhanced = await _call_openai(base_explanation, additional_context)
        return enhanced
    except Exception as e:
        log.warning(
            "openai_enhancement_failed_using_rule_based",
            error=str(e),
            explanation_type=base_explanation.explanation_type,
        )
        return base_explanation  # Graceful degradation


async def _call_openai(
    explanation: ExplanationResult,
    context: Optional[Dict] = None,
) -> ExplanationResult:
    """Make the OpenAI API call and enrich the explanation."""
    import openai

    client = openai.AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
    system_prompt = SYSTEM_PROMPTS.get(explanation.explanation_type, SYSTEM_PROMPTS["revenue"])

    # Build the user prompt from the rule-based explanation
    user_prompt = f"""Here is a rule-based financial explanation for a Nigerian SME owner.
Your job: rewrite the summary and pidgin_summary to sound more natural and human, while keeping all the numbers accurate.

EXISTING SUMMARY:
{explanation.summary}

EXISTING PIDGIN:
{explanation.pidgin_summary}

KEY FACTS:
{json.dumps(explanation.metrics_referenced, indent=2, default=str)}

ADDITIONAL CONTEXT:
{json.dumps(context or {}, indent=2, default=str)}

Return ONLY a JSON object with these keys:
{{
  "summary": "improved English summary (max 80 words)",
  "pidgin_summary": "improved Pidgin summary (max 80 words, natural Nigerian Pidgin)",
  "headline": "improved headline (max 12 words, punchy)",
  "key_insight": "one sentence — the most important thing the owner should know"
}}
Do not include any other text. Return only the JSON."""

    response = await client.chat.completions.create(
        model=settings.OPENAI_MODEL,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        max_tokens=500,
        temperature=0.7,
        response_format={"type": "json_object"},
    )

    raw_json = response.choices[0].message.content
    enriched = json.loads(raw_json)

    # Merge AI improvements into the base explanation
    explanation.summary = enriched.get("summary", explanation.summary)
    explanation.pidgin_summary = enriched.get("pidgin_summary", explanation.pidgin_summary)
    explanation.headline = enriched.get("headline", explanation.headline)
    explanation.ai_enhanced = True
    explanation.model_used = settings.OPENAI_MODEL

    # Prepend AI key insight to detail if provided
    if key_insight := enriched.get("key_insight"):
        explanation.detail = f"💡 {key_insight}\n\n{explanation.detail}"

    log.info(
        "explanation_enhanced_by_openai",
        explanation_type=explanation.explanation_type,
        model=settings.OPENAI_MODEL,
    )

    return explanation


# ── Bulk narrative generation (for weekly summaries) ─────────────────────────
async def generate_weekly_summary_narrative(
    business_name: str,
    revenue: float,
    revenue_change_pct: float,
    top_transactions: int,
    fraud_flags: int,
    health_score: int,
    language: str = "english",  # "english" | "pidgin"
) -> str:
    """
    Generate a rich weekly summary narrative for WhatsApp/email alerts.
    Used by the alert service for Monday morning summaries.
    """
    if not settings.OPENAI_API_KEY:
        return _fallback_weekly_summary(
            business_name, revenue, revenue_change_pct, fraud_flags, health_score, language
        )

    try:
        import openai
        from app.utils.formatters import format_naira

        client = openai.AsyncOpenAI(api_key=settings.OPENAI_API_KEY)

        direction = "up" if revenue_change_pct >= 0 else "down"
        lang_instruction = "Write in natural Nigerian Pidgin English." if language == "pidgin" else "Write in clear, warm, plain English."

        prompt = f"""Write a short (3–4 sentence) weekly business summary for {business_name}.
{lang_instruction}
Tone: like a smart CFO friend sending a WhatsApp message on Monday morning.

Facts:
- Revenue this week: ₦{revenue:,.0f} ({direction} {abs(revenue_change_pct):.1f}%)
- Transactions: {top_transactions:,}
- Fraud flags: {fraud_flags}
- Health score: {health_score}/100

Include: one concrete suggestion for the week ahead. Keep it under 60 words."""

        response = await client.chat.completions.create(
            model=settings.OPENAI_MODEL,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=150,
            temperature=0.8,
        )
        return response.choices[0].message.content.strip()

    except Exception as e:
        log.warning("weekly_summary_openai_failed", error=str(e))
        return _fallback_weekly_summary(
            business_name, revenue, revenue_change_pct, fraud_flags, health_score, language
        )


def _fallback_weekly_summary(
    business_name: str,
    revenue: float,
    change_pct: float,
    fraud_flags: int,
    health_score: int,
    language: str,
) -> str:
    """Rule-based fallback when OpenAI is unavailable."""
    from app.services.explanations.templates import format_naira_friendly, trend_verb

    direction = trend_verb(change_pct)
    rev_str = format_naira_friendly(revenue)

    if language == "pidgin":
        fraud_note = f" Watch am — {fraud_flags} fraud flag{'s' if fraud_flags > 1 else ''} dey open." if fraud_flags > 0 else ""
        return (
            f"Good morning! {business_name} make {rev_str} this week — revenue {direction} by {abs(change_pct):.1f}%.{fraud_note} "
            f"Health score na {health_score}/100. "
            f"{'Make you focus on getting more customers this week! 💪' if change_pct < 0 else 'Good performance — keep am up! 🚀'}"
        )
    else:
        fraud_note = f" Note: {fraud_flags} fraud flag{'s' if fraud_flags > 1 else ''} require{'s' if fraud_flags == 1 else ''} your attention." if fraud_flags > 0 else ""
        return (
            f"Good morning! {business_name} generated {rev_str} this week — revenue {direction} by {abs(change_pct):.1f}%.{fraud_note} "
            f"Your financial health score is {health_score}/100. "
            f"{'Focus on re-engaging inactive customers this week.' if change_pct < 0 else 'Strong performance — keep the momentum going!'}"
        )
