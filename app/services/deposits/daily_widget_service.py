"""
Service for computing daily deposit widget analytics and member status drill-down.
Uses local timezone day boundaries (Africa/Kampala, UTC+3) and verifies group visibility permissions.
"""
from datetime import datetime
from typing import Optional, List, Dict, Any, Tuple
import uuid
from fastapi import HTTPException
from sqlmodel import Session, select
from sqlalchemy import func

from app.models.user.user import User
from app.models.group.group import Group, GroupMembership
from app.models.group.settings import GroupVisibilitySettings
from app.models.group.finance.member_obligation import MemberObligation
from app.models.group.ledger.ledger_entry import LedgerEntry
from app.models.group.rotating.rotating_group_details import RotatingGroupDetails
from app.services.analytics.buckets import LOCAL_TZ

def get_day_window(date_ms: Optional[int] = None) -> Tuple[int, int, str]:
    """
    Returns (start_ms, end_ms, date_str) for a specific day in Africa/Kampala.
    If date_ms is None, uses current local time.
    """
    if date_ms is not None:
        dt = datetime.fromtimestamp(date_ms / 1000.0, tz=LOCAL_TZ)
    else:
        dt = datetime.now(LOCAL_TZ)
        
    start_dt = dt.replace(hour=0, minute=0, second=0, microsecond=0)
    end_dt = dt.replace(hour=23, minute=59, second=59, microsecond=999000)
    
    start_ms = int(start_dt.timestamp() * 1000)
    end_ms = int(end_dt.timestamp() * 1000)
    date_str = start_dt.strftime("%Y-%m-%d")
    return start_ms, end_ms, date_str

def mask_phone_number(phone: Optional[str]) -> str:
    """Masks a phone number for privacy: e.g. +256 701 *** 890"""
    if not phone:
        return "Hidden"
    p = str(phone).strip()
    if len(p) <= 6:
        return "***"
    return f"{p[:5]} *** {p[-3:]}"

def verify_deposit_widget_access(
    session: Session,
    group_id: str,
    current_user_id: uuid.UUID
) -> Tuple[GroupMembership, GroupVisibilitySettings]:
    """
    Verifies that the requester is an active member and that the group's
    visibility settings permit them to view the daily deposit widget.
    """
    membership = session.exec(
        select(GroupMembership).where(
            GroupMembership.group_id == group_id,
            GroupMembership.user_id == current_user_id
        )
    ).first()

    if not membership or membership.status != "ACTIVE":
        raise HTTPException(status_code=403, detail="You must be an active member of this group.")

    vis_settings = session.exec(
        select(GroupVisibilitySettings).where(GroupVisibilitySettings.group_id == group_id)
    ).first()

    # If no visibility settings exist, default to ALL_MEMBERS
    visibility = getattr(vis_settings, "deposit_widget_visibility", "ALL_MEMBERS") if vis_settings else "ALL_MEMBERS"

    if visibility == "ADMIN_ONLY" and membership.role != "ADMIN":
        raise HTTPException(
            status_code=403,
            detail="The Group Admin has restricted the daily deposit widget to group admins."
        )
    elif visibility == "ADMIN_AND_TREASURER" and membership.role not in ["ADMIN", "TREASURER"]:
        raise HTTPException(
            status_code=403,
            detail="The Group Admin has restricted the daily deposit widget to administrators and treasurers."
        )

    return membership, vis_settings

def _compute_member_deposit_states(
    session: Session,
    group_id: str,
    day_start_ms: int,
    day_end_ms: int,
    caller_role: str,
    hide_contact_info: bool
) -> Tuple[int, List[Dict[str, Any]]]:
    """
    Calculates deposit state (FULL, PARTIAL, NOT_DEPOSITED) for each active member.
    Returns (target_amount_per_member, member_records).
    """
    # 1. Fetch group details to find default contribution target
    rotating = session.exec(
        select(RotatingGroupDetails).where(RotatingGroupDetails.group_id == group_id)
    ).first()
    default_target = int(rotating.contribution_amount) if rotating and rotating.contribution_amount else 0

    # 2. Fetch all active memberships joined with User
    members_data = session.exec(
        select(GroupMembership, User)
        .join(User, GroupMembership.user_id == User.id)
        .where(
            GroupMembership.group_id == group_id,
            GroupMembership.status == "ACTIVE"
        )
    ).all()

    # 3. Fetch obligations for this day or active cycle
    if rotating:
        target_cycle = rotating.current_cycle or 1
        obligations = session.exec(
            select(MemberObligation).where(
                MemberObligation.group_id == group_id,
                MemberObligation.cycle_number == target_cycle
            )
        ).all()
    else:
        obligations = session.exec(
            select(MemberObligation).where(
                MemberObligation.group_id == group_id,
                MemberObligation.due_date >= day_start_ms,
                MemberObligation.due_date <= day_end_ms
            )
        ).all()
    obligations_by_user: Dict[uuid.UUID, MemberObligation] = {ob.user_id: ob for ob in obligations}

    # If default_target is 0, check if obligations have an amount_due
    if default_target == 0 and obligations:
        default_target = max(ob.amount_due for ob in obligations)

    # 4. Fetch deposits settled today from LedgerEntry
    deposits = session.exec(
        select(LedgerEntry).where(
            LedgerEntry.group_id == group_id,
            LedgerEntry.transaction_type == "DEPOSIT",
            LedgerEntry.status == "SETTLED",
            LedgerEntry.settled_at >= day_start_ms,
            LedgerEntry.settled_at <= day_end_ms
        )
    ).all()

    # Aggregate deposits per user
    user_deposits_today: Dict[uuid.UUID, List[LedgerEntry]] = {}
    for dep in deposits:
        if dep.user_id:
            user_deposits_today.setdefault(dep.user_id, []).append(dep)

    records: List[Dict[str, Any]] = []

    for membership, user in members_data:
        ob = obligations_by_user.get(user.id)
        amount_required = ob.amount_due if ob else default_target
        
        user_deps = user_deposits_today.get(user.id, [])
        ledger_paid = sum(d.amount for d in user_deps)
        
        # Consider amount_paid on obligation if recorded directly
        ob_paid = ob.amount_paid if ob else 0
        amount_paid = max(ledger_paid, ob_paid)
        
        latest_settled_at = max((d.settled_at for d in user_deps if d.settled_at), default=None)
        if not latest_settled_at and ob and ob.status == "PAID":
            latest_settled_at = ob.updated_at

        # Classification
        if amount_required > 0 and amount_paid >= amount_required:
            status = "FULL"
        elif amount_paid > 0:
            status = "PARTIAL"
        else:
            status = "NOT_DEPOSITED"

        pct = min(100.0, round((amount_paid / amount_required * 100.0), 1)) if amount_required > 0 else (100.0 if amount_paid > 0 else 0.0)
        remaining = max(0, amount_required - amount_paid)

        # Phone masking
        phone_display = user.phone_number
        if hide_contact_info and caller_role != "ADMIN":
            phone_display = mask_phone_number(user.phone_number)

        records.append({
            "user_id": str(user.id),
            "membership_id": membership.membership_id,
            "full_name": user.full_name or "Member",
            "profile_picture_url": user.profile_picture_url,
            "avatar_color": user.avatar_color or "#00D664",
            "phone_number": phone_display,
            "role": membership.role,
            "is_online": bool(user.is_online),
            "last_seen_at": user.last_seen_at,
            "amount_required": amount_required,
            "amount_paid": amount_paid,
            "amount_remaining": remaining,
            "percentage_paid": pct,
            "status": status,
            "settled_at": latest_settled_at,
            "can_nudge": (status != "FULL")
        })

    return default_target, records

def get_daily_deposit_widget_summary(
    session: Session,
    group_id: str,
    current_user: User,
    date_ms: Optional[int] = None
) -> Dict[str, Any]:
    """Returns the high-level summary counts and totals for the deposit widget."""
    membership, vis_settings = verify_deposit_widget_access(session, group_id, current_user.id)
    day_start_ms, day_end_ms, date_str = get_day_window(date_ms)
    
    hide_contacts = getattr(vis_settings, "hide_member_contact_info", True) if vis_settings else True
    target_amount, records = _compute_member_deposit_states(
        session, group_id, day_start_ms, day_end_ms, membership.role, hide_contacts
    )

    full_members = [r for r in records if r["status"] == "FULL"]
    partial_members = [r for r in records if r["status"] == "PARTIAL"]
    not_deposited_members = [r for r in records if r["status"] == "NOT_DEPOSITED"]

    total_members = len(records)
    total_expected = sum(r["amount_required"] for r in records)
    total_collected = sum(r["amount_paid"] for r in records)
    collection_rate = round((total_collected / total_expected * 100.0), 1) if total_expected > 0 else 0.0

    return {
        "status": "success",
        "data": {
            "group_id": group_id,
            "date": date_str,
            "target_amount_per_member": target_amount,
            "total_members": total_members,
            "summary": {
                "full": {
                    "count": len(full_members),
                    "total_amount": sum(r["amount_paid"] for r in full_members),
                    "percentage_of_members": round(len(full_members) / total_members * 100.0, 1) if total_members > 0 else 0.0
                },
                "partial": {
                    "count": len(partial_members),
                    "total_amount": sum(r["amount_paid"] for r in partial_members),
                    "percentage_of_members": round(len(partial_members) / total_members * 100.0, 1) if total_members > 0 else 0.0
                },
                "not_deposited": {
                    "count": len(not_deposited_members),
                    "total_amount": 0,
                    "percentage_of_members": round(len(not_deposited_members) / total_members * 100.0, 1) if total_members > 0 else 0.0
                }
            },
            "overall": {
                "total_expected": total_expected,
                "total_collected": total_collected,
                "collection_rate": collection_rate
            },
            "permissions": {
                "user_role": membership.role,
                "visibility_setting": getattr(vis_settings, "deposit_widget_visibility", "ALL_MEMBERS") if vis_settings else "ALL_MEMBERS",
                "can_view": True
            }
        }
    }

def get_daily_deposit_widget_members(
    session: Session,
    group_id: str,
    current_user: User,
    status_filter: str = "FULL",
    date_ms: Optional[int] = None
) -> Dict[str, Any]:
    """Returns the drill-down list of members filtered by status (FULL, PARTIAL, NOT_DEPOSITED, ALL)."""
    membership, vis_settings = verify_deposit_widget_access(session, group_id, current_user.id)
    day_start_ms, day_end_ms, date_str = get_day_window(date_ms)
    
    hide_contacts = getattr(vis_settings, "hide_member_contact_info", True) if vis_settings else True
    target_amount, records = _compute_member_deposit_states(
        session, group_id, day_start_ms, day_end_ms, membership.role, hide_contacts
    )

    filter_upper = status_filter.upper()
    if filter_upper == "HALF":
        filter_upper = "PARTIAL"

    if filter_upper != "ALL":
        filtered_records = [r for r in records if r["status"] == filter_upper]
    else:
        filtered_records = records

    # Sort: FULL by settled_at desc, NOT_DEPOSITED by full_name asc
    if filter_upper == "FULL":
        filtered_records.sort(key=lambda x: x["settled_at"] or 0, reverse=True)
    else:
        filtered_records.sort(key=lambda x: x["full_name"])

    return {
        "status": "success",
        "data": {
            "group_id": group_id,
            "date": date_str,
            "filter_status": filter_upper,
            "count": len(filtered_records),
            "members": filtered_records
        }
    }
