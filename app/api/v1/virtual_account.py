from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db, get_current_user
from app.models.user import User
from app.models.virtual_account import VirtualAccount
from app.schemas.virtual_account import (
    VirtualAccountCreateRequest,
    VirtualAccountCreateResponse,
)
from app.services.squad_service import SquadService, SquadAPIError

print("VIRTUAL ACCOUNTS ROUTER LOADED")

router = APIRouter(
    prefix="/virtual-accounts",
    tags=["Virtual Accounts"]
)


@router.post(
    "/create",
    response_model=VirtualAccountCreateResponse
)
async def create_virtual_account(
    payload: VirtualAccountCreateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        squad = SquadService(current_user)

        response = await squad.create_business_virtual_account(
            business_name=payload.business_name,
            customer_identifier=payload.customer_identifier,
            mobile_num=payload.mobile_num,
            beneficiary_account=payload.beneficiary_account,
            bvn=payload.bvn,
        )

        data = response.get("data", {})

        virtual_account = VirtualAccount(
            user_id=current_user.id,
            business_name=payload.business_name,
            customer_identifier=payload.customer_identifier,
            mobile_num=payload.mobile_num,
            beneficiary_account=payload.beneficiary_account,
            bvn=payload.bvn,
            account_name=data.get("account_name"),
            account_number=data.get("account_number"),
            bank_name=data.get("bank_name"),
            reference=data.get("reference"),
        )

        db.add(virtual_account)
        await db.commit()
        await db.refresh(virtual_account)

        return VirtualAccountCreateResponse(
            success=True,
            message="Virtual account created successfully",
            account_name=virtual_account.account_name,
            account_number=virtual_account.account_number,
            bank_name=virtual_account.bank_name,
            reference=virtual_account.reference,
        )

    except SquadAPIError as e:
        raise HTTPException(
            status_code=e.status_code,
            detail=str(e)
        )