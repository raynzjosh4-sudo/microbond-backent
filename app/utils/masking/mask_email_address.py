from typing import Optional

def mask_email_address(email: Optional[str]) -> Optional[str]:
    """Masks username portion of an email address."""
    if not email or "@" not in email:
        return None
    user_part, domain = email.split("@", 1)
    if len(user_part) <= 2:
        masked_user = user_part[0] + "*"
    else:
        masked_user = user_part[:2] + "*" * (len(user_part) - 2)
    return f"{masked_user}@{domain}"
