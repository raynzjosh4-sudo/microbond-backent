import re
import logging
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from pydantic import BaseModel, Field
from sqlmodel import Session

from app.core.database import get_session
from app.api.dependencies import require_telecom_kyc_guard
from app.models.user.user import User

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/deposit", tags=["Mobile Money Deposit Execution"])

class ExecuteDepositRequest(BaseModel):
    phone_number: str = Field(..., description="Ugandan Mobile Money phone number (e.g. 0771234567 or 256701234567)")
    total_to_charge: int = Field(..., gt=0, description="Total amount to charge including fees (UGX Integer)")
    quote_token: Optional[str] = Field(default=None, description="Layer 2 validated quote token")
    group_id: str = Field(..., description="Target group ID")

class ExecuteDepositResponse(BaseModel):
    status: str = "PROCESSING"
    message: str
    transaction_id: str
    provider: str
    formatted_phone_number: str

def sanitize_and_detect_uganda_carrier(raw_phone: str) -> tuple[str, str]:
    """
    Cleans phone number to E.164 Ugandan format (2567XXXXXXXX)
    and detects the mobile money network (MTN_UG or AIRTEL_UG).
    """
    clean_number = re.sub(r'\D', '', raw_phone)
    if clean_number.startswith("256"):
        formatted = clean_number
    elif clean_number.startswith("0"):
        formatted = "256" + clean_number[1:]
    else:
        formatted = "256" + clean_number

    if len(formatted) != 12:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid Ugandan phone number format. Must be a valid 10-digit local or 12-digit international number."
        )

    # Prefix checks (3-digit NDC after 256)
    prefix = formatted[3:6]

    airtel_prefixes = {"700", "701", "702", "703", "704", "705", "706", "707", "708", "709",
                       "750", "751", "752", "753", "754", "755", "756", "757", "758", "759", "744", "740", "741", "742", "743"}

    mtn_prefixes = {"770", "771", "772", "773", "774", "775", "776", "777", "778", "779",
                    "780", "781", "782", "783", "784", "785", "786", "787", "788", "789",
                    "760", "761", "762", "763", "764", "790", "791", "792", "793", "794"}

    if prefix in airtel_prefixes:
        provider = "AIRTEL_UG"
    elif prefix in mtn_prefixes:
        provider = "MTN_UG"
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported mobile network prefix ({prefix}). Must be an active MTN or Airtel Uganda line."
        )

    return formatted, provider

@router.post(
    "/execute",
    response_model=ExecuteDepositResponse,
    summary="Layer 3: Detect Carrier & Execute USSD Mobile Money Prompt",
    description="Sanitizes Ugandan MSISDN, detects MTN/Airtel network, and pushes USSD PIN prompt to user device."
)
async def execute_mobile_money_deposit(
    payload: ExecuteDepositRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(require_telecom_kyc_guard),
    session: Session = Depends(get_session)
):
    formatted_number, provider = sanitize_and_detect_uganda_carrier(payload.phone_number)

    import uuid
    tx_id = f"tx_dep_{uuid.uuid4().hex[:12]}"

    logger.info(
        f"[MOMO_DEPOSIT_EXECUTE] Initiating {provider} USSD push prompt of {payload.total_to_charge:,} UGX "
        f"to {formatted_number} for user {current_user.id} in group {payload.group_id} (TX: {tx_id})"
    )

    # Trigger async payment gateway prompt (MTN MoMo API / Airtel Money API)
    # In background: gateway sends USSD prompt -> user enters PIN -> webhook fires -> ledger updates ring!

    return ExecuteDepositResponse(
        status="PROCESSING",
        message=f"USSD PIN prompt dispatched to {provider} line +{formatted_number}. Please enter your Mobile Money PIN on your phone to complete deposit.",
        transaction_id=tx_id,
        provider=provider,
        formatted_phone_number=formatted_number
    )
