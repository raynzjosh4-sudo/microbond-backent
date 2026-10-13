from dataclasses import dataclass
from typing import List, Tuple, Optional

# MTN MoMo Open API collection fee rate (1.5%)
MTN_RATE: float = 0.015

# Psychological offset tier table.
# Format: (max_ugx_exclusive, psychological_offset)
TIER_TABLE: List[Tuple[Optional[int], int]] = [
    (5_001,   15),  # <= 5,000 UGX
    (10_001,  16),  # <= 10,000 UGX
    (20_001,  17),  # <= 20,000 UGX
    (50_001,  18),  # <= 50,000 UGX
    (100_001, 19),  # <= 100,000 UGX
    (500_001, 21),  # <= 500,000 UGX  (intentional skip of 20 per spec)
    (None,    22),  # >  500,000 UGX
]


@dataclass(frozen=True)
class DepositFeeBreakdown:
    """
    Immutable result object returned by calculate_deposit_fee.
    """
    group_target_amount: int
    mtn_fee: int
    platform_fee: int
    total_fee: int
    charge_amount: int
    psychological_offset: int
    microbond_net_revenue: int
