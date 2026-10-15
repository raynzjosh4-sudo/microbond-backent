from app.models.user.userpayoutaccount.payout_destination import UserPayoutDestination

def mask_number(number: str) -> str:
    """Masks all but the last 4 digits (e.g., **** 1234)"""
    if not number or len(number) < 4:
        return "****"
    return f"**** {number[-4:]}"

def format_destination_response(dest: UserPayoutDestination, source: str) -> dict:
    return {
        "status": "success",
        "source": source,
        "data": {
            "id": dest.id,
            "provider_name": dest.provider_name,
            "account_number": dest.account_number,
            "verified_name": dest.verified_name,
            "account_name": dest.verified_name,  # Backward compatibility for mobile client
            "account_type": dest.account_type,
            "is_verified": dest.is_verified,
            "verification_type": dest.verification_type,
            "masked_number": mask_number(dest.account_number)
        }
    }
