from dataclasses import dataclass
from typing import Optional, Dict

MTN_PROVIDERS = {"MTN Mobile Money"}
AIRTEL_PROVIDERS = {"Airtel Money"}
BANK_PROVIDER_CODES: Dict[str, str] = {
    "Stanbic Bank Uganda": "stanbic_ug",
    "DFCU Bank":           "dfcu_ug",
    "Equity Bank Uganda":  "equity_ug",
    "Centenary Bank":      "centenary_ug",
    "KCB Bank Uganda":     "kcb_ug",
    "Absa Bank Uganda":    "absa_ug",
    "PostBank Uganda":     "postbank_ug",
}

VERIFICATION_TYPE_MTN        = "MTN"
VERIFICATION_TYPE_AIRTEL     = "AIRTEL"
VERIFICATION_TYPE_PREMBLY    = "PREMBLY_BANK"
VERIFICATION_TYPE_MANUAL     = "MANUAL"


@dataclass
class VerificationResult:
    is_verified: bool
    verified_name: Optional[str]
    verification_type: str          # "MTN" | "AIRTEL" | "PREMBLY_BANK" | "MANUAL"
    raw_response: Optional[dict]    # Full provider payload, for audit/debugging
