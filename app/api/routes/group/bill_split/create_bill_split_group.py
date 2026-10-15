import uuid
from fastapi import APIRouter, Depends, status
from sqlmodel import Session
from app.core.database import get_session
from app.api.dependencies import get_current_user
from app.models.user.user import User
from app.models.group.group import Group, GroupMembership
from app.models.group.settings import GroupFinancialSettings, GroupGovernanceSettings, GroupCommunicationSettings, GroupVisibilitySettings
from app.models.group.bill_split import BillSplitConfig, BillSplitOperationalSettings, BillSplitMemberShare
from .schemas import BillSplitCreateRequest

router = APIRouter()

@router.post("/create", status_code=status.HTTP_201_CREATED)
def create_bill_split_group(
    request: BillSplitCreateRequest,
    db: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """
    Create a new BILL_SPLIT group.
    - Creates the base Group record (type='BILL_SPLIT', payment_mode='OBLIGATION').
    - Inserts immutable BillSplitConfig (total amount, payee, settlement deadline).
    - Inserts mutable BillSplitOperationalSettings (tip rules, auto-close, late fees).
    - Creates base GroupFinancialSettings and GroupOperationalSettings.
    - Assigns creator as ADMIN and initializes member share record.
    """
    group_id = str(uuid.uuid4())
    invite_code = str(uuid.uuid4())[:8].upper()

    # 1. Base Group
    group = Group(
        group_id=group_id,
        name=request.name,
        description=request.description or "",
        group_image_url=request.group_image_url or "",
        type="BILL_SPLIT",
        payment_mode="OBLIGATION",
        savings_term="SHORT_TERM",
        visibility=request.visibility,
        currency=request.currency,
        created_by_user_id=current_user.id,
        invite_code=invite_code,
        member_count=1,
        total_balance=0,
    )
    db.add(group)

    # 2. Creator Membership
    membership = GroupMembership(
        membership_id=str(uuid.uuid4()),
        group_id=group_id,
        user_id=current_user.id,
        role="ADMIN",
        title="Organizer",
        status="ACTIVE"
    )
    db.add(membership)

    # 3. BillSplitConfig (Immutable)
    config = BillSplitConfig(
        group_id=group_id,
        total_bill_amount=request.total_bill_amount,
        split_mode=request.split_mode,
        settlement_deadline=request.settlement_deadline,
        bill_category=request.bill_category,
        payout_destination_type=request.payout_destination_type,
        payee_identifier=request.payee_identifier,
        payee_name=request.payee_name,
        bill_receipt_url=request.bill_receipt_url,
    )
    db.add(config)

    # 4. BillSplitOperationalSettings (Mutable)
    ops = BillSplitOperationalSettings(
        group_id=group_id,
        allow_tip_or_extra=request.allow_tip_or_extra,
        auto_close_on_settlement=request.auto_close_on_settlement,
        send_reminder_hours_before=request.send_reminder_hours_before,
        enable_late_fees=request.enable_late_fees,
        late_fee_amount=request.late_fee_amount,
        grace_period_hours=request.grace_period_hours,
        is_settled=False,
        total_collected=0,
        total_tip_collected=0,
    )
    db.add(ops)

    # 5. Base Settings (Synchronized)
    fin_settings = GroupFinancialSettings(
        group_id=group_id,
        enable_late_fees=request.enable_late_fees,
        late_fee_amount=float(request.late_fee_amount),
        grace_period_hours=request.grace_period_hours,
    )
    db.add(fin_settings)
    db.add(GroupGovernanceSettings(group_id=group_id))
    db.add(GroupCommunicationSettings(group_id=group_id))
    db.add(GroupVisibilitySettings(group_id=group_id))

    # 6. Initialize Creator's Share
    creator_assigned = request.total_bill_amount
    if request.member_allocations:
        for alloc in request.member_allocations:
            if alloc.user_id == current_user.id:
                creator_assigned = alloc.assigned_amount
                break

    creator_share = BillSplitMemberShare(
        group_id=group_id,
        user_id=current_user.id,
        assigned_amount=creator_assigned,
        amount_paid=0,
        tip_paid=0,
        is_settled=False,
    )
    db.add(creator_share)

    # Additional member shares if allocated upfront
    if request.member_allocations:
        for alloc in request.member_allocations:
            if alloc.user_id != current_user.id:
                member_share = BillSplitMemberShare(
                    group_id=group_id,
                    user_id=alloc.user_id,
                    assigned_amount=alloc.assigned_amount,
                    amount_paid=0,
                    tip_paid=0,
                    is_settled=False,
                )
                db.add(member_share)

    db.commit()

    return {
        "status": "success",
        "group_id": group_id,
        "invite_code": invite_code,
        "message": "Bill Split group created successfully"
    }
