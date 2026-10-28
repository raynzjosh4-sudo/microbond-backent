from typing import Literal
from pydantic import BaseModel, Field


class ProposeSinglePayoutDestinationRequest(BaseModel):
    provider_name: str = Field(..., min_length=2, max_length=100)
    account_type: Literal["BANK_ACCOUNT", "MOBILE_MONEY"]
    account_number: str = Field(..., min_length=4, max_length=64)
    account_name: str = Field(..., min_length=2, max_length=150)


class ApproveSinglePayoutDestinationRequest(BaseModel):
    approved: bool


class SetMemberPayoutDestinationRequest(BaseModel):
    payout_destination_id: str = Field(..., min_length=1, max_length=100)
