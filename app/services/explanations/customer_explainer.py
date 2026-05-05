"""
SquadMind – Customer Behaviour Explanation Engine
Translates customer analytics into actionable CFO insights.
Covers: churn signals, top customer concentration, new vs returning mix,
loyalty patterns, and payment behaviour.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from app.services.explanations.templates import (
    ActionRecommendation,
    ExplanationResult,
    format_naira_friendly,
    pick_pidgin_closer,
)


def explain_customer_behavior(
    unique_customers: int,
    returning_customer_rate: float,         # 0–100 %
    top_customer_revenue_share: float,      # % of total revenue from top 3 customers
    churned_customers: Optional[int] = None,  # customers who transacted last period but not this
    new_customers: Optional[int] = None,
    avg_customer_lifetime_value: Optional[float] = None,
    most_valuable_customer: Optional[Dict] = None,  # {"name": "...", "spend": 450000, "tx_count": 23}
    payment_behaviour: Optional[str] = None,  # "improving" | "declining" | "stable"
    avg_days_between_purchases: Optional[float] = None,
) -> ExplanationResult:
    """Generate customer behaviour explanation."""

    # ── Concentration risk ────────────────────────────────────────────────────
    concentration_risk = top_customer_revenue_share > 40
    concentration_critical = top_customer_revenue_share > 60

    # ── Returning customer health ─────────────────────────────────────────────
    if returning_customer_rate >= 70:
        retention_level = "excellent"
        retention_en = f"Your customer retention rate of {returning_customer_rate:.0f}% is excellent — your customers are loyal and keep coming back."
        retention_pidgin = f"Your customer retention dey excellent at {returning_customer_rate:.0f}% — your customers dey loyal die!"
    elif returning_customer_rate >= 50:
        retention_level = "good"
        retention_en = f"Your {returning_customer_rate:.0f}% returning customer rate is solid — more than half your customers are loyal."
        retention_pidgin = f"Your {returning_customer_rate:.0f}% returning customer rate dey good — more than half dey come back."
    elif returning_customer_rate >= 30:
        retention_level = "moderate"
        retention_en = f"Your returning customer rate of {returning_customer_rate:.0f}% is moderate — there's room to improve loyalty and repeat business."
        retention_pidgin = f"Your {returning_customer_rate:.0f}% returning rate moderate — you fit improve customer loyalty."
    else:
        retention_level = "low"
        retention_en = f"Your returning customer rate is only {returning_customer_rate:.0f}% — most customers are buying once and not returning. This is costly."
        retention_pidgin = f"Only {returning_customer_rate:.0f}% of your customers dey return — most buy once and disappear. E dey cost you."

    # ── Churn insight ─────────────────────────────────────────────────────────
    churn_sentence = ""
    churn_pidgin = ""
    if churned_customers and churned_customers > 0:
        churn_sentence = f" {churned_customers} customer{'s who were' if churned_customers > 1 else ' who was'} active last period did not transact this period — that's potential revenue at risk."
        churn_pidgin = f" {churned_customers} customer{'s' if churned_customers > 1 else ''} wey dey active last time no show this period — that revenue don dey risk."

    # ── New customer acquisition ──────────────────────────────────────────────
    new_customer_sentence = ""
    new_customer_pidgin = ""
    if new_customers is not None:
        if new_customers > 0:
            new_customer_sentence = f" {new_customers} new customer{'s' if new_customers > 1 else ''} were acquired this period — healthy sign of growth."
            new_customer_pidgin = f" {new_customers} new customer{'s' if new_customers > 1 else ''} don enter this period — good sign!"
        else:
            new_customer_sentence = " No new customers were acquired this period — your growth is entirely dependent on existing accounts."
            new_customer_pidgin = " No new customers come this period — your growth depend only on your existing customers."

    # ── Top customer context ───────────────────────────────────────────────────
    concentration_sentence = ""
    concentration_pidgin = ""
    if concentration_critical:
        concentration_sentence = f" Your top customers account for {top_customer_revenue_share:.0f}% of total revenue — this concentration is a serious business risk. If one key account leaves, it could significantly destabilise your cash flow."
        concentration_pidgin = f" Your top customers carry {top_customer_revenue_share:.0f}% of your revenue — this na serious risk. If one big customer commot, e go affect you seriously."
    elif concentration_risk:
        concentration_sentence = f" Your top customers account for {top_customer_revenue_share:.0f}% of revenue. This is a moderate concentration risk — work on diversifying your customer base."
        concentration_pidgin = f" Your top customers carry {top_customer_revenue_share:.0f}% of your revenue — moderate risk. Work on getting more customers."

    # ── Purchase frequency ────────────────────────────────────────────────────
    frequency_sentence = ""
    frequency_pidgin = ""
    if avg_days_between_purchases is not None:
        if avg_days_between_purchases <= 7:
            frequency_sentence = f" Your average customer buys every {avg_days_between_purchases:.0f} days — very high frequency, excellent for cash flow."
            frequency_pidgin = f" Your average customer dey buy every {avg_days_between_purchases:.0f} days — very frequent, excellent for cash flow!"
        elif avg_days_between_purchases <= 30:
            frequency_sentence = f" Customers buy on average every {avg_days_between_purchases:.0f} days — healthy monthly purchase cycle."
            frequency_pidgin = f" Customers dey buy every {avg_days_between_purchases:.0f} days — healthy monthly cycle."
        else:
            frequency_sentence = f" Customers buy on average every {avg_days_between_purchases:.0f} days — infrequent. Increasing purchase frequency is the fastest path to revenue growth."
            frequency_pidgin = f" Customers dey buy every {avg_days_between_purchases:.0f} days — too slow. You need to make them buy more often."

    # ── Most valuable customer spotlight ──────────────────────────────────────
    mvc_sentence = ""
    mvc_pidgin = ""
    if most_valuable_customer:
        name = most_valuable_customer.get("name", "your top customer")
        spend = most_valuable_customer.get("spend", 0)
        tx = most_valuable_customer.get("tx_count", 0)
        mvc_sentence = f" Your most valuable customer — {name} — spent {format_naira_friendly(spend)} across {tx} transactions. This relationship deserves dedicated attention."
        mvc_pidgin = f" Your most valuable customer na {name} — dem spend {format_naira_friendly(spend)} for {tx} transactions. This relationship dey very important — protect am!"

    # ── Severity ──────────────────────────────────────────────────────────────
    if concentration_critical or retention_level == "low":
        severity = "high"
    elif concentration_risk or retention_level == "moderate" or (churned_customers and churned_customers > 5):
        severity = "medium"
    elif retention_level == "excellent":
        severity = "positive"
    else:
        severity = "low"

    # ── Headline ──────────────────────────────────────────────────────────────
    headline = (
        f"{unique_customers:,} active customers — "
        f"{returning_customer_rate:.0f}% retention rate, "
        f"concentration {'⚠️ HIGH' if concentration_risk else '✅ healthy'}"
    )

    # ── Summary ──────────────────────────────────────────────────────────────
    summary = (
        f"{retention_en}{churn_sentence}{new_customer_sentence}{concentration_sentence}"
    )

    # ── Detail ────────────────────────────────────────────────────────────────
    detail = (
        f"Your customer base consists of {unique_customers:,} active accounts this period. "
        f"{retention_en}{frequency_sentence}{mvc_sentence}"
        f"{churn_sentence}{new_customer_sentence}{concentration_sentence} "
        + ("Your customer metrics are healthy overall — focus on increasing average order value as the next lever." if severity == "positive"
           else "Addressing the concentration risk and improving retention are the highest-leverage customer actions you can take right now.")
    )

    # ── Pidgin ────────────────────────────────────────────────────────────────
    pidgin_summary = (
        f"{retention_pidgin}{churn_pidgin}{new_customer_pidgin}{concentration_pidgin}"
    )
    pidgin_detail = (
        f"Your customer base get {unique_customers:,} active accounts this period. "
        f"{retention_pidgin}{frequency_pidgin}{mvc_pidgin}"
        f"{churn_pidgin}{new_customer_pidgin}{concentration_pidgin} "
        + pick_pidgin_closer("positive" if severity == "positive" else "neutral")
    )

    # ── Key factors ───────────────────────────────────────────────────────────
    key_factors = [
        f"Active customers: {unique_customers:,}",
        f"Returning rate: {returning_customer_rate:.0f}% ({retention_level})",
        f"Top customer concentration: {top_customer_revenue_share:.0f}% of revenue",
    ]
    if churned_customers:
        key_factors.append(f"Churned this period: {churned_customers}")
    if new_customers is not None:
        key_factors.append(f"New customers acquired: {new_customers}")
    if avg_days_between_purchases:
        key_factors.append(f"Avg purchase frequency: every {avg_days_between_purchases:.0f} days")

    # ── Actions ──────────────────────────────────────────────────────────────
    actions = _build_customer_actions(
        returning_customer_rate, churned_customers, new_customers,
        concentration_critical, concentration_risk, avg_days_between_purchases,
        most_valuable_customer,
    )

    return ExplanationResult(
        headline=headline,
        summary=summary,
        detail=detail,
        pidgin_summary=pidgin_summary,
        pidgin_detail=pidgin_detail,
        severity=severity,
        explanation_type="customer_behavior",
        key_factors=key_factors,
        actions=actions,
        metrics_referenced={
            "unique_customers": unique_customers,
            "returning_customer_rate": returning_customer_rate,
            "top_customer_revenue_share": top_customer_revenue_share,
            "churned_customers": churned_customers,
            "new_customers": new_customers,
            "avg_days_between_purchases": avg_days_between_purchases,
        },
        ai_enhanced=False,
    )


def _build_customer_actions(
    retention_rate: float,
    churned: Optional[int],
    new_customers: Optional[int],
    concentration_critical: bool,
    concentration_risk: bool,
    purchase_frequency: Optional[float],
    mvc: Optional[Dict],
) -> List[ActionRecommendation]:
    actions = []

    if churned and churned > 0:
        actions.append(ActionRecommendation(
            priority="today",
            action=f"Send a personal WhatsApp message to each of the {churned} churned customers — something like 'We noticed you haven't been around — we miss you! Is everything okay?' A human touch recovers 30–40% of churned customers.",
            expected_outcome="Re-activating churned customers is 5x cheaper than acquiring new ones and can quickly recover lost revenue.",
            effort="quick",
        ))

    if concentration_critical:
        actions.append(ActionRecommendation(
            priority="this_week",
            action="Start an aggressive new customer acquisition campaign — target at least 5 new accounts in the next 30 days. Use referrals from your existing customers as the primary channel.",
            expected_outcome="Reducing top-3 customer concentration from 60%+ to below 40% takes 3–6 months but protects your business from devastating losses.",
            effort="significant",
        ))

    if concentration_risk and mvc:
        mvc_name = mvc.get("name", "your top customer")
        actions.append(ActionRecommendation(
            priority="this_week",
            action=f"Deepen your relationship with {mvc_name} — offer them loyalty perks, preferred pricing, or dedicated service. Making key accounts feel valued dramatically reduces their churn risk.",
            expected_outcome="Customers who feel appreciated have 80% lower churn rates. Protecting your top account protects your cash flow.",
            effort="quick",
        ))

    if purchase_frequency and purchase_frequency > 30:
        actions.append(ActionRecommendation(
            priority="this_week",
            action="Launch a repeat purchase incentive — 'Buy again within 14 days and get X' creates urgency. SMS campaigns get 90%+ open rates in Nigeria.",
            expected_outcome="Even moving average purchase frequency from 45 to 30 days can increase revenue by 33% with the same customer base.",
            effort="moderate",
        ))

    if not new_customers or new_customers == 0:
        actions.append(ActionRecommendation(
            priority="this_week",
            action="Ask every existing customer for one referral — incentivise it with a small discount for both parties. Referral acquisition is 3x cheaper than paid ads in the Nigerian market.",
            expected_outcome="A consistent referral programme adds 10–20% new customers monthly with minimal marketing spend.",
            effort="quick",
        ))

    if retention_rate < 40:
        actions.append(ActionRecommendation(
            priority="this_week",
            action="Investigate why customers are not returning — call 5 former customers and ask them directly. The honest feedback will be more valuable than any report.",
            expected_outcome="Businesses that act on churn feedback reduce churn by 25–40% within 60 days.",
            effort="moderate",
        ))

    return actions
