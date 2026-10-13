from enum import Enum


class PaymentType(str, Enum):
    """What kind of payment this deposit represents."""
    NORMAL          = "NORMAL"          # Exact or within normal range
    ARREARS         = "ARREARS"         # Catching up missed past cycles
    PARTIAL         = "PARTIAL"         # Paying less than total due (allowed)
    ADVANCE         = "ADVANCE"         # Paying more than total due (allowed)
    ARREARS_PARTIAL = "ARREARS_PARTIAL" # Catching up but still not fully cleared
