from uuid import uuid4

from sqlalchemy import String, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class VirtualAccount(Base):
    __tablename__ = "virtual_accounts"

    id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid4
    )

    user_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id"),
        nullable=False
    )

    business_name: Mapped[str] = mapped_column(String, nullable=False)
    customer_identifier: Mapped[str] = mapped_column(String, nullable=False)
    mobile_num: Mapped[str] = mapped_column(String, nullable=False)
    beneficiary_account: Mapped[str] = mapped_column(String, nullable=False)
    bvn: Mapped[str] = mapped_column(String, nullable=False)

    account_name: Mapped[str] = mapped_column(String, nullable=True)
    account_number: Mapped[str] = mapped_column(String, nullable=True)
    bank_name: Mapped[str] = mapped_column(String, nullable=True)
    reference: Mapped[str] = mapped_column(String, nullable=True)