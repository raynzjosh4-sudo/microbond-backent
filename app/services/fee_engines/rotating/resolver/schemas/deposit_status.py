from enum import Enum


class DepositStatus(str, Enum):
    """Outcome of the deposit resolution check."""
    APPROVED        = "APPROVED"        # Amount is valid — proceed to MTN
    REJECTED        = "REJECTED"        # Amount violates group rules — show error
    APPROVED_PARTIAL= "APPROVED_PARTIAL"# Partial payment accepted (underpayment OK)
    APPROVED_ADVANCE= "APPROVED_ADVANCE"# Overpayment accepted (credited forward)
