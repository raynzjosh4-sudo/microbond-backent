import re
from fastapi import HTTPException, status

AIRTEL_PREFIXES = {
    "700", "701", "702", "703", "704", "705", "706", "707", "708", "709",
    "750", "751", "752", "753", "754", "755", "756", "757", "758", "759",
    "740", "741", "742", "743", "744"
}

def sanitize_and_detect_carrier(phone: str, validate_length: bool = False) -> tuple[str, str]:
    """
    Cleans phone number to Ugandan MSISDN (2567XXXXXXXX) and detects telecom carrier:
    Returns (formatted_phone_256..., carrier_name)
    e.g. ("256701234567", "Airtel Money Uganda") or ("256771234567", "MTN Mobile Money Uganda")
    """
    clean_number = re.sub(r'\D', '', phone)
    if clean_number.startswith("256"):
        formatted = clean_number
    elif clean_number.startswith("0"):
        formatted = "256" + clean_number[1:]
    else:
        formatted = "256" + clean_number

    if validate_length and len(formatted) != 12:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid Ugandan phone number format. Must be a valid 10-digit local or 12-digit international number."
        )

    prefix = formatted[3:6] if len(formatted) >= 6 else ""
    if prefix in AIRTEL_PREFIXES:
        return formatted, "Airtel Money Uganda"
    return formatted, "MTN Mobile Money Uganda"
