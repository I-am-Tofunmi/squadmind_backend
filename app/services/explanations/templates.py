"""
SquadMind – Explanation Templates & Voice System
Defines the CFO tone, phrase banks, Pidgin translations, and
action recommendation patterns used across all explanation types.

Design principle: sound like a smart Nigerian CFO friend, not a bot.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional


# ── CFO Persona Traits ────────────────────────────────────────────────────────
CFO_TRAITS = {
    "tone": "warm, direct, action-oriented",
    "style": "no jargon unless explained, concrete numbers, clear so-what",
    "relationship": "trusted advisor, not a report generator",
    "cultural_context": "understands Nigerian market — power cuts, public holidays, month-end patterns",
}


# ── Severity → Opener mapping ─────────────────────────────────────────────────
SEVERITY_OPENERS: Dict[str, List[str]] = {
    "critical": [
        "This needs your attention right now.",
        "Stop what you're doing — this is urgent.",
        "Immediate action required.",
    ],
    "high": [
        "This is worth investigating today.",
        "You should look at this before end of day.",
        "Something unusual happened that you need to know about.",
    ],
    "medium": [
        "Here's something worth keeping an eye on.",
        "A pattern emerged that your CFO would flag.",
        "This is not urgent, but it matters.",
    ],
    "low": [
        "A small observation from your data.",
        "FYI — nothing to worry about, just keeping you informed.",
        "Here's a routine insight from your numbers.",
    ],
    "positive": [
        "Great news from your numbers.",
        "Your business is doing something right.",
        "Here's something worth celebrating.",
    ],
}


# ── Trend Language ────────────────────────────────────────────────────────────
def trend_verb(change_pct: float, magnitude: bool = False) -> str:
    """Return a human verb describing the direction and magnitude of change."""
    abs_pct = abs(change_pct)
    if change_pct > 0:
        if abs_pct >= 50:
            return "surged" if not magnitude else "a massive jump"
        elif abs_pct >= 20:
            return "jumped" if not magnitude else "a strong increase"
        elif abs_pct >= 10:
            return "grew" if not magnitude else "a healthy increase"
        else:
            return "ticked up" if not magnitude else "a slight increase"
    else:
        if abs_pct >= 50:
            return "dropped sharply" if not magnitude else "a steep fall"
        elif abs_pct >= 20:
            return "fell" if not magnitude else "a significant drop"
        elif abs_pct >= 10:
            return "declined" if not magnitude else "a noticeable decline"
        else:
            return "dipped slightly" if not magnitude else "a small dip"


def format_naira_friendly(amount: float) -> str:
    """Human-friendly Naira amounts — ₦4.2M reads better than ₦4,200,000."""
    if amount >= 1_000_000_000:
        return f"₦{amount / 1_000_000_000:.1f}B"
    elif amount >= 1_000_000:
        return f"₦{amount / 1_000_000:.1f}M"
    elif amount >= 1_000:
        return f"₦{amount / 1_000:.0f}K"
    else:
        return f"₦{amount:,.0f}"


def format_change(change_pct: float) -> str:
    """'up 12%' or 'down 8%' — clean and scannable."""
    direction = "up" if change_pct >= 0 else "down"
    return f"{direction} {abs(change_pct):.1f}%"


# ── Action Recommendation Patterns ────────────────────────────────────────────
@dataclass
class ActionRecommendation:
    priority: str        # immediate | today | this_week | monitor
    action: str          # what to do
    expected_outcome: str  # why it matters
    effort: str          # quick | moderate | significant


# ── Pidgin Translation Helpers ────────────────────────────────────────────────
PIDGIN_PHRASES = {
    # Revenue
    "revenue_up": "Your money don increase",
    "revenue_down": "Your revenue don drop",
    "revenue_flat": "Revenue dey maintain",
    "no_data": "No data dey for now",

    # Urgency
    "act_now": "You need to act fast o",
    "check_this": "Abeg check this one",
    "no_worry": "No worry, e normal",
    "good_job": "You don do am! E don do!",

    # Business health
    "business_good": "Your business dey fine",
    "business_bad": "Business need help",
    "business_okay": "E dey manage",

    # Customers
    "customer_good": "Your customers dey loyal",
    "customer_gone": "Some customers don disappear",
    "new_customers": "New customers dey come",

    # Fraud
    "fraud_warning": "Suspicious activity o!",
    "fraud_clear": "E clear — no fraud",
    "fraud_verify": "Abeg verify this transaction",

    # Actions
    "call_customer": "Call the customer",
    "check_records": "Check your records",
    "monitor": "Keep eye on am",
}

PIDGIN_CLOSERS = {
    "positive": [
        "E don do! Keep the momentum going! 🚀",
        "You dey do well — carry go! 💪",
        "Your hustle dey pay — no stop! 🔥",
    ],
    "neutral": [
        "Na your business — you get this! 💼",
        "Use this information wisely, abeg.",
        "Monitor am and act if e change.",
    ],
    "negative": [
        "Abeg act fast — e important o! ⚠️",
        "No dey sleep on this one — tackle am today.",
        "Your business need your attention right now.",
    ],
    "fraud": [
        "Protect your business — verify before e too late! 🚨",
        "No let fraudsters chop your money! Investigate now.",
        "Your money important — check this transaction! 🔒",
    ],
}


def pick_opener(severity: str, index: int = 0) -> str:
    options = SEVERITY_OPENERS.get(severity, SEVERITY_OPENERS["medium"])
    return options[index % len(options)]


def pick_pidgin_closer(tone: str, index: int = 0) -> str:
    options = PIDGIN_CLOSERS.get(tone, PIDGIN_CLOSERS["neutral"])
    return options[index % len(options)]


# ── Explanation Output Container ──────────────────────────────────────────────
@dataclass
class ExplanationResult:
    """
    Standardised output from any explanation generator.
    Frontend receives this directly — all fields are safe strings.
    """
    # Core content
    headline: str                          # One punchy sentence for the card header
    summary: str                           # 2–3 sentence plain-English explanation
    detail: str                            # Full paragraph with context and numbers
    pidgin_summary: str                    # Pidgin version of summary
    pidgin_detail: str                     # Pidgin version of detail

    # Structured metadata
    severity: str                          # critical | high | medium | low | positive
    explanation_type: str                  # fraud | forecast | health | revenue | customer | alert
    key_factors: List[str]                 # Bullet-point factors that drove this insight
    actions: List[ActionRecommendation]    # What to do next
    metrics_referenced: Dict              # The raw numbers behind the explanation

    # AI enhancement flag
    ai_enhanced: bool = False              # True if OpenAI was used
    model_used: Optional[str] = None       # e.g. "gpt-4o-mini"

    def to_dict(self) -> Dict:
        return {
            "headline": self.headline,
            "summary": self.summary,
            "detail": self.detail,
            "pidgin": {
                "summary": self.pidgin_summary,
                "detail": self.pidgin_detail,
            },
            "severity": self.severity,
            "explanation_type": self.explanation_type,
            "key_factors": self.key_factors,
            "actions": [
                {
                    "priority": a.priority,
                    "action": a.action,
                    "expected_outcome": a.expected_outcome,
                    "effort": a.effort,
                }
                for a in self.actions
            ],
            "metrics_referenced": self.metrics_referenced,
            "ai_enhanced": self.ai_enhanced,
            "model_used": self.model_used,
        }
