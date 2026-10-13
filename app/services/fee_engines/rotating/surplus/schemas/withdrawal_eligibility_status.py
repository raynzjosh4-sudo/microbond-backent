from enum import Enum


class WithdrawalEligibilityStatus(str, Enum):
    """Result of evaluating an accidental overpayment refund request."""
    ELIGIBLE                = "ELIGIBLE"                # All gates passed; ready to disburse
    EXCEEDS_CREDIT_BALANCE  = "EXCEEDS_CREDIT_BALANCE"  # Requested > unallocated advance credit
    INSUFFICIENT_POOL_CASH  = "INSUFFICIENT_POOL_CASH"  # Withdrawal would break upcoming recipient pot
    TIMELOCK_ACTIVE         = "TIMELOCK_ACTIVE"         # Cooldown window has not expired
    PENDING_APPROVALS       = "PENDING_APPROVALS"       # Multi-sig approvals still required
    BELOW_MINIMUM_THRESHOLD = "BELOW_MINIMUM_THRESHOLD" # Amount less than telecom disbursement fee
