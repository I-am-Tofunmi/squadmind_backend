"""
SquadMind – Revenue Explanation Engine
Turns raw revenue numbers into CFO-quality narrative: what happened,
why it happened, and what to do about it.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from app.services.explanations.templates import (
    ActionRecommendation,
    ExplanationResult,
    format_change,
    format_naira_friendly,
    pick_opener,
    pick_pidgin_closer,
    trend_verb,
)


# ── Nigerian Business Calendar Context ───────────────────────────────────────
NIGERIAN_CALENDAR_CONTEXT = {
    "january": "January is typically slow — post-holiday spending dip after the Christmas/New Year rush.",
    "february": "February often sees a mid-month bump due to Valentine's spending.",
    "march": "March is usually steady — end of Q1 often brings business-to-business payments.",
    "april": "April can dip around Easter, especially for consumer-facing businesses.",
    "may": "May tends to recover post-Easter. Mid-month salaries drive consumer spend.",
    "june": "June is end-of-Q2 — B2B invoices and government spending often spike.",
    "july": "July sees a seasonal dip in many sectors as schools close and spending shifts.",
    "august": "August is back-to-school month — retail and education-adjacent businesses often spike.",
    "september": "September is one of the strongest months — schools reopen, salaries paid, business picks up.",
    "october": "October is typically strong — Q4 begins and procurement budgets are opened.",
    "november": "November builds toward year-end. Black Friday effect starting to hit Nigerian retail.",
    "december": "December is peak season for most consumer businesses. B2B slows but retail surges.",
}

DAY_OF_WEEK_PATTERNS = {
    "monday": "Mondays are typically slow — customers are catching up on the week, not spending.",
    "tuesday": "Tuesdays are slightly below average for most businesses.",
    "wednesday": "Wednesday mid-week is usually the most consistent revenue day.",
    "thursday": "Thursdays often see a spending uptick as people anticipate the weekend.",
    "friday": "Fridays tend to be strong — end-of-week settlements and consumer spending.",
    "saturday": "Saturdays are strong for retail and food businesses, but slow for B2B.",
    "sunday": "Sundays are the slowest day for most Nigerian businesses.",
}


def explain_revenue(
    current_revenue: float,
    previous_revenue: float,
    change_percent: float,
    period_label: str,                          # "last 7 days" | "last 30 days" | "this month"
    total_transactions: int,
    avg_transaction_value: float,
    worst_day: Optional[Dict[str, Any]] = None,  # {"date": "Monday Jan 13", "amount": 45000, "count": 8}
    best_day: Optional[Dict[str, Any]] = None,
    top_customers_lost: Optional[List[str]] = None,  # customers who transacted before but not now
    payment_delays: Optional[int] = None,        # count of pending/failed transactions
    seasonal_month: Optional[str] = None,        # current month name (lowercase)
    channel_shift: Optional[Dict[str, float]] = None,  # {"card": -15.0, "bank_transfer": +22.0}
) -> ExplanationResult:
    """
    Generate a revenue explanation with context, cause analysis, and actions.
    """
    is_growth = change_percent >= 0
    abs_change = abs(change_percent)
    severity = _revenue_severity(change_percent)

    current_str = format_naira_friendly(current_revenue)
    previous_str = format_naira_friendly(previous_revenue)
    avg_str = format_naira_friendly(avg_transaction_value)
    change_str = format_change(change_percent)
    verb = trend_verb(change_percent)

    # ── Identify primary cause ────────────────────────────────────────────────
    causes: List[str] = []
    pidgin_causes: List[str] = []

    if worst_day:
        day_name = worst_day.get("date", "one day")
        day_amount = worst_day.get("amount", 0)
        causes.append(
            f"{day_name} was your weakest day at only {format_naira_friendly(day_amount)} "
            f"— significantly below your daily average"
        )
        pidgin_causes.append(
            f"{day_name} na your worst day — only {format_naira_friendly(day_amount)} enter, e weak die"
        )

    if top_customers_lost:
        count = len(top_customers_lost)
        names = ", ".join(top_customers_lost[:2])
        suffix = f" and {count - 2} others" if count > 2 else ""
        causes.append(
            f"{count} regular customer{'s' if count > 1 else ''} "
            f"({names}{suffix}) did not transact this period — that gap contributed to the drop"
        )
        pidgin_causes.append(
            f"{count} regular customer{'s' if count > 1 else ''} ({names}{suffix}) "
            f"no show this period — dem just disappear, na that one cause the gap"
        )

    if payment_delays and payment_delays > 0:
        causes.append(
            f"{payment_delays} transaction{'s' if payment_delays > 1 else ''} "
            f"{'were' if payment_delays > 1 else 'was'} delayed or failed and not yet settled"
        )
        pidgin_causes.append(
            f"{payment_delays} transaction{'s' if payment_delays > 1 else ''} fail or dey pending — "
            f"that money never enter your account"
        )

    if seasonal_month and not is_growth:
        context = NIGERIAN_CALENDAR_CONTEXT.get(seasonal_month.lower(), "")
        if context:
            causes.append(f"seasonal context: {context.lower()}")
            pidgin_causes.append(f"season matter: {context.lower()}")

    if channel_shift:
        biggest_drop = min(channel_shift.items(), key=lambda x: x[1], default=None)
        if biggest_drop and biggest_drop[1] < -10:
            ch, pct = biggest_drop
            causes.append(
                f"your {ch.replace('_', ' ')} payment channel dropped by {abs(pct):.0f}% this period"
            )
            pidgin_causes.append(
                f"your {ch.replace('_', ' ')} channel don drop {abs(pct):.0f}% — customers dey shift"
            )

    # ── Headline ──────────────────────────────────────────────────────────────
    if is_growth:
        headline = f"Revenue {verb} {change_str} — {current_str} earned in {period_label}"
    else:
        headline = f"Revenue {verb} {change_str} — down from {previous_str} to {current_str}"

    # ── Summary ───────────────────────────────────────────────────────────────
    if causes:
        cause_text = causes[0]
        summary = (
            f"Your revenue {verb} by {abs_change:.1f}% compared to the previous {period_label}, "
            f"bringing in {current_str} from {total_transactions:,} transactions. "
            f"The main driver was {cause_text}."
        )
    else:
        summary = (
            f"Your revenue {verb} by {abs_change:.1f}% compared to the previous {period_label}. "
            f"You earned {current_str} from {total_transactions:,} transactions "
            f"at an average of {avg_str} per transaction."
        )

    # ── Detail ────────────────────────────────────────────────────────────────
    cause_paragraph = ""
    if causes:
        if len(causes) == 1:
            cause_paragraph = f"The primary driver was {causes[0]}."
        else:
            joined = "; ".join(causes[:3])
            cause_paragraph = f"Several factors contributed: {joined}."

    best_day_note = ""
    if best_day:
        best_day_note = (
            f" Your strongest day was {best_day.get('date', 'one day')} with "
            f"{format_naira_friendly(best_day.get('amount', 0))} in revenue."
        )

    detail = (
        f"Over the {period_label}, your business generated {current_str} in revenue "
        f"from {total_transactions:,} successful transactions, "
        f"compared to {previous_str} in the prior period — "
        f"a {abs_change:.1f}% {'increase' if is_growth else 'decrease'}. "
        f"Your average transaction value was {avg_str}.{best_day_note} "
        f"{cause_paragraph} "
        + (
            "This growth trajectory is healthy — your revenue base is expanding."
            if is_growth and abs_change > 10
            else "While the decline is concerning, it's recoverable with targeted action on your key accounts."
            if not is_growth and abs_change > 10
            else "The change is within normal variance — continue monitoring weekly."
        )
    )

    # ── Pidgin ────────────────────────────────────────────────────────────────
    if pidgin_causes:
        pidgin_cause_text = pidgin_causes[0]
        pidgin_summary = (
            f"Your revenue {verb} by {abs_change:.1f}% compared to last {period_label} — "
            f"total na {current_str} from {total_transactions:,} transactions. "
            f"The main thing wey cause am: {pidgin_cause_text}."
        )
    else:
        pidgin_summary = (
            f"Your revenue {verb} by {abs_change:.1f}%. You make {current_str} from "
            f"{total_transactions:,} transactions — average na {avg_str} per transaction."
        )

    pidgin_detail = (
        f"For this {period_label}, your business make {current_str} compared to {previous_str} "
        f"for the period before — na {abs_change:.1f}% {'more' if is_growth else 'less'}. "
        f"Average transaction na {avg_str}. "
        + (f"The thing wey cause am: {'; '.join(pidgin_causes[:2])}. " if pidgin_causes else "")
        + pick_pidgin_closer("positive" if is_growth else "negative")
    )

    # ── Actions ───────────────────────────────────────────────────────────────
    actions = _build_revenue_actions(
        is_growth, abs_change, top_customers_lost, payment_delays, channel_shift
    )

    return ExplanationResult(
        headline=headline,
        summary=summary,
        detail=detail,
        pidgin_summary=pidgin_summary,
        pidgin_detail=pidgin_detail,
        severity=severity,
        explanation_type="revenue",
        key_factors=[c.split(".")[0][:100] for c in causes] or ["Revenue trend within normal range"],
        actions=actions,
        metrics_referenced={
            "current_revenue": current_revenue,
            "previous_revenue": previous_revenue,
            "change_percent": change_percent,
            "total_transactions": total_transactions,
            "avg_transaction_value": avg_transaction_value,
            "period": period_label,
        },
        ai_enhanced=False,
    )


def _revenue_severity(change_percent: float) -> str:
    if change_percent >= 20:
        return "positive"
    elif change_percent >= 0:
        return "low"
    elif change_percent >= -10:
        return "medium"
    elif change_percent >= -25:
        return "high"
    else:
        return "critical"


def _build_revenue_actions(
    is_growth: bool,
    abs_change: float,
    customers_lost: Optional[List[str]],
    payment_delays: Optional[int],
    channel_shift: Optional[Dict],
) -> List[ActionRecommendation]:
    actions = []

    if not is_growth and customers_lost:
        names = ", ".join(customers_lost[:3])
        actions.append(ActionRecommendation(
            priority="today",
            action=f"Reach out to {names} — a personal call or WhatsApp message asking if everything is okay often brings customers back.",
            expected_outcome="Re-engaging just 2 of your top customers could recover 30–40% of the revenue gap.",
            effort="quick",
        ))

    if payment_delays and payment_delays > 0:
        actions.append(ActionRecommendation(
            priority="immediate",
            action=f"Follow up on {payment_delays} pending/failed payment{'s' if payment_delays > 1 else ''}. Send payment reminders via WhatsApp — it has a 90%+ open rate in Nigeria.",
            expected_outcome="Recovering even half of these transactions can materially improve your period close.",
            effort="quick",
        ))

    if not is_growth and abs_change > 20:
        actions.append(ActionRecommendation(
            priority="this_week",
            action="Run a short-term promotion — a 5–10% discount for this week only creates urgency and can quickly bring volume back.",
            expected_outcome="Flash promotions often recover 15–25% of lost revenue within 7 days.",
            effort="moderate",
        ))

    if is_growth and abs_change > 15:
        actions.append(ActionRecommendation(
            priority="this_week",
            action="Identify what drove this growth — which customers, channels, or products performed best? Double down on what's working.",
            expected_outcome="Understanding your growth drivers lets you repeat and amplify them intentionally.",
            effort="moderate",
        ))

    if channel_shift:
        growing_channels = {k: v for k, v in channel_shift.items() if v > 10}
        if growing_channels:
            best = max(growing_channels, key=growing_channels.get)
            actions.append(ActionRecommendation(
                priority="this_week",
                action=f"Your {best.replace('_', ' ')} channel is growing fastest — consider promoting it as a payment option to all customers.",
                expected_outcome="Shifting more volume to your highest-performing channel improves both conversion and cash flow.",
                effort="quick",
            ))

    # Always monitor
    actions.append(ActionRecommendation(
        priority="monitor",
        action="Set up a weekly revenue alert in SquadMind — you'll get a WhatsApp/email summary every Monday morning before you start your week.",
        expected_outcome="Staying ahead of trends means you can react in days, not weeks.",
        effort="quick",
    ))

    return actions
