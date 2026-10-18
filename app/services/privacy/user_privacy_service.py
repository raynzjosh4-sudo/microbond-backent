from typing import Optional, Tuple
import uuid
from sqlmodel import Session, select
from sqlalchemy import func
from app.models.user.user import User
from app.models.group.group import GroupMembership

VALID_PRIVACY_OPTIONS = {"EVERYONE", "MY_CONTACTS", "NOBODY"}


def normalize_privacy_setting(value: Optional[str], default: str = "EVERYONE") -> str:
    """
    Normalizes human-friendly strings like "My contacts" or "Everyone" 
    into standard uppercase constants: EVERYONE, MY_CONTACTS, NOBODY.
    """
    if not value:
        return default
    
    cleaned = value.strip().upper().replace(" ", "_")
    if cleaned in ("ALL", "PUBLIC"):
        return "EVERYONE"
    if cleaned in ("CONTACTS", "MY_CONTACTS", "FRIENDS"):
        return "MY_CONTACTS"
    if cleaned in ("NONE", "NOBODY", "PRIVATE"):
        return "NOBODY"
    if cleaned in VALID_PRIVACY_OPTIONS:
        return cleaned
    
    return default


def can_view_profile_photo(
    target_user: User,
    viewer_user_id: Optional[uuid.UUID] = None,
    is_contact: bool = False,
    shares_group: bool = False,
) -> bool:
    """
    Determines whether a viewer is allowed to see the target user's profile photo.
    """
    # User can always see their own photo
    if viewer_user_id and target_user.id == viewer_user_id:
        return True

    visibility = normalize_privacy_setting(
        getattr(target_user, "profile_photo_visibility", "EVERYONE")
    )

    if visibility == "EVERYONE":
        return True
    if visibility == "NOBODY":
        return False
    if visibility == "MY_CONTACTS":
        return is_contact or shares_group

    return True


def can_view_about_status(
    target_user: User,
    viewer_user_id: Optional[uuid.UUID] = None,
    is_contact: bool = False,
    shares_group: bool = False,
) -> bool:
    """
    Determines whether a viewer is allowed to see the target user's about status.
    """
    if viewer_user_id and target_user.id == viewer_user_id:
        return True

    visibility = normalize_privacy_setting(
        getattr(target_user, "about_visibility", "EVERYONE")
    )

    if visibility == "EVERYONE":
        return True
    if visibility == "NOBODY":
        return False
    if visibility == "MY_CONTACTS":
        return is_contact or shares_group

    return True


def check_shared_group_membership(
    user_a_id: uuid.UUID,
    user_b_id: uuid.UUID,
    session: Session,
) -> bool:
    """
    Checks if two users share at least one active group membership.
    """
    if user_a_id == user_b_id:
        return True

    shared_group = session.exec(
        select(GroupMembership.group_id).where(
            GroupMembership.user_id.in_([user_a_id, user_b_id]),
            GroupMembership.status == "ACTIVE",
        ).group_by(GroupMembership.group_id).having(func.count(GroupMembership.user_id) >= 2)
    ).first()

    return shared_group is not None


def can_add_to_group(
    target_user: User,
    adder_user: User,
    session: Session,
) -> Tuple[bool, Optional[str]]:
    """
    Determines whether an admin/user is authorized by the target user's privacy rules
    to add them directly to a group.
    
    Returns:
        (is_allowed: bool, rejection_reason: Optional[str])
    """
    if target_user.id == adder_user.id:
        return True, None

    permission = normalize_privacy_setting(
        getattr(target_user, "group_add_permission", "EVERYONE")
    )

    if permission == "EVERYONE":
        return True, None

    if permission == "NOBODY":
        return (
            False,
            "This user's privacy settings do not allow anyone to add them to groups.",
        )

    if permission == "MY_CONTACTS":
        # Check if adder is a trusted contact via existing shared active group
        is_connected = check_shared_group_membership(
            target_user.id, adder_user.id, session
        )
        if not is_connected:
            return (
                False,
                "This user's privacy settings only allow their contacts to add them to groups.",
            )
        return True, None

    return True, None
