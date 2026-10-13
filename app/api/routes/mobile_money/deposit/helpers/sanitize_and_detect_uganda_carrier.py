import re
from fastapi import HTTPException, status


def sanitize_and_detect_uganda_carrier(raw_phone: str) -> tuple[str, str]:
    """
    Cleans phone number to E.164 Ugandan format (2567XXXXXXXX)
    and detects the mobile money network (MTN_UG or AIRTEL_UG).
    """
    clean_number = re.sub(r"\D", "", raw_phone)
    if clean_number.startswith("256"):
        formatted = clean_number
    elif clean_number.startswith("0"):
        formatted = "256" + clean_number[1:]
    else:
        formatted = "256" + clean_number

    if len(formatted) != 12:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid Ugandan phone number format. Must be a valid 10-digit local or 12-digit international number.",
        )

    # Prefix checks (3-digit NDC after 256)
    prefix = formatted[3:6]

    airtel_prefixes = {
        "700",
        "701",
        "702",
        "703",
        "704",
        "705",
        "706",
        "707",
        "708",
        "709",
        "750",
        "751",
        "752",
        "753",
        "754",
        "755",
        "756",
        "757",
        "758",
        "759",
        "744",
        "740",
        "741",
        "742",
        "743",
    }

    mtn_prefixes = {
        "770",
        "771",
        "772",
        "773",
        "774",
        "775",
        "776",
        "777",
        "778",
        "779",
        "780",
        "781",
        "782",
        "783",
        "784",
        "785",
        "786",
        "787",
        "788",
        "789",
        "760",
        "761",
        "762",
        "763",
        "764",
        "790",
        "791",
        "792",
        "793",
        "794",
    }

    if prefix in airtel_prefixes:
        provider = "AIRTEL_UG"
    elif prefix in mtn_prefixes:
        provider = "MTN_UG"
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported mobile network prefix ({prefix}). Must be an active MTN or Airtel Uganda line.",
        )

    return formatted, provider
