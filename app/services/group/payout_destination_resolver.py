import re
from dataclasses import dataclass
from typing import Optional
from uuid import UUID
from sqlmodel import Session, select

from app.models.group.group import GroupMembership
from app.models.user.user import User
from app.models.user.userpayoutaccount.payout_destination import UserPayoutDestination

@dataclass
class ResolvedPayoutAccount:
    destination_id: Optional[str]
    provider_name: str
    account_number: str
    account_name: Optional[str]
    account_type: str  # "MOBILE_MONEY" or "BANK_ACCOUNT"
    source: str        # "GROUP_SPECIFIC", "GLOBAL_DEFAULT", "ANY_VERIFIED", "FALLBACK_PHONE"

def sanitize_and_detect_carrier(phone: str) -> tuple[str, str]:
    """
    Cleans phone number and detects Ugandan telecom provider.
    """
    clean = re.sub(r'\D', '', phone)
    if clean.startswith("256"):
        formatted = clean
    elif clean.startswith("0"):
        formatted = "256" + clean[1:]
    else:
        formatted = "256" + clean

    prefix = formatted[3:6] if len(formatted) >= 6 else ""

    airtel_prefixes = {
        "700", "701", "702", "703", "704", "705", "706", "707", "708", "709",
        "750", "751", "752", "753", "754", "755", "756", "757", "758", "759",
        "740", "741", "742", "743", "744"
    }

    if prefix in airtel_prefixes:
        return formatted, "Airtel Money Uganda"
    return formatted, "MTN Mobile Money Uganda"

def mask_account_number(number: str) -> str:
    """Masks all but the last 4 characters."""
    if not number or len(number) < 4:
        return "****"
    return f"**** {number[-4:]}"

def resolve_member_payout_destination(
    session: Session,
    group_id: str,
    user_id: UUID
) -> ResolvedPayoutAccount:
    """
    Resolves the exact account to which a member's payout should be disbursed.
    Hierarchy:
    1. Group-specific chosen payout destination (GroupMembership.payout_destination_id)
    2. User's global default payout destination (UserPayoutDestination.is_default == True)
    3. Any verified payout destination of the user
    4. Fallback: User's registered phone number as Mobile Money
    """
    # 1. Check GroupMembership for a group-specific choice
    membership = session.exec(
        select(GroupMembership).where(
            GroupMembership.group_id == group_id,
            GroupMembership.user_id == user_id
        )
    ).first()

    if membership and membership.payout_destination_id:
        group_dest = session.exec(
            select(UserPayoutDestination).where(
                UserPayoutDestination.id == membership.payout_destination_id,
                UserPayoutDestination.user_id == user_id
            )
        ).first()

        if group_dest:
            return ResolvedPayoutAccount(
                destination_id=group_dest.id,
                provider_name=group_dest.provider_name,
                account_number=group_dest.account_number,
                account_name=group_dest.verified_name or group_dest.account_name,
                account_type=group_dest.account_type,
                source="GROUP_SPECIFIC"
            )

    # 2. Check for user's global default payout destination
    default_dest = session.exec(
        select(UserPayoutDestination).where(
            UserPayoutDestination.user_id == user_id,
            UserPayoutDestination.is_default == True
        )
    ).first()

    if default_dest:
        return ResolvedPayoutAccount(
            destination_id=default_dest.id,
            provider_name=default_dest.provider_name,
            account_number=default_dest.account_number,
            account_name=default_dest.verified_name or default_dest.account_name,
            account_type=default_dest.account_type,
            source="GLOBAL_DEFAULT"
        )

    # 3. Check for any verified payout destination
    verified_dest = session.exec(
        select(UserPayoutDestination).where(
            UserPayoutDestination.user_id == user_id,
            UserPayoutDestination.is_verified == True
        )
    ).first()

    if verified_dest:
        return ResolvedPayoutAccount(
            destination_id=verified_dest.id,
            provider_name=verified_dest.provider_name,
            account_number=verified_dest.account_number,
            account_name=verified_dest.verified_name or verified_dest.account_name,
            account_type=verified_dest.account_type,
            source="ANY_VERIFIED"
        )

    # 4. Fallback to user registered phone number
    user = session.exec(select(User).where(User.id == user_id)).first()
    raw_phone = user.phone_number if user and user.phone_number else ""
    formatted_phone, detected_provider = sanitize_and_detect_carrier(raw_phone)

    return ResolvedPayoutAccount(
        destination_id=None,
        provider_name=detected_provider,
        account_number=formatted_phone,
        account_name=user.full_name if user else None,
        account_type="MOBILE_MONEY",
        source="FALLBACK_PHONE"
    )
