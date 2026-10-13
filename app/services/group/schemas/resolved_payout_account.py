from dataclasses import dataclass
from typing import Optional


@dataclass
class ResolvedPayoutAccount:
    destination_id: Optional[str]
    provider_name: str
    account_number: str
    account_name: Optional[str]
    account_type: str  # "MOBILE_MONEY" or "BANK_ACCOUNT"
    source: str        # "GROUP_SPECIFIC", "GLOBAL_DEFAULT", "ANY_VERIFIED", "FALLBACK_PHONE"
