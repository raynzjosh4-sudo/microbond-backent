from typing import Dict


def format_deposit_broadcast_message(
    member_display_name: str,
    entered_amount_ugx: int,
    cycle_number: int,
    cycle_obligation_ugx: int,
    is_advance: bool = False,
) -> Dict[str, str]:
    """
    Generate broadcast announcements balancing social accountability and privacy.
    """
    public_msg = f"🎉 {member_display_name} contributed for Cycle {cycle_number}."

    if is_advance and entered_amount_ugx > cycle_obligation_ugx:
        surplus = entered_amount_ugx - cycle_obligation_ugx
        private_msg = (
            f"Deposit Confirmed: {entered_amount_ugx:,} UGX received. "
            f"Cycle {cycle_number} is cleared. Surplus of {surplus:,} UGX has been "
            f"credited forward to upcoming cycles. Your payout turn position remains unchanged."
        )
    else:
        private_msg = (
            f"Deposit Confirmed: {entered_amount_ugx:,} UGX received. "
            f"Cycle {cycle_number} is fully settled."
        )

    return {
        "group_chat_broadcast": public_msg,
        "member_private_receipt": private_msg,
    }
