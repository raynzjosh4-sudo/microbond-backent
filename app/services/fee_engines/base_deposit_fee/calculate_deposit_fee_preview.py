from typing import Dict, Any
from app.services.fee_engines.base_deposit_fee.calculate_deposit_fee import calculate_deposit_fee


def calculate_deposit_fee_preview(group_target_amount: int) -> Dict[str, Any]:
    """
    Return a JSON-serializable dict of the fee breakdown, ready to send
    to the mobile client as a deposit confirmation preview payload.

    Parameters
    ----------
    group_target_amount : int
        The base deposit amount in UGX.

    Returns
    -------
    dict
        Keys:
          group_target_amount  — what lands in the user's savings pool
          mtn_fee              — MTN's cut
          platform_fee         — Microbond's revenue
          total_fee            — total processing cost
          charge_amount        — exact amount shown on the MoMo PIN prompt
          display_label        — human-readable string for the UI button
    """
    b = calculate_deposit_fee(group_target_amount)
    return {
        "group_target_amount": b.group_target_amount,
        "mtn_fee": b.mtn_fee,
        "platform_fee": b.platform_fee,
        "total_fee": b.total_fee,
        "charge_amount": b.charge_amount,
        "display_label": f"{b.charge_amount:,} UGX",
    }
