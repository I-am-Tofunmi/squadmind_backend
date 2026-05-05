"""
SquadMind – AI Explanation Service (Master Orchestrator)
Single entry point for all explanation generation.
Routes requests to the correct specialist explainer, then optionally
enriches with OpenAI. Returns frontend-safe ExplanationResult dicts.

Usage:
    from app.services.ai_explanation_service import AIExplanationService
    service = AIExplanationService(db)
    result = await service.explain_fraud_alert(fraud_log_id="...")
"""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Dict, List, Optional
from uuid import UUID

from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.logging import get_logger
from app.models.forecast import Forecast
from app.models.fraud_log import FraudLog
from app.models.transaction import Transaction
from app.models.user import User
from app.services.explanations.customer_explainer import explain_customer_behavior
from app.services.explanations.forecast_explainer import explain_forecast
from app.services.explanations.fraud_explainer import explain_fraud
from app.services.explanations.health_explainer import explain_health_score
from app.services.explanations.openai_enhancer import enhance_explanation
from app.services.explanations.revenue_explainer import explain_revenue
from app.services.explanations.templates import ExplanationResult

log = get_logger(__name__)


class AIExplanationService:
    """
    Orchestrates explanation generation across all financial insight types.
    Every public method returns a dict safe to send directly in an API response.
    """

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    # ── 1. Fraud Alert Explanation ────────────────────────────────────────────
    async def explain_fraud_alert(
        self,
        fraud_log_id: UUID,
        use_ai: bool = True,
    ) -> Dict[str, Any]:
        """
        Explain a specific fraud log entry.
        Fetches context from DB and generates a full CFO-quality narrative.
        """
        # Fetch fraud log with transaction
        result = await self.db.execute(
            select(FraudLog).where(FraudLog.id == fraud_log_id)
        )
        fraud_log = result.scalar_one_or_none()
        if not fraud_log:
            return _not_found_response("fraud_log", fraud_log_id)

        # Fetch the associated transaction
        tx = None
        if fraud_log.transaction_id:
            tx_result = await self.db.execute(
                select(Transaction).where(Transaction.id == fraud_log.transaction_id)
            )
            tx = tx_result.scalar_one_or_none()

        # Build explanation inputs
        tx_amount = float(tx.amount) if tx else 0.0
        tx_hour = tx.transaction_date.hour if tx else None
        rules = fraud_log.rules_triggered or []

        # Extract velocity context from rules metadata if available
        velocity_count = None
        velocity_window = settings.FRAUD_VELOCITY_WINDOW_MINUTES
        if "velocity_breach" in rules and tx:
            # Count actual transactions in the window
            if tx.customer_id:
                from datetime import timedelta
                window_start = tx.transaction_date - timedelta(minutes=velocity_window)
                count_q = await self.db.execute(
                    select(func.count()).where(
                        and_(
                            Transaction.user_id == fraud_log.user_id,
                            Transaction.customer_id == tx.customer_id,
                            Transaction.transaction_date >= window_start,
                            Transaction.transaction_date <= tx.transaction_date,
                        )
                    )
                )
                velocity_count = count_q.scalar() or 2

        # Check if this is a new customer
        is_new_customer = False
        if tx and tx.customer_id:
            prev_q = await self.db.execute(
                select(func.count()).where(
                    and_(
                        Transaction.user_id == fraud_log.user_id,
                        Transaction.customer_id == tx.customer_id,
                        Transaction.id != tx.id,
                    )
                )
            )
            is_new_customer = (prev_q.scalar() or 0) == 0

        explanation = explain_fraud(
            transaction_amount=tx_amount,
            risk_score=float(fraud_log.risk_score),
            risk_level=fraud_log.risk_level,
            rules_triggered=rules,
            transaction_hour=tx_hour,
            velocity_count=velocity_count,
            velocity_window_minutes=velocity_window if velocity_count else None,
            customer_name=tx.customer_name if tx else None,
            customer_is_new=is_new_customer,
            large_tx_threshold=settings.FRAUD_LARGE_TRANSACTION_THRESHOLD,
        )

        if use_ai and settings.OPENAI_API_KEY:
            explanation = await enhance_explanation(
                explanation,
                force_enhance=(fraud_log.risk_level == "critical"),
            )

        log.info("fraud_explanation_generated", fraud_log_id=str(fraud_log_id), ai=explanation.ai_enhanced)
        return explanation.to_dict()

    # ── 2. Revenue Explanation ────────────────────────────────────────────────
    async def explain_revenue_change(
        self,
        user_id: UUID,
        period: str = "last_30_days",
        use_ai: bool = True,
    ) -> Dict[str, Any]:
        """Explain the user's revenue performance for the given period."""
        from datetime import timedelta

        now = datetime.now(tz=timezone.utc)
        if period == "last_7_days":
            start, prev_start = now - timedelta(days=7), now - timedelta(days=14)
        elif period == "this_month":
            start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            prev_start = (start - timedelta(days=1)).replace(day=1)
        else:
            start, prev_start = now - timedelta(days=30), now - timedelta(days=60)

        # Current period
        curr_q = await self.db.execute(
            select(
                func.coalesce(func.sum(Transaction.amount), 0).label("revenue"),
                func.count().label("count"),
                func.coalesce(func.avg(Transaction.amount), 0).label("avg"),
            ).where(and_(
                Transaction.user_id == user_id,
                Transaction.transaction_type == "credit",
                Transaction.status == "success",
                Transaction.transaction_date >= start,
            ))
        )
        curr = curr_q.one()

        # Previous period
        prev_q = await self.db.execute(
            select(func.coalesce(func.sum(Transaction.amount), 0)).where(and_(
                Transaction.user_id == user_id,
                Transaction.transaction_type == "credit",
                Transaction.status == "success",
                Transaction.transaction_date >= prev_start,
                Transaction.transaction_date < start,
            ))
        )
        prev_revenue = float(prev_q.scalar() or 0)
        curr_revenue = float(curr.revenue)
        change_pct = ((curr_revenue - prev_revenue) / prev_revenue * 100) if prev_revenue > 0 else 0.0

        # Best/worst day
        daily_q = await self.db.execute(
            select(
                func.date_trunc("day", Transaction.transaction_date).label("day"),
                func.sum(Transaction.amount).label("amount"),
                func.count().label("count"),
            ).where(and_(
                Transaction.user_id == user_id,
                Transaction.transaction_type == "credit",
                Transaction.status == "success",
                Transaction.transaction_date >= start,
            )).group_by("day").order_by("day")
        )
        daily_rows = daily_q.all()

        worst_day = None
        best_day = None
        if daily_rows:
            worst = min(daily_rows, key=lambda r: r.amount)
            best = max(daily_rows, key=lambda r: r.amount)
            worst_day = {"date": worst.day.strftime("%A %b %d"), "amount": float(worst.amount), "count": worst.count}
            best_day = {"date": best.day.strftime("%A %b %d"), "amount": float(best.amount), "count": best.count}

        # Pending/failed count
        pending_q = await self.db.execute(
            select(func.count()).where(and_(
                Transaction.user_id == user_id,
                Transaction.status.in_(["pending", "failed"]),
                Transaction.transaction_date >= start,
            ))
        )
        payment_delays = pending_q.scalar() or 0

        explanation = explain_revenue(
            current_revenue=curr_revenue,
            previous_revenue=prev_revenue,
            change_percent=change_pct,
            period_label=period.replace("_", " "),
            total_transactions=curr.count,
            avg_transaction_value=float(curr.avg),
            worst_day=worst_day,
            best_day=best_day,
            payment_delays=payment_delays or None,
            seasonal_month=now.strftime("%B").lower(),
        )

        if use_ai:
            explanation = await enhance_explanation(explanation)

        return explanation.to_dict()

    # ── 3. Health Score Explanation ───────────────────────────────────────────
    async def explain_health_score_change(
        self,
        user_id: UUID,
        current_score: int,
        grade: str,
        label: str,
        breakdown: Dict[str, int],
        previous_score: Optional[int] = None,
        use_ai: bool = True,
    ) -> Dict[str, Any]:
        """Explain the financial health score and how to improve it."""
        # Get business name
        user_q = await self.db.execute(select(User).where(User.id == user_id))
        user = user_q.scalar_one_or_none()
        business_name = user.business_name if user else None

        explanation = explain_health_score(
            current_score=current_score,
            grade=grade,
            label=label,
            breakdown=breakdown,
            previous_score=previous_score,
            business_name=business_name,
        )

        if use_ai:
            explanation = await enhance_explanation(explanation)

        return explanation.to_dict()

    # ── 4. Forecast Explanation ───────────────────────────────────────────────
    async def explain_forecast_result(
        self,
        forecast_id: UUID,
        use_ai: bool = True,
    ) -> Dict[str, Any]:
        """Explain a specific forecast result."""
        result = await self.db.execute(select(Forecast).where(Forecast.id == forecast_id))
        forecast = result.scalar_one_or_none()
        if not forecast:
            return _not_found_response("forecast", forecast_id)

        # Calculate daily average from the daily projections
        projections = forecast.daily_projections or {}
        if projections:
            revenues = [v["revenue"] for v in projections.values() if isinstance(v, dict)]
            daily_avg = sum(revenues) / len(revenues) if revenues else float(forecast.projected_revenue) / max(forecast.forecast_period_days, 1)
            # Detect trend direction
            if len(revenues) >= 2:
                trend = "up" if revenues[-1] > revenues[0] else ("down" if revenues[-1] < revenues[0] else "flat")
            else:
                trend = "flat"
        else:
            daily_avg = float(forecast.projected_revenue) / max(forecast.forecast_period_days, 1)
            trend = "flat"

        explanation = explain_forecast(
            projected_revenue=float(forecast.projected_revenue),
            projected_net=float(forecast.projected_net),
            confidence_score=float(forecast.confidence_score),
            algorithm=forecast.algorithm,
            days_ahead=forecast.forecast_period_days,
            lookback_days=forecast.lookback_days,
            transaction_count_used=forecast.transaction_count_used,
            current_daily_avg=daily_avg,
            trend_direction=trend,
        )

        if use_ai:
            explanation = await enhance_explanation(explanation)

        return explanation.to_dict()

    # ── 5. Customer Behaviour Explanation ─────────────────────────────────────
    async def explain_customer_patterns(
        self,
        user_id: UUID,
        period_days: int = 30,
        use_ai: bool = True,
    ) -> Dict[str, Any]:
        """Explain customer behaviour patterns for the period."""
        from datetime import timedelta
        now = datetime.now(tz=timezone.utc)
        start = now - timedelta(days=period_days)
        prev_start = start - timedelta(days=period_days)

        # Unique customers this period
        unique_q = await self.db.execute(
            select(func.count(func.distinct(Transaction.customer_id))).where(
                and_(Transaction.user_id == user_id, Transaction.transaction_date >= start)
            )
        )
        unique_customers = unique_q.scalar() or 0

        # Customers from previous period (to detect churn)
        prev_customers_q = await self.db.execute(
            select(Transaction.customer_id.distinct()).where(
                and_(
                    Transaction.user_id == user_id,
                    Transaction.transaction_date >= prev_start,
                    Transaction.transaction_date < start,
                    Transaction.customer_id.isnot(None),
                )
            )
        )
        prev_customer_ids = {row[0] for row in prev_customers_q.all()}

        curr_customers_q = await self.db.execute(
            select(Transaction.customer_id.distinct()).where(
                and_(
                    Transaction.user_id == user_id,
                    Transaction.transaction_date >= start,
                    Transaction.customer_id.isnot(None),
                )
            )
        )
        curr_customer_ids = {row[0] for row in curr_customers_q.all()}

        churned = len(prev_customer_ids - curr_customer_ids)
        new_customers = len(curr_customer_ids - prev_customer_ids)
        returning = len(curr_customer_ids & prev_customer_ids)
        returning_rate = (returning / max(unique_customers, 1)) * 100

        # Top customer concentration
        top_q = await self.db.execute(
            select(
                Transaction.customer_id,
                Transaction.customer_name,
                func.sum(Transaction.amount).label("spend"),
                func.count().label("tx_count"),
            ).where(and_(Transaction.user_id == user_id, Transaction.transaction_date >= start))
            .group_by(Transaction.customer_id, Transaction.customer_name)
            .order_by(func.sum(Transaction.amount).desc())
            .limit(3)
        )
        top_customers = top_q.all()

        total_revenue_q = await self.db.execute(
            select(func.coalesce(func.sum(Transaction.amount), 0)).where(
                and_(Transaction.user_id == user_id, Transaction.transaction_date >= start)
            )
        )
        total_revenue = float(total_revenue_q.scalar() or 1)

        top_3_revenue = sum(float(r.spend) for r in top_customers)
        concentration_pct = (top_3_revenue / total_revenue * 100) if total_revenue > 0 else 0

        mvc = None
        if top_customers:
            mvc = {
                "name": top_customers[0].customer_name or "Top Customer",
                "spend": float(top_customers[0].spend),
                "tx_count": top_customers[0].tx_count,
            }

        explanation = explain_customer_behavior(
            unique_customers=unique_customers,
            returning_customer_rate=returning_rate,
            top_customer_revenue_share=concentration_pct,
            churned_customers=churned or None,
            new_customers=new_customers,
            most_valuable_customer=mvc,
        )

        if use_ai:
            explanation = await enhance_explanation(explanation)

        return explanation.to_dict()

    # ── 6. On-demand plain-language query (GPT-powered) ───────────────────────
    async def answer_financial_question(
        self,
        user_id: UUID,
        question: str,
        language: str = "english",
    ) -> Dict[str, Any]:
        """
        Answer any financial question about the user's business in plain English or Pidgin.
        This is the 'ask your CFO' feature — powered entirely by GPT.
        """
        if not settings.OPENAI_API_KEY:
            return {
                "answer": "AI Q&A requires an OpenAI API key. Configure OPENAI_API_KEY in your settings.",
                "pidgin_answer": "AI Q&A needs OpenAI API key — configure am for your settings.",
                "ai_enhanced": False,
            }

        # Fetch recent context
        from datetime import timedelta
        now = datetime.now(tz=timezone.utc)
        start = now - timedelta(days=30)

        metrics_q = await self.db.execute(
            select(
                func.coalesce(func.sum(Transaction.amount), 0).label("revenue"),
                func.count().label("tx_count"),
                func.coalesce(func.avg(Transaction.amount), 0).label("avg"),
            ).where(and_(Transaction.user_id == user_id, Transaction.transaction_date >= start))
        )
        metrics = metrics_q.one()

        user_q = await self.db.execute(select(User).where(User.id == user_id))
        user = user_q.scalar_one_or_none()

        context = {
            "business_name": user.business_name if user else "This Business",
            "industry": user.industry if user else "unknown",
            "last_30_days_revenue": float(metrics.revenue),
            "last_30_days_transactions": metrics.tx_count,
            "avg_transaction_value": float(metrics.avg),
        }

        try:
            import openai
            client = openai.AsyncOpenAI(api_key=settings.OPENAI_API_KEY)

            lang_instruction = "Answer in natural Nigerian Pidgin English." if language == "pidgin" else "Answer in clear, warm, plain English."
            also_pidgin = "Also include a 'pidgin_answer' field in natural Nigerian Pidgin." if language == "english" else ""

            prompt = f"""You are SquadMind's AI CFO advisor for {context['business_name']}, a Nigerian SME.

Business context:
- Industry: {context['industry']}
- Last 30 days revenue: ₦{context['last_30_days_revenue']:,.0f}
- Last 30 days transactions: {context['last_30_days_transactions']:,}
- Average transaction value: ₦{context['avg_transaction_value']:,.0f}

Owner's question: {question}

{lang_instruction}
Be specific, actionable, and use Nigerian business context where relevant.
{also_pidgin}

Return JSON: {{"answer": "...", "pidgin_answer": "...", "confidence": "high|medium|low"}}"""

            response = await client.chat.completions.create(
                model=settings.OPENAI_MODEL,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=400,
                temperature=0.7,
                response_format={"type": "json_object"},
            )
            result = json_parse_safe(response.choices[0].message.content)
            result["ai_enhanced"] = True
            result["model"] = settings.OPENAI_MODEL
            return result

        except Exception as e:
            log.error("financial_qa_failed", error=str(e))
            return {
                "answer": "I couldn't process that question right now. Please try again.",
                "pidgin_answer": "E no work now — try again later.",
                "ai_enhanced": False,
                "error": str(e),
            }


def _not_found_response(resource: str, id: Any) -> Dict:
    return {
        "headline": f"{resource.replace('_', ' ').title()} not found",
        "summary": f"Could not find {resource} with ID {id}.",
        "detail": "",
        "pidgin": {"summary": f"We no see this {resource} — ID: {id}", "detail": ""},
        "severity": "low",
        "explanation_type": resource,
        "key_factors": [],
        "actions": [],
        "metrics_referenced": {},
        "ai_enhanced": False,
    }


def json_parse_safe(raw: str) -> Dict:
    """Parse JSON, stripping markdown fences if present."""
    import json
    clean = raw.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
    return json.loads(clean)
