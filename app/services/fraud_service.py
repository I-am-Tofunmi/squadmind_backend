"""
SquadMind – Fraud Detection Service
Rule-based engine with a composite risk score.
Phase 1 rules → ready to plug in ML in Phase 2 without breaking the interface.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Any, Dict, List, Optional
from uuid import UUID

from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.logging import get_logger
from app.models.fraud_log import FraudLog
from app.models.transaction import Transaction

log = get_logger(__name__)


@dataclass
class FraudCheckResult:
    """Result of running all fraud rules against a transaction."""
    is_fraud: bool
    risk_score: float          # 0–100
    risk_level: str            # low | medium | high | critical
    rules_triggered: List[str] = field(default_factory=list)
    explanation: str = ""


class FraudDetectionService:
    """
    Composite rule-based fraud detection.
    Each rule returns (triggered: bool, score_contribution: float, label: str).
    Final score = sum of contributions, capped at 100.
    """

    RISK_THRESHOLDS = {
        "critical": 75,
        "high": 50,
        "medium": 25,
        "low": 0,
    }

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def analyze_transaction(
        self,
        tx: Transaction,
        user_id: UUID,
    ) -> Dict[str, Any]:
        """
        Run all fraud rules. Persist a FraudLog if risk >= medium.
        Returns a dict suitable for API response.
        """
        result = await self._run_rules(tx, user_id)

        # Persist fraud log if risk is non-trivial
        if result.risk_score >= self.RISK_THRESHOLDS["medium"]:
            await self._persist_fraud_log(tx, user_id, result)

            # Update the transaction's fraud flag
            tx.is_flagged_fraud = result.risk_score >= self.RISK_THRESHOLDS["high"]
            tx.fraud_score = Decimal(str(round(result.risk_score, 2)))

        log.info(
            "fraud_analysis_complete",
            transaction_id=str(tx.id),
            risk_score=result.risk_score,
            risk_level=result.risk_level,
            rules=result.rules_triggered,
        )

        return {
            "transaction_id": str(tx.id),
            "is_fraud": result.is_fraud,
            "risk_score": result.risk_score,
            "risk_level": result.risk_level,
            "rules_triggered": result.rules_triggered,
            "explanation": result.explanation,
        }

    async def _run_rules(self, tx: Transaction, user_id: UUID) -> FraudCheckResult:
        """Execute all rules and aggregate scores."""
        rules_triggered: List[str] = []
        total_score = 0.0

        # ── Rule 1: Large Transaction Amount ──────────────────────────────────
        if float(tx.amount) >= settings.FRAUD_LARGE_TRANSACTION_THRESHOLD:
            contribution = min(30.0, float(tx.amount) / settings.FRAUD_LARGE_TRANSACTION_THRESHOLD * 15)
            total_score += contribution
            rules_triggered.append("large_transaction_amount")

        # ── Rule 2: Night-time Transaction ────────────────────────────────────
        tx_hour = tx.transaction_date.hour
        night_start = settings.FRAUD_NIGHT_HOUR_START
        night_end = settings.FRAUD_NIGHT_HOUR_END
        is_night = tx_hour >= night_start or tx_hour <= night_end
        if is_night:
            total_score += 15.0
            rules_triggered.append("night_transaction")

        # ── Rule 3: Transaction Velocity Breach ───────────────────────────────
        velocity_exceeded = await self._check_velocity(user_id, tx.customer_id, tx.transaction_date)
        if velocity_exceeded:
            total_score += 35.0
            rules_triggered.append("velocity_breach")

        # ── Rule 4: Round Number Amount (money laundering signal) ─────────────
        amount_val = float(tx.amount)
        if amount_val > 10000 and amount_val % 10000 == 0:
            total_score += 10.0
            rules_triggered.append("round_number_amount")

        # ── Rule 5: Duplicate Transaction (same amount + customer in 5 min) ───
        is_duplicate = await self._check_duplicate(tx, user_id)
        if is_duplicate:
            total_score += 40.0
            rules_triggered.append("potential_duplicate")

        # ── Rule 6: First Transaction (new customer, high amount) ─────────────
        if tx.customer_id:
            first_tx = await self._check_first_transaction(tx, user_id)
            if first_tx and float(tx.amount) >= 50000:
                total_score += 20.0
                rules_triggered.append("high_value_first_transaction")

        # Cap at 100
        total_score = min(100.0, total_score)

        # Determine level
        risk_level = "low"
        for level, threshold in self.RISK_THRESHOLDS.items():
            if total_score >= threshold:
                risk_level = level
                break

        is_fraud = total_score >= self.RISK_THRESHOLDS["high"]
        explanation = self._generate_explanation(rules_triggered, total_score, tx)

        return FraudCheckResult(
            is_fraud=is_fraud,
            risk_score=round(total_score, 2),
            risk_level=risk_level,
            rules_triggered=rules_triggered,
            explanation=explanation,
        )

    async def _check_velocity(
        self, user_id: UUID, customer_id: Optional[str], tx_date: datetime
    ) -> bool:
        """Check if customer exceeded transaction count in velocity window."""
        if not customer_id:
            return False

        window_start = tx_date - timedelta(minutes=settings.FRAUD_VELOCITY_WINDOW_MINUTES)
        result = await self.db.execute(
            select(func.count()).where(
                and_(
                    Transaction.user_id == user_id,
                    Transaction.customer_id == customer_id,
                    Transaction.transaction_date >= window_start,
                    Transaction.transaction_date <= tx_date,
                )
            )
        )
        count = result.scalar() or 0
        return count >= settings.FRAUD_VELOCITY_MAX_COUNT

    async def _check_duplicate(self, tx: Transaction, user_id: UUID) -> bool:
        """Detect potential duplicate: same customer, same amount, within 5 min."""
        if not tx.customer_id:
            return False

        window_start = tx.transaction_date - timedelta(minutes=5)
        result = await self.db.execute(
            select(func.count()).where(
                and_(
                    Transaction.user_id == user_id,
                    Transaction.customer_id == tx.customer_id,
                    Transaction.amount == tx.amount,
                    Transaction.transaction_date >= window_start,
                    Transaction.transaction_date < tx.transaction_date,
                    Transaction.id != tx.id,
                )
            )
        )
        return (result.scalar() or 0) > 0

    async def _check_first_transaction(self, tx: Transaction, user_id: UUID) -> bool:
        """Check if this is the customer's first-ever transaction."""
        result = await self.db.execute(
            select(func.count()).where(
                and_(
                    Transaction.user_id == user_id,
                    Transaction.customer_id == tx.customer_id,
                    Transaction.id != tx.id,
                )
            )
        )
        return (result.scalar() or 0) == 0

    def _generate_explanation(
        self, rules: List[str], score: float, tx: Transaction
    ) -> str:
        if not rules:
            return f"No fraud signals detected. Risk score: {score:.1f}/100."

        descriptions = {
            "large_transaction_amount": f"Transaction amount (₦{float(tx.amount):,.2f}) exceeds the large-transaction threshold.",
            "night_transaction": "Transaction occurred during unusual hours (11 PM – 5 AM).",
            "velocity_breach": f"Customer exceeded {settings.FRAUD_VELOCITY_MAX_COUNT} transactions within {settings.FRAUD_VELOCITY_WINDOW_MINUTES} minutes.",
            "round_number_amount": "Transaction amount is a suspiciously round number — common in structuring schemes.",
            "potential_duplicate": "A transaction with the same amount and customer was recorded within the last 5 minutes.",
            "high_value_first_transaction": "This is the customer's first transaction and the amount is unusually high.",
        }

        parts = [descriptions.get(r, r) for r in rules]
        return f"Risk score {score:.1f}/100. Flags: {'; '.join(parts)}"

    async def _persist_fraud_log(
        self, tx: Transaction, user_id: UUID, result: FraudCheckResult
    ) -> FraudLog:
        log_entry = FraudLog(
            user_id=user_id,
            transaction_id=tx.id,
            rules_triggered=result.rules_triggered,
            risk_score=Decimal(str(result.risk_score)),
            risk_level=result.risk_level,
            explanation=result.explanation,
            status="open",
        )
        self.db.add(log_entry)
        await self.db.flush()
        return log_entry


# ── Batch Scanner (used by Celery task) ──────────────────────────────────────
async def scan_recent_transactions(db: AsyncSession, user_id: UUID, hours: int = 24) -> int:
    """
    Scan all transactions from the last N hours for a user.
    Called by the background fraud scan task.
    Returns count of flagged transactions.
    """
    since = datetime.now(tz=timezone.utc) - timedelta(hours=hours)
    result = await db.execute(
        select(Transaction).where(
            and_(
                Transaction.user_id == user_id,
                Transaction.transaction_date >= since,
                Transaction.is_flagged_fraud == False,  # noqa: E712
            )
        )
    )
    transactions = result.scalars().all()

    service = FraudDetectionService(db)
    flagged = 0

    for tx in transactions:
        analysis = await service.analyze_transaction(tx, user_id)
        if analysis["is_fraud"]:
            flagged += 1

    log.info(
        "batch_fraud_scan_complete",
        user_id=str(user_id),
        scanned=len(transactions),
        flagged=flagged,
    )
    return flagged
