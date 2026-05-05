"""
SquadMind – Health Score Explanation Engine
Explains why a business scored what it scored and provides
a prioritised roadmap to improve it.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from app.services.explanations.templates import (
    ActionRecommendation,
    ExplanationResult,
    format_naira_friendly,
    pick_pidgin_closer,
)


# ── Component explanation templates ───────────────────────────────────────────
COMPONENT_EXPLANATIONS = {
    "revenue_growth": {
        "label": "Revenue Growth",
        90: ("Your revenue is growing consistently — your business is in an expansion phase.", "Your revenue dey grow steady — business dey expand!"),
        70: ("Revenue growth is healthy but could be more consistent week-to-week.", "Revenue dey grow but e fit be more consistent."),
        50: ("Revenue is relatively flat — you're maintaining but not growing.", "Revenue dey maintain — no growth but no fall either."),
        30: ("Revenue is declining — this is the most urgent area to address.", "Revenue dey fall — this na the most important thing to fix now."),
        0: ("Revenue is dropping significantly — immediate action is needed.", "Revenue don fall seriously — act now o!"),
    },
    "fraud_safety": {
        "label": "Fraud Safety",
        90: ("Your fraud rate is very low — your transaction patterns are healthy.", "Your fraud rate very low — your transactions dey clean!"),
        70: ("Fraud rate is manageable but worth monitoring.", "Fraud rate dey okay but keep watching am."),
        50: ("Elevated fraud signals detected — review flagged transactions.", "Too much fraud signals — check your flagged transactions."),
        30: ("High fraud activity detected — your business may be targeted.", "High fraud activity — your business fit be under attack!"),
        0: ("Critical fraud levels — review all recent transactions immediately.", "Critical fraud! Check all your recent transactions NOW!"),
    },
    "transaction_volume": {
        "label": "Transaction Volume",
        90: ("High transaction volume — your customer base is active and engaged.", "High transaction volume — your customers dey active!"),
        70: ("Good transaction volume with room to grow.", "Transaction volume dey okay — e fit be better."),
        50: ("Moderate transaction volume — your customer engagement could improve.", "Transaction volume moderate — customers no too active."),
        30: ("Low transaction volume — customer engagement needs work.", "Transaction volume low — you need more customer activity."),
        0: ("Very few transactions recorded — sync your Squad API data or increase sales activity.", "Very few transactions — connect Squad API or hustle more sales!"),
    },
    "payment_success_rate": {
        "label": "Payment Success Rate",
        90: ("Almost all payments succeed — your customers' payment experience is smooth.", "Almost all payments dey work — customers dey happy!"),
        70: ("Payment success rate is good with minor friction.", "Payment success rate dey okay."),
        50: ("Noticeable payment failures — investigate common failure reasons.", "Too many payment failures — find out why e dey fail."),
        30: ("High failure rate — customers may be abandoning payments.", "High failure rate — customers fit dey leave without paying!"),
        0: ("Most payments are failing — urgent investigation needed.", "Most payments dey fail — check am immediately!"),
    },
}

GRADE_NARRATIVE = {
    "A": {
        "en": "Your business is financially excellent — you're outperforming the majority of Nigerian SMEs at this scale.",
        "pidgin": "Your business excellent! You better pass most Nigerian SMEs for your level — e don do!",
    },
    "B": {
        "en": "Your business is financially healthy. A few targeted improvements could push you to excellent.",
        "pidgin": "Your business dey healthy! Small adjustments go push you to excellent level.",
    },
    "C": {
        "en": "Your business is stable but has clear areas for improvement. Address the weak components to move up.",
        "pidgin": "Business dey stable but e get room for improvement — fix the weak areas.",
    },
    "D": {
        "en": "Your business is financially stressed. Immediate focus on revenue and fraud prevention is essential.",
        "pidgin": "Your business dey struggle financially — focus on revenue and fraud prevention now!",
    },
    "F": {
        "en": "Your business is in a critical financial position. Treat this as an emergency and act this week.",
        "pidgin": "Your business dey critical position — treat am like emergency and act this week!",
    },
}

SCORE_CHANGE_NARRATIVES = {
    "improved_significantly": {
        "en": "improved significantly",
        "pidgin": "don improve seriously",
    },
    "improved_slightly": {
        "en": "ticked up slightly",
        "pidgin": "don go up small",
    },
    "unchanged": {
        "en": "remained steady",
        "pidgin": "remain the same",
    },
    "declined_slightly": {
        "en": "dipped slightly",
        "pidgin": "don drop small small",
    },
    "declined_significantly": {
        "en": "dropped significantly",
        "pidgin": "don fall seriously",
    },
}


def _get_score_bracket(score: int, thresholds: Dict) -> int:
    """Find the right narrative threshold for a given score."""
    int_keys = sorted([k for k in thresholds.keys() if isinstance(k, int)], reverse=True)
    for threshold in int_keys:
        if score >= threshold:
            return threshold
    return int_keys[-1]  # lowest bracket as fallback


def explain_health_score(
    current_score: int,
    grade: str,
    label: str,
    breakdown: Dict[str, int],             # {"revenue_growth": 82, "fraud_safety": 91, ...}
    previous_score: Optional[int] = None,   # Score from last period for change narrative
    business_name: Optional[str] = None,
) -> ExplanationResult:
    """
    Explain the financial health score with component-level detail
    and a prioritised improvement roadmap.
    """
    biz = business_name or "Your business"

    # ── Score change context ──────────────────────────────────────────────────
    if previous_score is not None:
        delta = current_score - previous_score
        if delta >= 10:
            change_key = "improved_significantly"
        elif delta >= 3:
            change_key = "improved_slightly"
        elif delta >= -2:
            change_key = "unchanged"
        elif delta >= -9:
            change_key = "declined_slightly"
        else:
            change_key = "declined_significantly"
        change_en = SCORE_CHANGE_NARRATIVES[change_key]["en"]
        change_pidgin = SCORE_CHANGE_NARRATIVES[change_key]["pidgin"]
        change_sentence = f" Since last period, your score has {change_en} from {previous_score} to {current_score}."
        change_pidgin_sentence = f" Since last period, your score {change_pidgin} from {previous_score} to {current_score}."
    else:
        change_sentence = ""
        change_pidgin_sentence = ""

    # ── Component analysis ────────────────────────────────────────────────────
    component_insights: List[str] = []
    component_pidgin: List[str] = []
    weakest_components: List[str] = []
    strongest_components: List[str] = []

    sorted_components = sorted(breakdown.items(), key=lambda x: x[1])

    for component, score in sorted_components:
        if component not in COMPONENT_EXPLANATIONS:
            continue
        comp_data = COMPONENT_EXPLANATIONS[component]
        bracket = _get_score_bracket(score, comp_data)
        en_text, pidgin_text = comp_data[bracket]
        component_insights.append(f"**{comp_data['label']} ({score}/100):** {en_text}")
        component_pidgin.append(f"{comp_data['label']} ({score}/100): {pidgin_text}")

        if score < 50:
            weakest_components.append(comp_data["label"].lower())
        elif score >= 80:
            strongest_components.append(comp_data["label"].lower())

    # ── Grade narrative ───────────────────────────────────────────────────────
    grade_text = GRADE_NARRATIVE.get(grade, GRADE_NARRATIVE["C"])

    # ── Improvement path ──────────────────────────────────────────────────────
    lowest_component = sorted_components[0] if sorted_components else None
    improvement_sentence = ""
    if lowest_component and lowest_component[1] < 70:
        comp_label = COMPONENT_EXPLANATIONS.get(lowest_component[0], {}).get("label", lowest_component[0])
        improvement_sentence = (
            f" Your biggest opportunity for improvement is {comp_label} "
            f"(currently {lowest_component[1]}/100) — improving this one area "
            f"could add 10–15 points to your overall score."
        )

    # ── Severity ──────────────────────────────────────────────────────────────
    severity_map = {"A": "positive", "B": "low", "C": "medium", "D": "high", "F": "critical"}
    severity = severity_map.get(grade, "medium")

    # ── Headlines ─────────────────────────────────────────────────────────────
    headline = f"{biz} scores {current_score}/100 — Grade {grade}: {label}"

    # ── Summary ──────────────────────────────────────────────────────────────
    summary = (
        f"{biz} has a Financial Health Score of {current_score} out of 100, earning a Grade {grade} ({label}) rating.{change_sentence} "
        f"{grade_text['en']}"
        + (f" Your weakest area is {weakest_components[0]}" if weakest_components else "")
        + "."
    )

    # ── Detail ────────────────────────────────────────────────────────────────
    detail = (
        f"SquadMind assessed {biz} across {len(breakdown)} financial health dimensions "
        f"and calculated an overall score of {current_score}/100 — Grade {grade}, which is {label}.{change_sentence} "
        f"{grade_text['en']}{improvement_sentence} "
        f"Here's how each dimension contributed: "
        + " | ".join(component_insights[:4])
        + "."
    )

    # ── Pidgin ────────────────────────────────────────────────────────────────
    pidgin_summary = (
        f"{biz} get Financial Health Score of {current_score} out of 100 — Grade {grade} ({label}).{change_pidgin_sentence} "
        f"{grade_text['pidgin']}"
        + (f" Your weakest area na {weakest_components[0]}" if weakest_components else "")
        + "."
    )

    pidgin_detail = (
        f"SquadMind check {biz} for {len(breakdown)} areas and give overall score of {current_score}/100 — Grade {grade}, {label}.{change_pidgin_sentence} "
        f"{grade_text['pidgin']} "
        + (" | ".join(component_pidgin[:3]))
        + ". " + pick_pidgin_closer("positive" if grade in ("A", "B") else "negative")
    )

    # ── Key factors ───────────────────────────────────────────────────────────
    key_factors = []
    for comp, score in sorted_components:
        comp_label = COMPONENT_EXPLANATIONS.get(comp, {}).get("label", comp)
        emoji = "✅" if score >= 80 else ("⚠️" if score >= 50 else "🔴")
        key_factors.append(f"{emoji} {comp_label}: {score}/100")

    # ── Actions ──────────────────────────────────────────────────────────────
    actions = _build_health_actions(grade, sorted_components, breakdown)

    return ExplanationResult(
        headline=headline,
        summary=summary,
        detail=detail,
        pidgin_summary=pidgin_summary,
        pidgin_detail=pidgin_detail,
        severity=severity,
        explanation_type="health_score",
        key_factors=key_factors,
        actions=actions,
        metrics_referenced={
            "current_score": current_score,
            "previous_score": previous_score,
            "grade": grade,
            "label": label,
            "breakdown": breakdown,
            "weakest_components": weakest_components,
            "strongest_components": strongest_components,
        },
        ai_enhanced=False,
    )


def _build_health_actions(
    grade: str,
    sorted_components: List,
    breakdown: Dict[str, int],
) -> List[ActionRecommendation]:
    actions = []

    # Address the weakest component first
    if sorted_components:
        worst_comp, worst_score = sorted_components[0]
        comp_label = COMPONENT_EXPLANATIONS.get(worst_comp, {}).get("label", worst_comp)

        if worst_comp == "revenue_growth":
            actions.append(ActionRecommendation(
                priority="this_week",
                action="Run a '3 Calls a Day' campaign — personally call 3 inactive customers each day for a week. Offer them a small incentive to return.",
                expected_outcome="Direct outreach re-activates 20–35% of dormant customers in Nigerian markets. Could add 8–12 points to your score.",
                effort="moderate",
            ))
        elif worst_comp == "fraud_safety":
            actions.append(ActionRecommendation(
                priority="today",
                action="Review all open fraud flags in SquadMind and resolve them — mark each as genuine, fraudulent, or dismissed after investigation.",
                expected_outcome="Resolving fraud flags improves your safety score and removes unnecessary risk exposure.",
                effort="moderate",
            ))
        elif worst_comp == "transaction_volume":
            actions.append(ActionRecommendation(
                priority="this_week",
                action="Launch a short promotion exclusively for existing customers — 'Pay once, get a bonus' deals work well for Nigerian consumer markets.",
                expected_outcome="Increasing transaction frequency from existing customers is 3x cheaper than acquiring new ones.",
                effort="moderate",
            ))
        elif worst_comp == "payment_success_rate":
            actions.append(ActionRecommendation(
                priority="today",
                action="Check your failed transactions — the most common failures are expired cards, insufficient funds, and bank network errors. Reach out to those customers directly.",
                expected_outcome="Re-attempting failed payments recovers 30–50% of them, often within 24 hours.",
                effort="quick",
            ))

    # Grade-based overall recommendation
    if grade in ("D", "F"):
        actions.append(ActionRecommendation(
            priority="immediate",
            action="Schedule a business review this week — look at your top 10 customers, your payment failure rate, and any open fraud cases. Treat this like a monthly board meeting.",
            expected_outcome="Businesses that review their financials weekly grow 23% faster than those that don't.",
            effort="significant",
        ))
    elif grade == "C":
        actions.append(ActionRecommendation(
            priority="this_week",
            action="Set revenue targets for the next 30 days and review them weekly. Even a 10% improvement in your weakest area will move your grade to B.",
            expected_outcome="Consistent monitoring moves 70% of Grade C businesses to Grade B within 60 days.",
            effort="moderate",
        ))
    elif grade in ("A", "B"):
        actions.append(ActionRecommendation(
            priority="monitor",
            action="Maintain your current practices and set up weekly health score monitoring. Your next step is expanding your customer base rather than fixing problems.",
            expected_outcome="Growing from Grade B to A typically requires expanding to 150%+ of current revenue volume.",
            effort="moderate",
        ))

    return actions
