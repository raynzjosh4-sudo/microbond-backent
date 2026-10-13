from dataclasses import dataclass


@dataclass(frozen=True)
class DepositBreakdown:
    """
    Detailed line-by-line breakdown of what the member owes and what
    they are paying. Returned as part of DepositResolution for UI display.
    """
    current_cycle_due: int
    amount_already_paid: int
    current_cycle_remaining: int
    arrears_owed: int
    penalties_owed: int
    total_outstanding: int

    entered_amount: int
    amount_to_credit: int
    surplus_credited_forward: int
    shortfall_remaining: int

    mtn_collection_fee: int
    microbond_base_fee: int
    milestone_payout_fee: int
    total_fee: int
    final_charge_amount: int

    is_milestone_deposit: bool
