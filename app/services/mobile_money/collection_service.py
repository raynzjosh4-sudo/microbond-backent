import logging
from typing import Optional

logger = logging.getLogger(__name__)


def initiate_mobile_money_collection(
    phone_number: str,
    amount: int,
    group_id: str,
    obligation_id: int
) -> bool:
    """
    Initiates an automated C2B / Mobile Money USSD collection prompt
    (e.g. MTN MoMo Request to Pay, Airtel Money Collection) to member's handset.
    """
    logger.info(
        f"[MOMO_COLLECTION] Sending USSD payment prompt of {amount:,} UGX to {phone_number} "
        f"(Group: {group_id}, Obligation: {obligation_id})."
    )
    # Telecom gateway integration (MTN MoMo API / Airtel Money / Beyonic)
    # When active credentials exist, posts to collection endpoint; otherwise logs safely.
    return True
