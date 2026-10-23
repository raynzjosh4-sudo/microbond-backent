import uuid
from typing import List, Optional, Dict
from fastapi import APIRouter, Depends
from sqlmodel import Session, select

from app.core.database import get_session
from app.models.user.core.user import User
from app.models.group.core.group import Group
from app.models.group.core.group_membership import GroupMembership
from app.models.group.settings import GroupVisibilitySettings
from .schemas import (
    ContactSyncRequest,
    DiscoverableContactGroup,
    ContactMemberSummary,
)
from .sync_contacts import get_optional_current_user
from app.utils.avatar_colors import resolve_vibrant_avatar_color

router = APIRouter()

CHUNK_SIZE = 500
MAX_TOTAL_LOOKUPS = 5000


@router.post(
    "/discover-groups",
    response_model=List[DiscoverableContactGroup],
    summary="Discover Groups where Phone Contacts are Members",
    description="Cross-references phone contacts against active group memberships to discover trusted groups with mutual contacts.",
)
def discover_groups_by_contacts(
    request: ContactSyncRequest,
    session: Session = Depends(get_session),
    current_user: Optional[User] = Depends(get_optional_current_user),
) -> List[DiscoverableContactGroup]:
    """
    Finds groups that the caller's phone contacts are actively enrolled in:
    1. Looks up contacts who are registered Microbond users.
    2. Identifies active group memberships of those contacts.
    3. Excludes groups the caller is already a member of.
    4. Gathers group metadata and lists the contacts in each group.
    5. Returns groups ranked by highest mutual contact count.
    """
    if not request.phone_numbers:
        return []

    # 1. Clean, strip and deduplicate phone numbers
    unique_numbers = list({
        num.strip()
        for num in request.phone_numbers
        if num and num.strip()
    })[:MAX_TOTAL_LOOKUPS]

    if not unique_numbers:
        return []

    current_user_id = current_user.id if current_user else None

    # 2. Look up matching users from contacts in chunks
    matched_users: List[User] = []
    for i in range(0, len(unique_numbers), CHUNK_SIZE):
        chunk = unique_numbers[i : i + CHUNK_SIZE]
        statement = select(User).where(User.phone_number.in_(chunk))
        if current_user_id:
            statement = statement.where(User.id != current_user_id)
        results = session.exec(statement).all()
        matched_users.extend(results)

    if not matched_users:
        return []

    user_map: Dict[uuid.UUID, User] = {u.id: u for u in matched_users}
    contact_user_ids = list(user_map.keys())

    # 3. Find groups the current user is ALREADY in (avoid suggesting groups they already joined)
    my_group_ids_set = set()
    if current_user_id:
        my_memberships = session.exec(
            select(GroupMembership.group_id).where(
                GroupMembership.user_id == current_user_id,
                GroupMembership.status == "ACTIVE",
            )
        ).all()
        my_group_ids_set = set(my_memberships)

    # 4. Find all active group memberships of matched contacts
    group_to_contacts: Dict[str, List[User]] = {}
    for i in range(0, len(contact_user_ids), CHUNK_SIZE):
        chunk_ids = contact_user_ids[i : i + CHUNK_SIZE]
        memberships = session.exec(
            select(GroupMembership).where(
                GroupMembership.user_id.in_(chunk_ids),
                GroupMembership.status == "ACTIVE",
            )
        ).all()

        for m in memberships:
            # Skip if current user is already in this group
            if m.group_id in my_group_ids_set:
                continue
            contact = user_map.get(m.user_id)
            if contact:
                current_list = group_to_contacts.setdefault(m.group_id, [])
                if not any(existing.id == contact.id for existing in current_list):
                    current_list.append(contact)

    if not group_to_contacts:
        return []

    # 5. Fetch details for these groups
    candidate_group_ids = list(group_to_contacts.keys())
    active_groups: List[Group] = []
    for i in range(0, len(candidate_group_ids), CHUNK_SIZE):
        chunk_gids = candidate_group_ids[i : i + CHUNK_SIZE]
        groups = session.exec(
            select(Group).where(
                Group.group_id.in_(chunk_gids),
                Group.status == "ACTIVE",
            )
        ).all()
        for g in groups:
            vis = session.exec(
                select(GroupVisibilitySettings).where(GroupVisibilitySettings.group_id == g.group_id)
            ).first()
            # Groups with invite-only discoverability do not appear in searches or discovery
            if vis and vis.invite_only_discoverability:
                continue
            active_groups.append(g)

    # 6. Build the response list
    results: List[DiscoverableContactGroup] = []
    for g in active_groups:
        contacts_in_group = group_to_contacts.get(g.group_id, [])
        if not contacts_in_group:
            continue

        results.append(
            DiscoverableContactGroup(
                group_id=g.group_id,
                name=g.name,
                description=g.description or "",
                group_image_url=g.group_image_url or "",
                type=g.type,
                payment_mode=g.payment_mode or "OBLIGATION",
                visibility=g.visibility or "PRIVATE",
                currency=g.currency or "UGX",
                member_count=g.member_count or len(contacts_in_group),
                max_members=g.max_members,
                mutual_contacts_count=len(contacts_in_group),
                contact_members=[
                    ContactMemberSummary(
                        user_id=str(u.id),
                        phone_number=u.phone_number,
                        profile_name=u.full_name or "Microbond Member",
                        profile_picture_url=u.profile_picture_url,
                        avatar_color=resolve_vibrant_avatar_color(u.avatar_color, seed=u.phone_number or str(u.id)),
                    )
                    for u in contacts_in_group
                ],
            )
        )

    # 7. Sort: Groups with the most mutual contacts appear first
    results.sort(key=lambda item: item.mutual_contacts_count, reverse=True)
    return results
