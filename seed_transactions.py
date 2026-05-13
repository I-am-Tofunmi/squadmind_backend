"""
seed_transactions.py

Populate the database with realistic SME transactions for:
- Dashboard analytics
- Fraud detection
- Forecasting
- TrustScore engine
- Demo presentation

Run with:

python seed_transactions.py
"""

import asyncio
import random
import uuid
from decimal import Decimal
from datetime import datetime, timedelta, timezone

from sqlalchemy import select

from app.db.session import AsyncSessionLocal
from app.models.transaction import Transaction
from app.models.user import User


CUSTOMER_NAMES = [
    "Ade Traders",
    "Bola Ventures",
    "Chika Stores",
    "Divine Foods",
    "Eko Supplies",
    "Fresh Mart",
    "Grace Electronics",
    "Harmony Fashion",
    "Ikeja Wholesales",
    "Jide Agro",
]

PAYMENT_CHANNELS = [
    "bank_transfer",
    "pos",
    "ussd",
    "card",
    "virtual_account",
]

TRANSACTION_TYPES = [
    "credit",
    "payment",
    "transfer",
    "debit",
]

STATUSES = [
    "success",
    "success",
    "success",
    "success",
    "failed",
    "pending",
]


def generate_amount():
    """
    Create stronger demo-ready transaction values
    with guaranteed suspicious transactions
    """

    # 25% chance of high-value suspicious transaction
    if random.randint(1, 4) == 2:
        suspicious_values = [
            500000,
            750000,
            850000,
            1000000,
            1200000,
            1500000,
            2000000,
        ]
        return Decimal(str(random.choice(suspicious_values)))

    # normal SME transaction
    return Decimal(str(random.randint(5000, 250000)))


def should_flag_fraud(amount):
    """
    Stronger fraud detection trigger for demo presentation
    """

    # automatic fraud flag for large amounts
    if amount >= 500000:
        return True

    # some medium suspicious transactions
    if random.randint(1, 6) == 3:
        return True

    return False


async def seed_transactions():
    async with AsyncSessionLocal() as db:

        # Always seed for user1 specifically
        result = await db.execute(
            select(User).where(User.email == "user1@example.com")
        )
        user = result.scalar_one_or_none()

        if not user:
            print("User user1@example.com not found. Register user first.")
            return

        print(f"Seeding transactions for user: {user.email}")

        transactions_to_create = []

        for _ in range(75):
            customer = random.choice(CUSTOMER_NAMES)
            amount = generate_amount()
            is_flagged = should_flag_fraud(amount)

            fraud_score = (
                Decimal(str(round(random.uniform(65, 95), 2)))
                if is_flagged
                else Decimal(str(round(random.uniform(5, 35), 2)))
            )

            tx_date = datetime.now(timezone.utc) - timedelta(
                days=random.randint(1, 90),
                hours=random.randint(1, 23),
                minutes=random.randint(1, 59),
            )

            transaction = Transaction(
                id=uuid.uuid4(),
                user_id=user.id,

                squad_transaction_ref=f"SQD-{uuid.uuid4().hex[:12].upper()}",
                squad_merchant_ref=f"MER-{uuid.uuid4().hex[:8].upper()}",

                amount=amount,
                currency="NGN",
                transaction_type=random.choice(TRANSACTION_TYPES),
                status=random.choice(STATUSES),

                customer_name=customer,
                customer_email=f"{customer.lower().replace(' ', '')}@gmail.com",
                customer_phone=f"080{random.randint(10000000, 99999999)}",
                customer_id=f"CUST-{random.randint(1000, 9999)}",

                payment_channel=random.choice(PAYMENT_CHANNELS),
                narration=f"Payment from {customer}",

                meta={
                    "source": "seed_script",
                    "demo": True,
                },

                is_flagged_fraud=is_flagged,
                fraud_score=fraud_score,

                transaction_date=tx_date,
                created_at=tx_date,
            )

            transactions_to_create.append(transaction)

        db.add_all(transactions_to_create)
        await db.commit()

        print("===================================")
        print("Transactions seeded successfully!")
        print(f"Total inserted: {len(transactions_to_create)}")
        print("Dashboard will now show real data.")
        print("Fraud engine can now trigger alerts.")
        print("TrustScore engine is ready for build.")
        print("===================================")


if __name__ == "__main__":
    asyncio.run(seed_transactions())