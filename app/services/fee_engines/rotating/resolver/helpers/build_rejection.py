from app.services.fee_engines.rotating.resolver.schemas.deposit_status import DepositStatus
from app.services.fee_engines.rotating.resolver.schemas.payment_type import PaymentType
from app.services.fee_engines.rotating.resolver.schemas.deposit_resolution import (
    DepositResolution,
)


def build_rejection(reason: str) -> DepositResolution:
    return DepositResolution(
        status=DepositStatus.REJECTED,
        payment_type=PaymentType.NORMAL,
        rejection_reason=reason,
        breakdown=None,
        final_charge_amount=0,
        display_summary=reason,
    )
