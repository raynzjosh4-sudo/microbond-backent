from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import Session, select
from typing import Optional, List
from pydantic import BaseModel

from app.core.database import get_session
from app.api.dependencies import get_current_user
from app.models.user.user import User
from app.models.group.group import GroupMembership
from app.models.group.finance import MemberObligation

router = APIRouter(prefix="/api/v1/groups", tags=["Group Membership"])

class MemberListResponse(BaseModel):
    user_id: str
    full_name: str
    phone_number: str
    profile_picture_url: Optional[str]
    role: str
    is_signer: bool
    payout_position: Optional[int]
    status: str
    total_contributed: int
    trust_score: int
    joined_at: int
    outstanding_balance: float

# Dependency class to group all the advanced filters
class MemberFilterParams:
    def __init__(
        self,
        # Basic Role & Governance
        role: Optional[str] = Query(None, description="Filter by exact role (e.g., ADMIN, MEMBER)"),
        is_signer: Optional[bool] = Query(None, description="True for signers, False for non-signers"),
        
        # Financial Health
        payment_status: Optional[str] = Query(None, description="Options: 'late' (currently owes money), 'defaulted' (banned/failed), 'perfect_payer' (never late)"),
        min_total_contributed: Optional[int] = Query(None, description="Minimum total contributed amount"),
        max_total_contributed: Optional[int] = Query(None, description="Maximum total contributed amount"),
        
        # Time & Cohorts
        joined_within_days: Optional[int] = Query(None, description="Members who joined in the last X days (e.g., 30 for new members this month)"),
        inactive_for_days: Optional[int] = Query(None, description="Members whose last_seen_at is older than X days"),
        has_outstanding_balance: Optional[bool] = Query(None, description="Filter for members who owe money"),
        
        # Trust & Security
        min_trust_score: Optional[int] = Query(None, description="Minimum user trust score (e.g., 80)"),
        kyc_tier: Optional[int] = Query(None, description="Exact KYC tier (0, 1, 2, 3)"),
        
        # Sorting
        sort_by: Optional[str] = Query("joined_at_desc", description="Sort by: joined_at_desc, joined_at_asc, contribution_desc, trust_score_desc, name_asc")
    ):
        self.role = role
        self.is_signer = is_signer
        self.payment_status = payment_status
        self.min_total_contributed = min_total_contributed
        self.max_total_contributed = max_total_contributed
        self.joined_within_days = joined_within_days
        self.inactive_for_days = inactive_for_days
        self.has_outstanding_balance = has_outstanding_balance
        self.min_trust_score = min_trust_score
        self.kyc_tier = kyc_tier
        self.sort_by = sort_by

@router.get("/{group_id}/members", response_model=List[MemberListResponse], summary="Advanced List & Filter Group Members")
def list_group_members(
    group_id: str,
    filters: MemberFilterParams = Depends(),
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    import time
    current_time_ms = int(time.time() * 1000)

    # Verify the requester is actually in the group
    membership = session.exec(
        select(GroupMembership).where(
            GroupMembership.group_id == group_id,
            GroupMembership.user_id == current_user.id
        )
    ).first()
    
    if not membership:
        raise HTTPException(status_code=403, detail="You must be a member of the group to view the roster.")

    # Base query combining Member and User
    stmt = select(GroupMembership, User).join(User, GroupMembership.user_id == User.id).where(
        GroupMembership.group_id == group_id
    )

    # --- Apply Dynamic Filters ---
    
    if filters.role:
        stmt = stmt.where(GroupMembership.role == filters.role.upper())
        
    if filters.is_signer is not None:
        stmt = stmt.where(GroupMembership.is_signer == filters.is_signer)
        
    if filters.min_total_contributed is not None:
        stmt = stmt.where(GroupMembership.total_contributed >= filters.min_total_contributed)
        
    if filters.max_total_contributed is not None:
        stmt = stmt.where(GroupMembership.total_contributed <= filters.max_total_contributed)
        
    if filters.min_trust_score is not None:
        stmt = stmt.where(User.trust_score >= filters.min_trust_score)
        
    if filters.kyc_tier is not None:
        stmt = stmt.where(User.kyc_tier == filters.kyc_tier)
        
    if filters.joined_within_days is not None:
        cutoff_ms = current_time_ms - (filters.joined_within_days * 24 * 60 * 60 * 1000)
        stmt = stmt.where(GroupMembership.joined_at >= cutoff_ms)
        
    if filters.inactive_for_days is not None:
        cutoff_ms = current_time_ms - (filters.inactive_for_days * 24 * 60 * 60 * 1000)
        stmt = stmt.where(User.last_seen_at <= cutoff_ms)

    # --- Complex Subquery Filters (Payment Status) ---
    if filters.payment_status:
        if filters.payment_status == "late":
            late_users_stmt = select(MemberObligation.user_id).where(
                MemberObligation.group_id == group_id,
                MemberObligation.status == "LATE"
            ).distinct()
            late_user_ids = session.exec(late_users_stmt).all()
            if not late_user_ids:
                return []
            stmt = stmt.where(GroupMembership.user_id.in_(late_user_ids))
            
        elif filters.payment_status == "defaulted":
            defaulted_users_stmt = select(MemberObligation.user_id).where(
                MemberObligation.group_id == group_id,
                MemberObligation.status == "DEFAULTED"
            ).distinct()
            defaulted_user_ids = session.exec(defaulted_users_stmt).all()
            if not defaulted_user_ids:
                return []
            stmt = stmt.where(GroupMembership.user_id.in_(defaulted_user_ids))
            
        elif filters.payment_status == "perfect_payer":
            # Find users who have NEVER been late or defaulted in this group
            bad_payers_stmt = select(MemberObligation.user_id).where(
                MemberObligation.group_id == group_id,
                MemberObligation.status.in_(["LATE", "DEFAULTED"])
            ).distinct()
            bad_payer_ids = session.exec(bad_payers_stmt).all()
            if bad_payer_ids:
                stmt = stmt.where(GroupMembership.user_id.not_in(bad_payer_ids))
                
    if filters.has_outstanding_balance is not None:
        if filters.has_outstanding_balance:
            debtors_stmt = select(MemberObligation.user_id).where(
                MemberObligation.group_id == group_id,
                MemberObligation.amount_due > MemberObligation.amount_paid
            ).distinct()
            debtors_ids = session.exec(debtors_stmt).all()
            if not debtors_ids:
                return []
            stmt = stmt.where(GroupMembership.user_id.in_(debtors_ids))
        else:
            debtors_stmt = select(MemberObligation.user_id).where(
                MemberObligation.group_id == group_id,
                MemberObligation.amount_due > MemberObligation.amount_paid
            ).distinct()
            debtors_ids = session.exec(debtors_stmt).all()
            if debtors_ids:
                stmt = stmt.where(GroupMembership.user_id.not_in(debtors_ids))

    # --- Apply Sorting ---
    if filters.sort_by == "joined_at_desc":
        stmt = stmt.order_by(GroupMembership.joined_at.desc())
    elif filters.sort_by == "joined_at_asc":
        stmt = stmt.order_by(GroupMembership.joined_at.asc())
    elif filters.sort_by == "contribution_desc":
        stmt = stmt.order_by(GroupMembership.total_contributed.desc())
    elif filters.sort_by == "trust_score_desc":
        stmt = stmt.order_by(User.trust_score.desc())
    elif filters.sort_by == "name_asc":
        stmt = stmt.order_by(User.full_name.asc())

    # Execute
    results = session.exec(stmt).all()
    
    response_list = []
    for mem, usr in results:
        # Calculate outstanding balance
        obligations = session.exec(
            select(MemberObligation).where(
                MemberObligation.group_id == group_id,
                MemberObligation.user_id == usr.id,
                MemberObligation.amount_due > MemberObligation.amount_paid
            )
        ).all()
        outstanding_balance = sum((ob.amount_due - ob.amount_paid) for ob in obligations)
        
        response_list.append(MemberListResponse(
            user_id=str(usr.id),
            full_name=usr.full_name or "Unknown User",
            phone_number=usr.phone_number,
            profile_picture_url=usr.profile_picture_url,
            role=mem.role,
            is_signer=mem.is_signer,
            payout_position=mem.payout_position,
            status=mem.status,
            total_contributed=mem.total_contributed,
            trust_score=usr.trust_score,
            joined_at=mem.joined_at,
            outstanding_balance=outstanding_balance
        ))
        
    return response_list
