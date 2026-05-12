from pydantic import BaseModel, Field


class VirtualAccountCreateRequest(BaseModel):
    business_name: str = Field(..., min_length=2, max_length=255)
    customer_identifier: str = Field(..., min_length=2, max_length=100)
    mobile_num: str = Field(..., min_length=10, max_length=15)
    beneficiary_account: str = Field(..., min_length=10, max_length=10)
    bvn: str = Field(..., min_length=11, max_length=11)


class VirtualAccountCreateResponse(BaseModel):
    success: bool
    message: str
    account_name: str | None = None
    account_number: str | None = None
    bank_name: str | None = None
    reference: str | None = None