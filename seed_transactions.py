from decimal import Decimal
from datetime import datetime, timedelta, timezone
import uuid

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.config import settings
from app.models.user import User
from app.models.transaction import Transaction


# Use sync DB URL
engine = create_engine(settings.DATABASE_URL_SYNC)
SessionLocal = sessionmaker(bind=engine)


def seed_transactions():
    db = SessionLocal()

    try:
        # Find the existing test user
        user = db.query(User).filter(User.email == "user3@example.com").first()

        if not user:
            print("User not found: user3@example.com")
            return

        # Prevent duplicate seeding
        existing = db.query(Transaction).filter(Transaction.user_id == user.id).first()
        if existing:
            print("Transactions already exist for this user.")
            return

        sample_transactions = [
            {
                "amount": Decimal("45000.00"),
                "transaction_type": "credit",
                "status": "success",
                "customer_name": "Ade Ventures",
                "payment_channel": "bank_transfer",
                "narration": "POS settlement"
            },
            {
                "amount": Decimal("120000.00"),
                "transaction_type": "credit",
                "status": "success",
                "customer_name": "Bisi Stores",
                "payment_channel": "card",
                "narration": "Bulk payment"
            },
            {
                "amount": Decimal("850000.00"),
                "transaction_type": "debit",
                "status": "success",
                "customer_name": "Unknown Vendor",
                "payment_channel": "bank_transfer",
                "narration": "Large midnight transfer"
            },
            {
                "amount": Decimal("35000.00"),
                "transaction_type": "debit",
                "status": "failed",
                "customer_name": "Supplier A",
                "payment_channel": "bank_transfer",
                "narration": "Failed supplier payment"
            },
            {
                "amount": Decimal("78000.00"),
                "transaction_type": "credit",
                "status": "success",
                "customer_name": "Kemi Retail",
                "payment_channel": "ussd",
                "narration": "Daily sales inflow"
            }
        ]

        for i, tx in enumerate(sample_transactions):
            transaction = Transaction(
                id=uuid.uuid4(),
                user_id=user.id,
                amount=tx["amount"],
                currency="NGN",
                transaction_type=tx["transaction_type"],
                status=tx["status"],
                customer_name=tx["customer_name"],
                payment_channel=tx["payment_channel"],
                narration=tx["narration"],
                transaction_date=datetime.now(timezone.utc) - timedelta(days=i),
                is_flagged_fraud=False
            )
            db.add(transaction)

        db.commit()
        print("Sample transactions seeded successfully!")

    except Exception as e:
        db.rollback()
        print(f"Error: {str(e)}")

    finally:
        db.close()


if __name__ == "__main__":
    seed_transactions()