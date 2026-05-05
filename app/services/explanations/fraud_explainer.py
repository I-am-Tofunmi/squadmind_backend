"""
SquadMind – Fraud Explanation Engine
Converts raw risk scores and triggered rules into CFO-quality narrative.

Rule-based first: every fraud combination has a crafted explanation.
OpenAI layer: enriches the explanation when API key is available.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Dict, List, Optional

from app.services.explanations.templates import (
    ActionRecommendation,
    ExplanationResult,
    format_naira_friendly,
    pick_opener,
    pick_pidgin_closer,
)


# ── Rule Descriptions (human language for each fraud signal) ──────────────────
RULE_DESCRIPTIONS = {
    "large_transaction_amount": {
        "en": lambda amount, threshold: (
            f"the transaction amount ({format_naira_friendly(amount)}) is significantly "
            f"above your typical limit of {format_naira_friendly(threshold)}"
        ),
        "pidgin": lambda amount, threshold: (
            f"the amount ({format_naira_friendly(amount)}) pass your normal limit "
            f"of {format_naira_friendly(threshold)} — e too much"
        ),
    },
    "night_transaction": {
        "en": lambda hour, *_: (
            f"it happened at {_format_hour(hour)}, well outside normal business hours"
        ),
        "pidgin": lambda hour, *_: (
            f"e happen for {_format_hour(hour)} — who dey do business for that time?"
        ),
    },
    "velocity_breach": {
        "en": lambda count, window, *_: (
            f"the same customer attempted {count} transactions within {window} minutes — "
            f"far above the normal frequency"
        ),
        "pidgin": lambda count, window, *_: (
            f"the customer try {count} transactions for just {window} minutes — "
            f"that one no normal at all"
        ),
    },
    "round_number_amount": {
        "en": lambda amount, *_: (
            f"the amount ({format_naira_friendly(amount)}) is a suspiciously round number, "
            f"a common pattern in structured fraud"
        ),
        "pidgin": lambda amount, *_: (
            f"the amount na too round number ({format_naira_friendly(amount)}) — "
            f"fraudsters usually use round numbers"
        ),
    },
    "potential_duplicate": {
        "en": lambda *_: (
            "an identical transaction from the same customer appeared just minutes earlier — "
            "this could be a double-charge or a replay attack"
        ),
        "pidgin": lambda *_: (
            "the same customer don do the same transaction twice for few minutes — "
            "e fit be double charge or fraud replay"
        ),
    },
    "high_value_first_transaction": {
        "en": lambda amount, *_: (
            f"this is the customer's very first transaction with you, and the amount "
            f"({format_naira_friendly(amount)}) is unusually high for a new relationship"
        ),
        "pidgin": lambda amount, *_: (
            f"this na the customer's first time with you, and dem wan pay "
            f"{format_naira_friendly(amount)} immediately — that one suspicious"
        ),
    },
}

RISK_LEVEL_CONTEXT = {
    "critical": {
        "opener": "This transaction has multiple serious red flags that require immediate review.",
        "pidgin_opener": "This transaction get serious problem — you need to check am NOW!",
        "urgency": "Do not process or release funds from this transaction until you have verified it.",
        "pidgin_urgency": "No release any funds o — verify am first before e too late!",
    },
    "high": {
        "opener": "This transaction raised significant concerns across several indicators.",
        "pidgin_opener": "This transaction get plenty warning signs — e need your attention!",
        "urgency": "Review this transaction today before proceeding with any related actions.",
        "pidgin_urgency": "Check this transaction today before you do anything — e important!",
    },
    "medium": {
        "opener": "This transaction has some unusual characteristics that are worth checking.",
        "pidgin_opener": "This transaction get some unusual signs — e worth checking.",
        "urgency": "Keep an eye on this customer and flag any follow-up activity.",
        "pidgin_urgency": "Watch this customer and record any follow-up wey happen.",
    },
    "low": {
        "opener": "This transaction has a minor anomaly, likely routine but logged for your records.",
        "pidgin_opener": "Small small issue with this transaction — no big deal but e recorded.",
        "urgency": "No immediate action needed — just monitor for patterns.",
        "pidgin_urgency": "No need to panic — just keep eye on am.",
    },
}


def _format_hour(hour: int) -> str:
    """Convert 24h hour to readable time with AM/PM."""
    if hour == 0:
        return "12:00 AM (midnight)"
    elif hour < 12:
        return f"{hour}:00 AM"
    elif hour == 12:
        return "12:00 PM (noon)"
    else:
        return f"{hour - 12}:00 PM"


# ── Main Fraud Explainer ───────────────────────────────────────────────────────
def explain_fraud(
    transaction_amount: float,
    risk_score: float,
    risk_level: str,
    rules_triggered: List[str],
    transaction_hour: Optional[int] = None,
    velocity_count: Optional[int] = None,
    velocity_window_minutes: Optional[int] = None,
    customer_name: Optional[str] = None,
    customer_is_new: bool = False,
    large_tx_threshold: float = 500_000,
) -> ExplanationResult:
    """
    Generate a CFO-quality fraud explanation from rule data.

    Args:
        transaction_amount: NGN amount (not kobo)
        risk_score: 0–100 composite score
        risk_level: critical | high | medium | low
        rules_triggered: list of rule key strings
        transaction_hour: hour of day (0–23) if night_transaction fired
        velocity_count: number of transactions in window
        velocity_window_minutes: size of velocity window
        customer_name: for personalised messaging
        customer_is_new: for first-transaction rule context
        large_tx_threshold: the configured threshold for large amounts
    """
    customer_ref = f"customer {customer_name}" if customer_name else "this customer"
    ctx = RISK_LEVEL_CONTEXT.get(risk_level, RISK_LEVEL_CONTEXT["medium"])

    # ── Build factor list (human sentences) ───────────────────────────────────
    en_factors: List[str] = []
    pidgin_factors: List[str] = []

    for rule in rules_triggered:
        if rule not in RULE_DESCRIPTIONS:
            continue
        desc = RULE_DESCRIPTIONS[rule]

        if rule == "large_transaction_amount":
            en_factors.append(desc["en"](transaction_amount, large_tx_threshold))
            pidgin_factors.append(desc["pidgin"](transaction_amount, large_tx_threshold))
        elif rule == "night_transaction" and transaction_hour is not None:
            en_factors.append(desc["en"](transaction_hour))
            pidgin_factors.append(desc["pidgin"](transaction_hour))
        elif rule == "velocity_breach" and velocity_count and velocity_window_minutes:
            en_factors.append(desc["en"](velocity_count, velocity_window_minutes))
            pidgin_factors.append(desc["pidgin"](velocity_count, velocity_window_minutes))
        elif rule == "round_number_amount":
            en_factors.append(desc["en"](transaction_amount))
            pidgin_factors.append(desc["pidgin"](transaction_amount))
        elif rule == "potential_duplicate":
            en_factors.append(desc["en"]())
            pidgin_factors.append(desc["pidgin"]())
        elif rule == "high_value_first_transaction":
            en_factors.append(desc["en"](transaction_amount))
            pidgin_factors.append(desc["pidgin"](transaction_amount))

    # ── Construct narrative ───────────────────────────────────────────────────
    amount_str = format_naira_friendly(transaction_amount)
    n_factors = len(en_factors)

    if n_factors == 0:
        factor_sentence = "The transaction pattern deviates from your historical baseline."
        pidgin_factor_sentence = "This transaction no match your normal pattern."
    elif n_factors == 1:
        factor_sentence = f"Specifically, {en_factors[0]}."
        pidgin_factor_sentence = f"The issue na say {pidgin_factors[0]}."
    elif n_factors == 2:
        factor_sentence = f"Two things stand out: {en_factors[0]}, and {en_factors[1]}."
        pidgin_factor_sentence = f"Two things dey wrong: {pidgin_factors[0]}, and {pidgin_factors[1]}."
    else:
        joined_en = "; ".join(en_factors[:-1]) + f"; and {en_factors[-1]}"
        joined_pidgin = "; ".join(pidgin_factors[:-1]) + f"; and then {pidgin_factors[-1]}"
        factor_sentence = f"Multiple signals fired simultaneously: {joined_en}."
        pidgin_factor_sentence = f"Many things suspicious at the same time: {joined_pidgin}."

    # ── Headline ──────────────────────────────────────────────────────────────
    headline_map = {
        "critical": f"🚨 {amount_str} transaction flagged CRITICAL — {n_factors} fraud signals detected",
        "high": f"⚠️ {amount_str} transaction flagged HIGH risk — review before proceeding",
        "medium": f"⚡ {amount_str} transaction has {n_factors} unusual pattern{'s' if n_factors > 1 else ''}",
        "low": f"ℹ️ Minor anomaly on {amount_str} transaction — logged for monitoring",
    }
    headline = headline_map.get(risk_level, f"Fraud flag on {amount_str} transaction")

    # ── Summary (2–3 sentences) ────────────────────────────────────────────────
    summary = (
        f"{ctx['opener']} "
        f"A {amount_str} transaction from {customer_ref} scored {risk_score:.0f}/100 on the fraud risk scale. "
        f"{factor_sentence}"
    )

    # ── Detail (full paragraph) ───────────────────────────────────────────────
    detail = (
        f"{ctx['opener']} "
        f"SquadMind's fraud engine analysed a {amount_str} transaction from {customer_ref} "
        f"and assigned it a risk score of {risk_score:.0f} out of 100 — "
        f"placing it in the {risk_level.upper()} category. "
        f"{factor_sentence} "
        f"When multiple fraud signals fire on a single transaction, the combined risk is "
        f"significantly higher than any one signal alone. "
        f"{ctx['urgency']}"
    )

    # ── Pidgin versions ───────────────────────────────────────────────────────
    pidgin_summary = (
        f"{ctx['pidgin_opener']} "
        f"This {amount_str} transaction from {customer_ref} get risk score of {risk_score:.0f}/100. "
        f"{pidgin_factor_sentence}"
    )

    pidgin_detail = (
        f"{ctx['pidgin_opener']} "
        f"SquadMind check this {amount_str} transaction from {customer_ref} — "
        f"the risk score na {risk_score:.0f} out of 100 — {risk_level.upper()} level. "
        f"{pidgin_factor_sentence} "
        f"When many warning signs dey for one transaction, e more dangerous than just one sign. "
        f"{ctx['pidgin_urgency']} "
        f"{pick_pidgin_closer('fraud')}"
    )

    # ── Actions ───────────────────────────────────────────────────────────────
    actions = _build_fraud_actions(risk_level, rules_triggered, customer_name, velocity_count)

    # ── Key factors (short labels for frontend bullets) ────────────────────────
    key_factors_display = []
    rule_labels = {
        "large_transaction_amount": f"Unusually large amount ({amount_str})",
        "night_transaction": f"Late-night transaction ({_format_hour(transaction_hour) if transaction_hour else 'unusual hours'})",
        "velocity_breach": f"High frequency ({velocity_count} transactions in {velocity_window_minutes} min)" if velocity_count else "Transaction velocity breach",
        "round_number_amount": f"Suspiciously round amount ({amount_str})",
        "potential_duplicate": "Potential duplicate transaction",
        "high_value_first_transaction": f"New customer, high value ({amount_str})",
    }
    for rule in rules_triggered:
        key_factors_display.append(rule_labels.get(rule, rule.replace("_", " ").title()))

    return ExplanationResult(
        headline=headline,
        summary=summary,
        detail=detail,
        pidgin_summary=pidgin_summary,
        pidgin_detail=pidgin_detail,
        severity=risk_level,
        explanation_type="fraud",
        key_factors=key_factors_display,
        actions=actions,
        metrics_referenced={
            "transaction_amount": transaction_amount,
            "risk_score": risk_score,
            "risk_level": risk_level,
            "rules_triggered": rules_triggered,
            "rules_count": n_factors,
        },
        ai_enhanced=False,
    )


def _build_fraud_actions(
    risk_level: str,
    rules: List[str],
    customer_name: Optional[str],
    velocity_count: Optional[int],
) -> List[ActionRecommendation]:
    """Contextual action recommendations based on what fired."""
    actions = []
    customer_ref = customer_name or "the customer"

    if risk_level == "critical":
        actions.append(ActionRecommendation(
            priority="immediate",
            action=f"Put a temporary hold on this transaction and contact {customer_ref} directly via a phone call to verify their identity.",
            expected_outcome="Prevents funds from leaving if this is fraudulent. Most legitimate customers will respond quickly.",
            effort="quick",
        ))

    if "velocity_breach" in rules and velocity_count:
        actions.append(ActionRecommendation(
            priority="immediate",
            action=f"Review all {velocity_count} transactions from this customer in the last hour and check if they were authorised.",
            expected_outcome="Identifies whether this is a stolen card, a system glitch, or legitimate bulk activity.",
            effort="moderate",
        ))

    if "potential_duplicate" in rules:
        actions.append(ActionRecommendation(
            priority="immediate",
            action="Check your payment processor for duplicate charges. If confirmed, reverse the duplicate before the customer notices.",
            expected_outcome="Avoids a chargeback, maintains customer trust, and protects your reputation.",
            effort="quick",
        ))

    if "large_transaction_amount" in rules:
        actions.append(ActionRecommendation(
            priority="today",
            action=f"Request proof of purpose for this transaction from {customer_ref} — a purchase order, invoice, or written confirmation.",
            expected_outcome="Creates a paper trail that protects you if this becomes a dispute.",
            effort="quick",
        ))

    if "high_value_first_transaction" in rules:
        actions.append(ActionRecommendation(
            priority="today",
            action=f"Before fulfilling this order, verify {customer_ref}'s identity through a second channel — call them or request ID.",
            expected_outcome="Reduces risk of advance-fee fraud which is common with high-value new customer orders.",
            effort="quick",
        ))

    # Always add a monitoring action
    actions.append(ActionRecommendation(
        priority="this_week",
        action=f"Flag {customer_ref} for enhanced monitoring for the next 7 days. Any new transaction above ₦50,000 should trigger a manual review.",
        expected_outcome="Creates a safety net if this is part of a longer pattern of fraudulent activity.",
        effort="quick",
    ))

    return actions
