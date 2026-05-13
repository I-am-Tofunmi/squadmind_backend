"""
SquadMind – Dashboard Router  /api/v1/dashboard
Single-endpoint payload powering the Revenue Intelligence Dashboard.
Returns KPIs, health score, trends, fraud summary, alerts, and AI insight.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Optional
from collections import defaultdict

from fastapi import APIRouter, Query
from sqlalchemy import func, select, case, and_

from app.api.deps import CurrentUser, DB, Redis
from app.core.logging import get_logger
from app.db.redis import cache
from app.models.transaction import Transaction
from app.models.fraud_log import FraudLog
from app.models.alert import Alert
from app.schemas.dashboard import (
    AlertResponse,
    AlertSummary,
    DashboardResponse,
    FraudSummary,
    HealthScore,
    MetricCard,
    RevenueDataPoint,
    TopCustomer,
)
from app.services.forecast_service import ForecastService
from app.utils.formatters import format_naira, format_percent
from app.utils.responses import success_response

log = get_logger(__name__)
router = APIRouter(prefix="/dashboard", tags=["Dashboard"])


@router.get(
    "/",
    response_model=dict,
    summary="Revenue Intelligence Dashboard",
    description="Returns everything the main dashboard needs in a single request.",
)
async def get_dashboard(
    current_user: CurrentUser,
    db: DB,
    period: str = Query("last_30_days", enum=["last_7_days", "last_30_days", "this_month"]),
) -> dict:
    cache_key = f"dashboard:{current_user.id}:{period}"

    cached = await cache.get(cache_key)
    if cached:
        log.debug("dashboard_cache_hit", user_id=str(current_user.id), period=period)
        return success_response(data=cached)

    now = datetime.now(tz=timezone.utc)
    if period == "last_7_days":
        start_date = now - timedelta(days=7)
        prev_start = start_date - timedelta(days=7)
    elif period == "this_month":
        start_date = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        prev_start = (start_date - timedelta(days=1)).replace(day=1)
    else:
        start_date = now - timedelta(days=30)
        prev_start = start_date - timedelta(days=30)

    tx_count_result = await db.execute(
        select(func.count()).where(Transaction.user_id == current_user.id)
    )
    total_tx_count = tx_count_result.scalar() or 0
    is_mock = total_tx_count == 0 or not current_user.has_squad_credentials

    if is_mock:
        dashboard_data = _build_mock_dashboard(current_user, period, now)
    else:
        dashboard_data = await _build_real_dashboard(
            db, current_user, period, start_date, prev_start, now
        )

    await cache.set(cache_key, dashboard_data, ttl_seconds=300)

    return success_response(data=dashboard_data)


def _calculate_best_sales_day(revenue_trend: list) -> str:
    """
    Calculate the best sales day from revenue trend data.
    Returns the day of the week with the highest average revenue.
    """
    day_revenue = defaultdict(list)
    day_names = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]

    for point in revenue_trend:
        try:
            date = datetime.strptime(point["date"], "%Y-%m-%d")
            day_name = day_names[date.weekday()]
            day_revenue[day_name].append(point["revenue"])
        except Exception:
            continue

    if not day_revenue:
        return "Friday"

    best_day = max(day_revenue, key=lambda d: sum(day_revenue[d]) / len(day_revenue[d]))
    return best_day


async def _build_real_dashboard(
    db, user, period: str, start_date: datetime, prev_start: datetime, now: datetime
) -> dict:
    """Build dashboard from actual transaction data."""
    uid = user.id

    revenue_q = await db.execute(
        select(
            func.coalesce(func.sum(Transaction.amount), 0).label("total"),
            func.count().label("count"),
        ).where(
            and_(
                Transaction.user_id == uid,
                Transaction.transaction_type == "credit",
                Transaction.status == "success",
                Transaction.transaction_date >= start_date,
            )
        )
    )
    revenue_row = revenue_q.one()
    total_revenue = Decimal(str(revenue_row.total))
    total_tx = revenue_row.count

    prev_revenue_q = await db.execute(
        select(func.coalesce(func.sum(Transaction.amount), 0)).where(
            and_(
                Transaction.user_id == uid,
                Transaction.transaction_type == "credit",
                Transaction.status == "success",
                Transaction.transaction_date >= prev_start,
                Transaction.transaction_date < start_date,
            )
        )
    )
    prev_revenue = Decimal(str(prev_revenue_q.scalar() or 0))
    revenue_change = (
        float(((total_revenue - prev_revenue) / prev_revenue * 100)) if prev_revenue else 0.0
    )

    avg_tx_value = total_revenue / total_tx if total_tx else Decimal("0")

    unique_customers_q = await db.execute(
        select(func.count(func.distinct(Transaction.customer_id))).where(
            and_(Transaction.user_id == uid, Transaction.transaction_date >= start_date)
        )
    )
    unique_customers = unique_customers_q.scalar() or 0

    fraud_q = await db.execute(
        select(
            func.count().label("count"),
            func.coalesce(func.sum(Transaction.amount), 0).label("amount"),
        ).where(
            and_(
                Transaction.user_id == uid,
                Transaction.is_flagged_fraud == True,  # noqa: E712
                Transaction.transaction_date >= start_date,
            )
        )
    )
    fraud_row = fraud_q.one()
    flagged_count = fraud_row.count
    flagged_amount = Decimal(str(fraud_row.amount))
    fraud_rate = (flagged_count / total_tx * 100) if total_tx else 0.0

    open_fraud_q = await db.execute(
        select(func.count()).where(
            and_(FraudLog.user_id == uid, FraudLog.status == "open")
        )
    )
    open_cases = open_fraud_q.scalar() or 0

    trend_q = await db.execute(
        select(
            func.date_trunc("day", Transaction.transaction_date).label("day"),
            func.sum(Transaction.amount).label("revenue"),
            func.count().label("count"),
        ).where(
            and_(
                Transaction.user_id == uid,
                Transaction.transaction_type == "credit",
                Transaction.status == "success",
                Transaction.transaction_date >= start_date,
            )
        ).group_by("day").order_by("day")
    )
    revenue_trend = [
        {"date": row.day.strftime("%Y-%m-%d"), "revenue": float(row.revenue), "transactions": row.count}
        for row in trend_q.all()
    ]

    # Calculate best sales day from real trend data
    best_sales_day = _calculate_best_sales_day(revenue_trend)

    score = _calculate_health_score(
        revenue_change=revenue_change,
        fraud_rate=fraud_rate,
        total_tx=total_tx,
    )

    top_cust_q = await db.execute(
        select(
            Transaction.customer_id,
            Transaction.customer_name,
            func.sum(Transaction.amount).label("total_spend"),
            func.count().label("tx_count"),
            func.max(Transaction.transaction_date).label("last_tx"),
        ).where(
            and_(Transaction.user_id == uid, Transaction.transaction_date >= start_date)
        ).group_by(Transaction.customer_id, Transaction.customer_name)
        .order_by(func.sum(Transaction.amount).desc())
        .limit(5)
    )
    top_customers = [
        {
            "customer_id": row.customer_id,
            "customer_name": row.customer_name or "Unknown",
            "total_spend": float(row.total_spend),
            "transaction_count": row.tx_count,
            "last_transaction_date": row.last_tx.isoformat() if row.last_tx else None,
        }
        for row in top_cust_q.all()
    ]

    alerts_q = await db.execute(
        select(Alert)
        .where(Alert.user_id == uid)
        .order_by(Alert.created_at.desc())
        .limit(5)
    )
    recent_alerts = [
        {
            "id": str(a.id),
            "type": a.alert_type,
            "title": a.title,
            "channel": a.channel,
            "status": a.status,
            "created_at": a.created_at.isoformat(),
        }
        for a in alerts_q.scalars().all()
    ]

    unread_alerts_q = await db.execute(
        select(func.count()).where(and_(Alert.user_id == uid, Alert.status == "pending"))
    )
    unread_count = unread_alerts_q.scalar() or 0

    return {
        "user_id": str(user.id),
        "business_name": user.business_name,
        "period": period,
        "generated_at": now.isoformat(),
        "has_squad_credentials": user.has_squad_credentials,
        "squad_last_synced_at": (
            user.squad_last_synced_at.isoformat() if user.squad_last_synced_at else None
        ),
        "best_sales_day": best_sales_day,
        "metrics": [
            {
                "label": "Total Revenue",
                "value": format_naira(total_revenue),
                "raw_value": float(total_revenue),
                "change_percent": round(revenue_change, 2),
                "trend": "up" if revenue_change > 0 else ("down" if revenue_change < 0 else "flat"),
            },
            {
                "label": "Total Transactions",
                "value": f"{total_tx:,}",
                "raw_value": total_tx,
                "change_percent": 0.0,
                "trend": "flat",
            },
            {
                "label": "Avg Transaction Value",
                "value": format_naira(avg_tx_value),
                "raw_value": float(avg_tx_value),
                "change_percent": 0.0,
                "trend": "flat",
            },
            {
                "label": "Unique Customers",
                "value": f"{unique_customers:,}",
                "raw_value": unique_customers,
                "change_percent": 0.0,
                "trend": "flat",
            },
        ],
        "health_score": score,
        "revenue_trend": revenue_trend,
        "top_customers": top_customers,
        "unique_customers": unique_customers,
        "returning_customer_rate": 0.0,
        "fraud_summary": {
            "flagged_count": flagged_count,
            "flagged_amount": float(flagged_amount),
            "fraud_rate_percent": round(fraud_rate, 2),
            "open_cases": open_cases,
            "recent_flags": [],
        },
        "alert_summary": {
            "unread_count": unread_count,
            "recent": recent_alerts,
        },
        "ai_insight": _generate_ai_insight(total_revenue, revenue_change, total_tx),
        "ai_insight_pidgin": _generate_pidgin_insight(total_revenue, revenue_change, total_tx),
        "is_mock_data": False,
    }


def _calculate_health_score(
    revenue_change: float, fraud_rate: float, total_tx: int
) -> dict:
    revenue_score = min(100, max(0, 50 + revenue_change))
    fraud_score = max(0, 100 - (fraud_rate * 10))
    volume_score = min(100, total_tx * 2)

    overall = int((revenue_score * 0.5) + (fraud_score * 0.3) + (volume_score * 0.2))
    overall = max(0, min(100, overall))

    if overall >= 80:
        grade, label = "A", "Excellent"
    elif overall >= 65:
        grade, label = "B", "Good"
    elif overall >= 50:
        grade, label = "C", "Fair"
    elif overall >= 35:
        grade, label = "D", "Poor"
    else:
        grade, label = "F", "Critical"

    return {
        "score": overall,
        "grade": grade,
        "label": label,
        "breakdown": {
            "revenue_growth": int(revenue_score),
            "fraud_safety": int(fraud_score),
            "transaction_volume": int(volume_score),
        },
        "ai_summary": f"Your business scores {overall}/100 — {label} financial health.",
        "pidgin_summary": _health_pidgin(overall, label),
    }


def _health_pidgin(score: int, label: str) -> str:
    if score >= 80:
        return f"Bros, your business dey fire! Score na {score}/100 🔥 Money dey flow, fraud no dey disturb you."
    elif score >= 65:
        return f"Your business dey do well, e reach {score}/100. Small small improvement go make am excellent!"
    elif score >= 50:
        return f"E dey manage for {score}/100. You need to hustle more — revenue consistency need work."
    else:
        return f"Omo, score na {score}/100 — e no too good. Act fast, check your cash flow and fraud alerts!"


def _generate_ai_insight(revenue: Decimal, change: float, tx_count: int) -> str:
    direction = "increased" if change > 0 else "decreased"
    return (
        f"Your revenue has {direction} by {abs(change):.1f}% this period, "
        f"with {tx_count:,} transactions totalling {format_naira(revenue)}. "
        f"{'Keep up the momentum!' if change > 0 else 'Review your top customer engagement to reverse the trend.'}"
    )


def _generate_pidgin_insight(revenue: Decimal, change: float, tx_count: int) -> str:
    direction = "up" if change > 0 else "down"
    return (
        f"Your revenue don go {direction} by {abs(change):.1f}% this period — "
        f"total na {format_naira(revenue)} from {tx_count:,} transactions. "
        f"{'You dey show! Carry go 💪' if change > 0 else 'Abeg check your top customers, make you boost am up!'}"
    )


def _build_mock_dashboard(user, period: str, now: datetime) -> dict:
    """
    Return rich mock data for users without Squad credentials yet.
    """
    mock_trend = [
        {"date": (now - timedelta(days=i)).strftime("%Y-%m-%d"), "revenue": 140000 + (i * 3000), "transactions": 40 + i}
        for i in range(29, -1, -1)
    ]

    best_sales_day = _calculate_best_sales_day(mock_trend)

    return {
        "user_id": str(user.id),
        "business_name": user.business_name,
        "period": period,
        "generated_at": now.isoformat(),
        "has_squad_credentials": False,
        "squad_last_synced_at": None,
        "best_sales_day": best_sales_day,
        "metrics": [
            {"label": "Total Revenue", "value": "₦4,200,000", "raw_value": 4200000, "change_percent": 12.5, "trend": "up"},
            {"label": "Total Transactions", "value": "1,247", "raw_value": 1247, "change_percent": 8.3, "trend": "up"},
            {"label": "Avg Transaction Value", "value": "₦3,368", "raw_value": 3368, "change_percent": 3.8, "trend": "up"},
            {"label": "Unique Customers", "value": "342", "raw_value": 342, "change_percent": 15.2, "trend": "up"},
        ],
        "health_score": {
            "score": 78,
            "grade": "B",
            "label": "Good",
            "breakdown": {"revenue_growth": 82, "fraud_safety": 91, "transaction_volume": 65},
            "ai_summary": "Your business scores 78/100 — Good financial health.",
            "pidgin_summary": "Your business dey do well, e reach 78/100. Small small improvement go make am excellent!",
        },
        "revenue_trend": mock_trend,
        "top_customers": [
            {"customer_id": "CUST001", "customer_name": "Adebayo Stores", "total_spend": 450000, "transaction_count": 23, "last_transaction_date": (now - timedelta(days=1)).isoformat()},
            {"customer_id": "CUST002", "customer_name": "Ngozi Enterprises", "total_spend": 320000, "transaction_count": 18, "last_transaction_date": (now - timedelta(days=2)).isoformat()},
            {"customer_id": "CUST003", "customer_name": "Emeka Trading Co", "total_spend": 280000, "transaction_count": 15, "last_transaction_date": (now - timedelta(days=3)).isoformat()},
        ],
        "unique_customers": 342,
        "returning_customer_rate": 67.4,
        "fraud_summary": {"flagged_count": 3, "flagged_amount": 45000, "fraud_rate_percent": 0.24, "open_cases": 2, "recent_flags": []},
        "alert_summary": {"unread_count": 2, "recent": []},
        "ai_insight": "Your business is performing well with consistent revenue growth of 12.5%. Your top 3 customers account for 25% of total revenue — consider a loyalty program.",
        "ai_insight_pidgin": "Your business dey do well! Revenue don go up 12.5% 🚀 Your top customers dey carry the load — reward dem with something special!",
        "is_mock_data": True,
    }
