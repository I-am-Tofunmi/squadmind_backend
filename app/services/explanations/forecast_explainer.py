"""
SquadMind – Forecast Explanation Engine
Explains cash flow projections in CFO language — not just numbers,
but what they mean for the business and what risks to watch for.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from app.services.explanations.templates import (
    ActionRecommendation,
    ExplanationResult,
    format_naira_friendly,
    pick_pidgin_closer,
)


CONFIDENCE_LABELS = {
    "high":   (70, 100, "High confidence", "High confidence — plenty data back this forecast"),
    "medium": (40, 70,  "Medium confidence", "Medium confidence — forecast based on moderate data"),
    "low":    (0,  40,  "Low confidence",   "Low confidence — need more transaction history"),
}

ALGORITHM_PLAIN = {
    "moving_average":   "a 7-day moving average of your recent revenue",
    "weighted_ma":      "a weighted average that gives more weight to recent trends",
    "trend_adjusted":   "a trend-based model that accounts for the direction your revenue is moving",
}

RISK_SCENARIOS = {
    "revenue_below_projection": {
        "en": "revenue coming in below projection",
        "pidgin": "revenue come less than we expect",
        "mitigation": "Pre-collect deposits on large orders and negotiate shorter payment terms with regular customers.",
    },
    "seasonal_slowdown": {
        "en": "a seasonal slowdown in your industry",
        "pidgin": "season slow down your business",
        "mitigation": "Build a cash reserve now — target 6 weeks of operating expenses before the slow period hits.",
    },
    "customer_concentration": {
        "en": "one or two key customers reducing their spending",
        "pidgin": "your biggest customers reduce their spending",
        "mitigation": "Diversify — no single customer should exceed 30% of your revenue. Start acquiring new accounts now.",
    },
    "payment_delays": {
        "en": "delayed payments pushing your actual cash below the forecast",
        "pidgin": "customers delay payment and your cash go drop",
        "mitigation": "Use Squad's payment links proactively — send reminders 3 days before payment is due.",
    },
}


def explain_forecast(
    projected_revenue: float,
    projected_net: float,
    confidence_score: float,
    algorithm: str,
    days_ahead: int,
    lookback_days: int,
    transaction_count_used: int,
    current_daily_avg: float,
    trend_direction: str,              # "up" | "down" | "flat"
    top_risk: Optional[str] = None,   # key from RISK_SCENARIOS
    cash_reserve_days: Optional[float] = None,  # estimated days of expenses covered
    seasonal_risk_month: Optional[str] = None,
) -> ExplanationResult:
    """
    Generate a CFO-quality forecast explanation with risk assessment.
    """
    rev_str = format_naira_friendly(projected_revenue)
    net_str = format_naira_friendly(projected_net)
    daily_str = format_naira_friendly(current_daily_avg)
    algo_text = ALGORITHM_PLAIN.get(algorithm, "a statistical model")

    # ── Confidence label ──────────────────────────────────────────────────────
    conf_label_en = "Low confidence"
    conf_label_pidgin = "Low confidence"
    conf_qualifier = ""
    for key, (low, high, label_en, label_pidgin) in CONFIDENCE_LABELS.items():
        if low <= confidence_score <= high:
            conf_label_en = label_en
            conf_label_pidgin = label_pidgin
            break

    if confidence_score >= 70:
        conf_qualifier = "This forecast is well-supported by your transaction history."
        conf_qualifier_pidgin = "This forecast get strong support from your transaction history."
    elif confidence_score >= 40:
        conf_qualifier = f"Based on {transaction_count_used:,} transactions over {lookback_days} days, this projection has moderate reliability."
        conf_qualifier_pidgin = f"Based on {transaction_count_used:,} transactions for {lookback_days} days, this forecast moderate reliable."
    else:
        conf_qualifier = f"Only {transaction_count_used:,} transactions were available — sync more transaction history via Squad API to improve accuracy."
        conf_qualifier_pidgin = f"Only {transaction_count_used:,} transactions dey available — sync more data from Squad API to improve this forecast."

    # ── Trend sentence ────────────────────────────────────────────────────────
    if trend_direction == "up":
        trend_sentence = f"The model detected an upward revenue trend — your daily average of {daily_str} is projected to grow over the {days_ahead}-day window."
        trend_pidgin = f"Revenue trend dey go up — your daily average of {daily_str} go grow for this {days_ahead}-day period."
    elif trend_direction == "down":
        trend_sentence = f"Caution: the model detected a downward trend. Your daily average of {daily_str} is expected to face some pressure."
        trend_pidgin = f"Careful — revenue trend dey go down. Your daily average of {daily_str} go face some pressure."
    else:
        trend_sentence = f"Your revenue trend is stable. The model projects continuation of your current daily average of {daily_str}."
        trend_pidgin = f"Your revenue trend stable. The forecast say your daily average of {daily_str} go continue."

    # ── Expense assumption note ───────────────────────────────────────────────
    expense_ratio = (projected_revenue - projected_net) / projected_revenue * 100 if projected_revenue > 0 else 35
    expense_note = (
        f"The net projection of {net_str} assumes a {expense_ratio:.0f}% operating expense ratio. "
        f"If your actual expenses are higher, your net could be lower — review your cost structure."
    )
    expense_note_pidgin = (
        f"The net projection of {net_str} assume {expense_ratio:.0f}% operating expenses. "
        f"If your actual expenses more than this, your net go be less — check your costs."
    )

    # ── Risk scenario ─────────────────────────────────────────────────────────
    risk_sentence = ""
    risk_pidgin = ""
    risk_action = None

    if top_risk and top_risk in RISK_SCENARIOS:
        risk = RISK_SCENARIOS[top_risk]
        risk_sentence = f"The primary risk to this forecast is {risk['en']}. {risk['mitigation']}"
        risk_pidgin = f"The main risk na {risk['pidgin']}. {risk['mitigation']}"
        risk_action = ActionRecommendation(
            priority="this_week",
            action=risk["mitigation"],
            expected_outcome="Mitigating this risk could protect 20–40% of your projected net income.",
            effort="moderate",
        )

    # ── Cash reserve context ──────────────────────────────────────────────────
    reserve_note = ""
    if cash_reserve_days is not None:
        if cash_reserve_days < 14:
            reserve_note = f"Warning: your estimated cash reserve covers only {cash_reserve_days:.0f} days of operations. This is critically low — prioritise collections."
        elif cash_reserve_days < 30:
            reserve_note = f"Your cash reserve of approximately {cash_reserve_days:.0f} days is below the recommended 30-day buffer. Build this up as a priority."
        else:
            reserve_note = f"Your cash reserve of {cash_reserve_days:.0f} days is healthy — you have a good buffer against slow periods."

    # ── Severity ─────────────────────────────────────────────────────────────
    if trend_direction == "down" or confidence_score < 40:
        severity = "medium"
    elif trend_direction == "up" and confidence_score >= 70:
        severity = "positive"
    else:
        severity = "low"

    # ── Headline ─────────────────────────────────────────────────────────────
    headline = (
        f"30-day revenue forecast: {rev_str} projected "
        f"({conf_label_en.lower()}, trend {trend_direction})"
    )

    # ── Summary ──────────────────────────────────────────────────────────────
    summary = (
        f"Based on {transaction_count_used:,} transactions over the last {lookback_days} days, "
        f"SquadMind projects {rev_str} in total revenue for the next {days_ahead} days, "
        f"with an estimated net income of {net_str}. "
        f"{trend_sentence} "
        f"{conf_qualifier}"
    )

    # ── Detail ────────────────────────────────────────────────────────────────
    detail = (
        f"This {days_ahead}-day forecast was generated using {algo_text}. "
        f"The model analysed {transaction_count_used:,} transactions spanning {lookback_days} days "
        f"and calculated a confidence score of {confidence_score:.0f}/100 ({conf_label_en}). "
        f"{trend_sentence} "
        f"{expense_note} "
        + (f"{risk_sentence} " if risk_sentence else "")
        + (f"{reserve_note} " if reserve_note else "")
        + f"Update this forecast weekly as new transaction data comes in — accuracy improves significantly with 90+ days of history."
    )

    # ── Pidgin ────────────────────────────────────────────────────────────────
    pidgin_summary = (
        f"Based on {transaction_count_used:,} transactions for {lookback_days} days, "
        f"SquadMind project {rev_str} revenue for the next {days_ahead} days — "
        f"net income go reach {net_str}. "
        f"{trend_pidgin} "
        f"{conf_qualifier_pidgin}"
    )

    pidgin_detail = (
        f"This {days_ahead}-day forecast use {algo_text}. "
        f"The model check {transaction_count_used:,} transactions for {lookback_days} days "
        f"and confidence score na {confidence_score:.0f}/100 ({conf_label_pidgin}). "
        f"{trend_pidgin} {expense_note_pidgin} "
        + (f"{risk_pidgin} " if risk_pidgin else "")
        + pick_pidgin_closer("positive" if trend_direction == "up" else "neutral")
    )

    # ── Key factors ───────────────────────────────────────────────────────────
    key_factors = [
        f"Projected revenue: {rev_str} over {days_ahead} days",
        f"Estimated net: {net_str} (after {expense_ratio:.0f}% expense assumption)",
        f"Confidence: {confidence_score:.0f}/100 ({conf_label_en})",
        f"Based on: {transaction_count_used:,} transactions / {lookback_days} days",
        f"Daily average: {daily_str}",
        f"Trend direction: {trend_direction.capitalize()}",
    ]
    if top_risk:
        key_factors.append(f"Primary risk: {RISK_SCENARIOS.get(top_risk, {}).get('en', top_risk)}")

    # ── Actions ──────────────────────────────────────────────────────────────
    actions = _build_forecast_actions(
        trend_direction, confidence_score, projected_net, cash_reserve_days, risk_action
    )

    return ExplanationResult(
        headline=headline,
        summary=summary,
        detail=detail,
        pidgin_summary=pidgin_summary,
        pidgin_detail=pidgin_detail,
        severity=severity,
        explanation_type="forecast",
        key_factors=key_factors,
        actions=actions,
        metrics_referenced={
            "projected_revenue": projected_revenue,
            "projected_net": projected_net,
            "confidence_score": confidence_score,
            "days_ahead": days_ahead,
            "lookback_days": lookback_days,
            "transaction_count_used": transaction_count_used,
            "current_daily_avg": current_daily_avg,
            "trend_direction": trend_direction,
            "algorithm": algorithm,
        },
        ai_enhanced=False,
    )


def _build_forecast_actions(
    trend_direction: str,
    confidence: float,
    projected_net: float,
    cash_reserve_days: Optional[float],
    risk_action: Optional[ActionRecommendation],
) -> List[ActionRecommendation]:
    actions = []

    if cash_reserve_days is not None and cash_reserve_days < 30:
        actions.append(ActionRecommendation(
            priority="immediate" if cash_reserve_days < 14 else "this_week",
            action="Accelerate collections — identify overdue invoices and send payment reminders via WhatsApp today. Offer a 2% early payment discount to incentivise speed.",
            expected_outcome=f"Recovering 30% of outstanding invoices could extend your cash runway by {max(0, 30 - int(cash_reserve_days))} days.",
            effort="moderate",
        ))

    if trend_direction == "down":
        actions.append(ActionRecommendation(
            priority="this_week",
            action="Audit your expenses — identify any non-essential costs that can be paused for 30 days while revenue recovers.",
            expected_outcome="Reducing variable costs by 15% during a down period can preserve the same net income as a 20% revenue increase.",
            effort="moderate",
        ))

    if confidence < 40:
        actions.append(ActionRecommendation(
            priority="today",
            action="Sync more transaction history via Squad API — the more data SquadMind has, the more accurate your forecast becomes. Aim for 90 days of history.",
            expected_outcome="Going from low to high confidence often doubles the forecast accuracy. Better accuracy = better decisions.",
            effort="quick",
        ))

    if risk_action:
        actions.append(risk_action)

    if trend_direction == "up":
        actions.append(ActionRecommendation(
            priority="this_week",
            action="Use this growth window to negotiate better supplier terms — growing revenue gives you leverage to ask for volume discounts or extended payment periods.",
            expected_outcome="Improving your supplier terms during growth periods can add 5–8% to your net margins.",
            effort="moderate",
        ))

    actions.append(ActionRecommendation(
        priority="monitor",
        action="Regenerate this forecast in 7 days — weekly forecasting keeps you ahead of surprises and helps you spot trend changes early.",
        expected_outcome="Businesses that forecast weekly are 40% more likely to avoid cash flow crises.",
        effort="quick",
    ))

    return actions
