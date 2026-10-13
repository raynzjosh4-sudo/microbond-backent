from typing import Optional

def mask_phone_number(phone: Optional[str]) -> str:
    """Masks middle characters of a phone number."""
    if not phone or len(phone) < 7:
        return "****"
    return phone[:6] + "****" + phone[-2:]
