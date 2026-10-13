from typing import Optional

def mask_account_number(number: Optional[str]) -> str:
    """Masks all but the last 4 characters of an account/phone number."""
    if not number or len(number) < 4:
        return "****"
    return f"**** {number[-4:]}"
