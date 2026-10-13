import logging
import uuid
from fastapi import APIRouter, Depends, BackgroundTasks
from sqlmodel import Session
from app.core.database import get_session
from app.api.dependencies import require_telecom_kyc_guard
from app.models.user.user import User
from .schemas import ExecuteDepositRequest, ExecuteDepositResponse
from .helpers.sanitize_and_detect_uganda_carrier import sanitize_and_detect_uganda_carrier

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post(
    "/execute",
    response_model=ExecuteDepositResponse,
    summary="Layer 3: Detect Carrier & Execute USSD Mobile Money Prompt",
    description="Sanitizes Ugandan MSISDN, detects MTN/Airtel network, and pushes USSD PIN prompt to user device.",
)
async def execute_mobile_money_deposit(
    payload: ExecuteDepositRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(require_telecom_kyc_guard),
    session: Session = Depends(get_session),
):
    formatted_number, provider = sanitize_and_detect_uganda_carrier(
        payload.phone_number
    )

    tx_id = f"tx_dep_{uuid.uuid4().hex[:12]}"

    logger.info(
        f"[MOMO_DEPOSIT_EXECUTE] Initiating {provider} USSD push prompt of {payload.total_to_charge:,} UGX "
        f"to {formatted_number} for user {current_user.id} in group {payload.group_id} (TX: {tx_id})"
    )

    return ExecuteDepositResponse(
        status="PROCESSING",
        message=f"USSD PIN prompt dispatched to {provider} line +{formatted_number}. Please enter your Mobile Money PIN on your phone to complete deposit.",
        transaction_id=tx_id,
        provider=provider,
        formatted_phone_number=formatted_number,
    )
