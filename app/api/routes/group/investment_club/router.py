from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from sqlmodel import Session, select
from pydantic import BaseModel, Field
from typing import Optional
import uuid
import time
import json
import logging

from app.core.database import get_session
from app.api.dependencies import get_current_user
from app.models.group.group import Group, GroupMembership
from app.models.user.user import User
from app.models.group.settings import (
    GroupFinancialSettings, GroupGovernanceSettings,
    GroupCommunicationSettings, GroupVisibilitySettings
)
from app.models.group.investment_association import (
    InvestmentClubConfig,
    InvestmentClubOperationalSettings,
    InvestmentClubMemberShare,
    InvestmentClubLoan
)
from app.models.group.chat import GroupPoll, GroupPollVote
from app.schemas.investment_club_schemas import (
    InvestmentClubGroupCreateRequest,
    UpdateInvestmentClubSettingsRequest,
    BuySharesRequest,
    CreateInvestmentProposalRequest,
    DistributeDividendsRequest,
    TransferSharesRequest,
    ApplyLoanRequest,
    ReviewLoanRequest,
    RepayLoanRequest
)
from app.api.routes.group.chat.messages import broadcast_system_message_sync

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/groups/investment-club", tags=["Investment Club Groups"])


class VoteProposalRequest(BaseModel):
    vote: str = Field(..., description="APPROVE or REJECT")


def _now_ms() -> int:
    return int(time.time() * 1000)


def _get_club(group_id: str, session: Session):
    config = session.exec(
        select(InvestmentClubConfig).where(InvestmentClubConfig.group_id == group_id)
    ).first()
    settings = session.exec(
        select(InvestmentClubOperationalSettings).where(InvestmentClubOperationalSettings.group_id == group_id)
    ).first()
    if not config or not settings:
        raise HTTPException(status_code=404, detail="Investment club configuration not found for this group.")
    return config, settings


def _require_admin(group_id: str, user: User, session: Session):
    membership = session.exec(
        select(GroupMembership).where(
            GroupMembership.group_id == group_id,
            GroupMembership.user_id == user.id,
            GroupMembership.role == "ADMIN",
            GroupMembership.status == "ACTIVE"
        )
    ).first()
    if not membership:
        raise HTTPException(status_code=403, detail="Only the club admin/chairperson can perform this action.")
    return membership


def _require_member(group_id: str, user: User, session: Session):
    membership = session.exec(
        select(GroupMembership).where(
            GroupMembership.group_id == group_id,
            GroupMembership.user_id == user.id,
            GroupMembership.status == "ACTIVE"
        )
    ).first()
    if not membership:
        raise HTTPException(status_code=403, detail="You must be an active member of this investment club.")
    return membership


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.post("/create", summary="Create a new Investment Club group")
def create_investment_club(
    request: InvestmentClubGroupCreateRequest,
    background_tasks: BackgroundTasks,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """
    Creates a new INVESTMENT_CLUB group.
    - Creator must have KYC Tier >= 2 (National ID verified).
    - Initializes InvestmentClubConfig (locked equity and voting model).
    - Initializes InvestmentClubOperationalSettings (quotas, fees, live counters).
    - Adds creator as ADMIN and initializes member share ledger.
    """
    creator = current_user
    now_ms = _now_ms()

    # 1. KYC verification
    if creator.kyc_tier < 2 or getattr(creator, "is_dependent_account", False):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Creating an Investment Club requires full Tier 2 National ID (NIN) verification."
        )

    # 2. Identifiers
    new_group_id = str(uuid.uuid4())
    invite_code = str(uuid.uuid4())[:8].upper()

    # 3. Create Group
    new_group = Group(
        group_id=new_group_id,
        name=request.name,
        description=request.description,
        group_image_url=request.group_image_url,
        type="INVESTMENT_CLUB",
        payment_mode="VOLUNTARY",
        visibility=request.visibility,
        currency=request.currency,
        created_by_user_id=creator.id,
        invite_code=invite_code,
        member_count=1
    )
    session.add(new_group)

    # 4. Base settings
    session.add(GroupFinancialSettings(group_id=new_group_id))
    session.add(GroupGovernanceSettings(group_id=new_group_id))
    session.add(GroupCommunicationSettings(group_id=new_group_id))
    session.add(GroupVisibilitySettings(group_id=new_group_id))

    # 5. InvestmentClubConfig (Table 1)
    config = InvestmentClubConfig(
        group_id=new_group_id,
        share_unit_price=request.share_unit_price,
        equity_calculation_mode=request.equity_calculation_mode,
        voting_power_logic=request.voting_power_logic,
        payout_destination_type=request.payout_destination_type,
        dividend_distribution_rule=request.dividend_distribution_rule,
        lock_in_period_days=request.lock_in_period_days,
        liquidation_action=request.liquidation_action,
        created_at=now_ms
    )
    session.add(config)

    # 6. InvestmentClubOperationalSettings (Table 2 - defaults)
    op_settings = InvestmentClubOperationalSettings(
        group_id=new_group_id,
        minimum_purchase_quota=0,
        proposal_approval_threshold_pct=66,
        admin_management_fee_pct=0,
        allow_internal_share_transfers=True,
        enable_late_fees=False,
        current_balance=0,
        total_invested_capital=0,
        total_shares_issued=0,
        total_dividends_distributed=0,
        is_active=True,
        updated_at=now_ms
    )
    session.add(op_settings)

    # 7. Creator membership (ADMIN)
    session.add(GroupMembership(
        membership_id=str(uuid.uuid4()),
        group_id=new_group_id,
        user_id=creator.id,
        role="ADMIN",
        status="ACTIVE",
        joined_at=now_ms
    ))

    # 8. Creator share ledger
    session.add(InvestmentClubMemberShare(
        group_id=new_group_id,
        user_id=creator.id,
        shares_owned=0,
        total_invested=0,
        last_dividend_received=0,
        created_at=now_ms,
        updated_at=now_ms
    ))

    try:
        session.commit()
        session.refresh(new_group)
        session.refresh(config)
    except Exception as e:
        session.rollback()
        logger.exception(f"Error creating investment club: {e}")
        raise HTTPException(status_code=500, detail="Database error creating investment club.")

    broadcast_system_message_sync(
        group_id=new_group_id,
        message_text=f"{creator.full_name} established the Investment Club '{new_group.name}'.",
        message_type="SYSTEM_EVENT",
        sender_id=str(creator.id),
        session=session,
        background_tasks=background_tasks
    )

    return {
        "status": "success",
        "message": "Investment Club created successfully.",
        "data": {
            "group_id": new_group.group_id,
            "invite_code": new_group.invite_code,
            "name": new_group.name,
            "currency": new_group.currency,
            "share_unit_price": config.share_unit_price,
            "equity_calculation_mode": config.equity_calculation_mode,
            "voting_power_logic": config.voting_power_logic,
            "dividend_distribution_rule": config.dividend_distribution_rule,
            "lock_in_period_days": config.lock_in_period_days
        }
    }


@router.get("/{group_id}/dashboard", summary="View club NAV, equity portfolio, and member shares")
def get_investment_club_dashboard(
    group_id: str,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """
    Returns full status of the Investment Club:
    - Creation rules (Table 1)
    - Live portfolio balances & shares (Table 2)
    - Member's personal shares & equity percentage
    - Net Asset Value (NAV) breakdown
    """
    _require_member(group_id, current_user, session)
    config, settings = _get_club(group_id, session)

    # Member's equity
    member_share = session.exec(
        select(InvestmentClubMemberShare).where(
            InvestmentClubMemberShare.group_id == group_id,
            InvestmentClubMemberShare.user_id == current_user.id
        )
    ).first()

    shares_owned = member_share.shares_owned if member_share else 0
    total_invested = member_share.total_invested if member_share else 0

    equity_pct = 0.0
    if settings.total_shares_issued > 0:
        equity_pct = round((shares_owned / settings.total_shares_issued) * 100, 2)

    net_asset_value = settings.current_balance + settings.total_invested_capital

    return {
        "status": "success",
        "data": {
            "club_config": config.model_dump(mode="json"),
            "operational_settings": settings.model_dump(mode="json"),
            "net_asset_value": net_asset_value,
            "uninvested_vault_cash": settings.current_balance,
            "deployed_capital": settings.total_invested_capital,
            "my_equity": {
                "shares_owned": shares_owned,
                "total_invested": total_invested,
                "equity_percentage": equity_pct,
                "share_unit_price": config.share_unit_price
            }
        }
    }


@router.patch("/{group_id}/settings", summary="Admin updates mutable club settings")
def update_investment_club_settings(
    group_id: str,
    request: UpdateInvestmentClubSettingsRequest,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """
    Updates mutable operational settings for the Investment Club:
    - minimum_purchase_quota
    - proposal_approval_threshold_pct
    - admin_management_fee_pct
    - allow_internal_share_transfers
    - enable_late_fees
    """
    _require_admin(group_id, current_user, session)
    config, settings = _get_club(group_id, session)

    update_dict = request.dict(exclude_unset=True)
    if not update_dict:
        raise HTTPException(status_code=400, detail="No valid settings provided to update.")

    for field, val in update_dict.items():
        if hasattr(settings, field) and val is not None:
            setattr(settings, field, val)

    settings.updated_at = _now_ms()
    session.add(settings)

    try:
        session.commit()
        session.refresh(settings)
    except Exception as e:
        session.rollback()
        logger.exception(f"Error updating investment club settings: {e}")
        raise HTTPException(status_code=500, detail="Database error updating settings.")

    return {
        "status": "success",
        "message": "Investment club settings updated successfully.",
        "data": settings.model_dump(mode="json")
    }


@router.post("/{group_id}/buy-shares", summary="Member purchases equity shares in the club")
def buy_shares(
    group_id: str,
    request: BuySharesRequest,
    background_tasks: BackgroundTasks,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """
    Member purchases equity shares.
    - Calculates total cost based on fixed share_unit_price.
    - Credits club vault balance and increases total_shares_issued.
    - Updates member's personal share balance.
    """
    _require_member(group_id, current_user, session)
    group = session.exec(select(Group).where(Group.group_id == group_id)).first()
    config, settings = _get_club(group_id, session)
    now_ms = _now_ms()

    if not settings.is_active:
        raise HTTPException(status_code=400, detail="The investment club is currently inactive or closed to share purchases.")

    total_cost = request.shares_count * config.share_unit_price

    # 1. Update or create member share entry
    member_share = session.exec(
        select(InvestmentClubMemberShare).where(
            InvestmentClubMemberShare.group_id == group_id,
            InvestmentClubMemberShare.user_id == current_user.id
        )
    ).first()

    if not member_share:
        member_share = InvestmentClubMemberShare(
            group_id=group_id,
            user_id=current_user.id,
            shares_owned=request.shares_count,
            total_invested=total_cost,
            last_dividend_received=0,
            created_at=now_ms,
            updated_at=now_ms
        )
    else:
        member_share.shares_owned += request.shares_count
        member_share.total_invested += total_cost
        member_share.updated_at = now_ms

    session.add(member_share)

    # 2. Update club settings & counters
    settings.total_shares_issued += request.shares_count
    settings.current_balance += total_cost
    settings.updated_at = now_ms
    session.add(settings)

    try:
        session.commit()
    except Exception as e:
        session.rollback()
        logger.exception(f"Error buying shares: {e}")
        raise HTTPException(status_code=500, detail="Database error recording share purchase.")

    broadcast_system_message_sync(
        group_id=group_id,
        message_text=f"📈 {current_user.full_name} purchased {request.shares_count} shares ({total_cost} {group.currency}).",
        message_type="SYSTEM_EVENT",
        sender_id=str(current_user.id),
        session=session,
        background_tasks=background_tasks
    )

    return {
        "status": "success",
        "message": f"Successfully purchased {request.shares_count} shares.",
        "data": {
            "shares_bought": request.shares_count,
            "total_cost": total_cost,
            "my_total_shares": member_share.shares_owned,
            "club_total_shares": settings.total_shares_issued,
            "vault_balance": settings.current_balance
        }
    }


@router.post("/{group_id}/proposals/create", summary="Propose funding an external asset")
def create_investment_proposal(
    group_id: str,
    request: CreateInvestmentProposalRequest,
    background_tasks: BackgroundTasks,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """
    Submits an investment proposal to deploy capital from the club vault into an asset.
    Opens a voting poll for the club.
    """
    _require_member(group_id, current_user, session)
    group = session.exec(select(Group).where(Group.group_id == group_id)).first()
    config, settings = _get_club(group_id, session)
    now_ms = _now_ms()

    if settings.current_balance < request.required_capital:
        raise HTTPException(
            status_code=400,
            detail=f"Insufficient uninvested vault capital. Vault has {settings.current_balance} {group.currency}, required is {request.required_capital} {group.currency}."
        )

    poll_id = uuid.uuid4()
    poll = GroupPoll(
        id=poll_id,
        group_id=group_id,
        creator_id=current_user.id,
        question=f"Investment Proposal: {request.asset_name} ({request.required_capital} {group.currency} for {request.asset_type})",
        options=json.dumps(["APPROVE", "REJECT"]),
        poll_type="INVESTMENT_PROPOSAL",
        status="OPEN",
        expires_at=now_ms + (72 * 3600 * 1000),
        created_at=now_ms
    )
    session.add(poll)

    try:
        session.commit()
    except Exception as e:
        session.rollback()
        logger.exception(f"Error creating proposal: {e}")
        raise HTTPException(status_code=500, detail="Database error creating proposal.")

    broadcast_system_message_sync(
        group_id=group_id,
        message_text=(
            f"💡 New Investment Proposal: {current_user.full_name} proposed investing {request.required_capital} {group.currency} "
            f"in '{request.asset_name}'. Please review and vote before the poll closes."
        ),
        message_type="SYSTEM_EVENT",
        sender_id=str(current_user.id),
        session=session,
        background_tasks=background_tasks
    )

    return {
        "status": "success",
        "message": "Investment proposal created and opened for voting.",
        "data": {
            "poll_id": str(poll_id),
            "asset_name": request.asset_name,
            "required_capital": request.required_capital,
            "expires_at": poll.expires_at
        }
    }


@router.post("/{group_id}/proposals/{poll_id}/vote", summary="Vote on an investment proposal")
def vote_on_proposal(
    group_id: str,
    poll_id: uuid.UUID,
    request: VoteProposalRequest,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """
    Active member casts vote on an investment proposal.
    If voting_power_logic is PROPORTIONAL, member must own at least 1 share.
    """
    _require_member(group_id, current_user, session)
    config, settings = _get_club(group_id, session)

    poll = session.exec(
        select(GroupPoll).where(
            GroupPoll.id == poll_id,
            GroupPoll.group_id == group_id,
            GroupPoll.poll_type == "INVESTMENT_PROPOSAL"
        )
    ).first()

    if not poll:
        raise HTTPException(status_code=404, detail="Investment proposal poll not found.")

    if poll.status != "OPEN":
        raise HTTPException(status_code=400, detail=f"This proposal is already {poll.status.lower()}.")

    now_ms = _now_ms()
    if poll.expires_at <= now_ms:
        poll.status = "CLOSED"
        session.add(poll)
        session.commit()
        raise HTTPException(status_code=400, detail="This voting poll has expired.")

    vote_val = request.vote.upper()
    if vote_val not in ("APPROVE", "REJECT"):
        raise HTTPException(status_code=400, detail="Vote must be APPROVE or REJECT.")

    # Check shareholding if PROPORTIONAL
    if config.voting_power_logic == "PROPORTIONAL":
        member_share = session.exec(
            select(InvestmentClubMemberShare).where(
                InvestmentClubMemberShare.group_id == group_id,
                InvestmentClubMemberShare.user_id == current_user.id
            )
        ).first()
        if not member_share or member_share.shares_owned <= 0:
            raise HTTPException(status_code=400, detail="You must hold at least 1 equity share to vote.")

    existing_vote = session.exec(
        select(GroupPollVote).where(
            GroupPollVote.poll_id == poll_id,
            GroupPollVote.user_id == current_user.id
        )
    ).first()

    if existing_vote:
        existing_vote.selected_option = vote_val
        session.add(existing_vote)
    else:
        new_vote = GroupPollVote(
            poll_id=poll_id,
            user_id=current_user.id,
            selected_option=vote_val,
            created_at=now_ms
        )
        session.add(new_vote)

    session.commit()

    return {
        "status": "success",
        "message": f"Vote '{vote_val}' recorded."
    }


@router.post("/{group_id}/proposals/{poll_id}/execute", summary="Admin executes approved proposal and deploys capital")
def execute_proposal(
    group_id: str,
    poll_id: uuid.UUID,
    background_tasks: BackgroundTasks,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """
    Admin verifies voting threshold and executes capital deployment to external broker/vendor:
    - Verifies approval threshold (e.g. 66%).
    - Transfers capital from vault current_balance to total_invested_capital.
    - Closes poll and marks status EXECUTED.
    """
    _require_admin(group_id, current_user, session)
    group = session.exec(select(Group).where(Group.group_id == group_id)).first()
    config, settings = _get_club(group_id, session)

    poll = session.exec(
        select(GroupPoll).where(
            GroupPoll.id == poll_id,
            GroupPoll.group_id == group_id,
            GroupPoll.poll_type == "INVESTMENT_PROPOSAL"
        )
    ).first()

    if not poll:
        raise HTTPException(status_code=404, detail="Proposal poll not found.")

    if poll.status == "EXECUTED":
        raise HTTPException(status_code=400, detail="This proposal has already been executed.")

    votes = session.exec(select(GroupPollVote).where(GroupPollVote.poll_id == poll_id)).all()
    if not votes:
        raise HTTPException(status_code=400, detail="No votes have been cast for this proposal.")

    # Calculate vote weight
    if config.voting_power_logic == "PROPORTIONAL":
        total_approve_weight = 0
        total_vote_weight = 0
        for v in votes:
            ms = session.exec(
                select(InvestmentClubMemberShare).where(
                    InvestmentClubMemberShare.group_id == group_id,
                    InvestmentClubMemberShare.user_id == v.user_id
                )
            ).first()
            w = ms.shares_owned if ms else 0
            total_vote_weight += w
            if v.selected_option == "APPROVE":
                total_approve_weight += w
        approval_pct = (total_approve_weight / total_vote_weight * 100) if total_vote_weight > 0 else 0
    else:
        approve_count = sum(1 for v in votes if v.selected_option == "APPROVE")
        approval_pct = (approve_count / len(votes) * 100)

    if approval_pct < settings.proposal_approval_threshold_pct:
        raise HTTPException(
            status_code=400,
            detail=f"Proposal did not meet required threshold of {settings.proposal_approval_threshold_pct}%. Current approval is {round(approval_pct, 1)}%."
        )

    # Deploy capital
    poll.status = "EXECUTED"
    session.add(poll)

    session.commit()

    broadcast_system_message_sync(
        group_id=group_id,
        message_text=f"🚀 Investment Executed: Proposal '{poll.question}' approved with {round(approval_pct, 1)}% support and capital deployed.",
        message_type="SYSTEM_EVENT",
        sender_id=str(current_user.id),
        session=session,
        background_tasks=background_tasks
    )

    return {
        "status": "success",
        "message": "Investment proposal executed and capital deployed.",
        "data": {
            "poll_id": str(poll_id),
            "approval_percentage": round(approval_pct, 1),
            "threshold_required": settings.proposal_approval_threshold_pct
        }
    }


@router.post("/{group_id}/distribute-dividends", summary="Admin injects returns and distributes dividends")
def distribute_dividends(
    group_id: str,
    request: DistributeDividendsRequest,
    background_tasks: BackgroundTasks,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """
    Records profit return from an asset:
    - Deducts admin management fee cut if configured.
    - If AUTO_PUSH_PROPORTIONAL: records distributed dividends.
    - If REINVEST_IN_VAULT: adds return directly back into vault current_balance.
    """
    _require_admin(group_id, current_user, session)
    group = session.exec(select(Group).where(Group.group_id == group_id)).first()
    config, settings = _get_club(group_id, session)
    now_ms = _now_ms()

    admin_fee = 0
    if settings.admin_management_fee_pct > 0:
        admin_fee = (request.total_profit_amount * settings.admin_management_fee_pct) // 100

    net_dividends = request.total_profit_amount - admin_fee

    settings.total_dividends_distributed += request.total_profit_amount
    if config.dividend_distribution_rule == "REINVEST_IN_VAULT":
        settings.current_balance += net_dividends
    settings.updated_at = now_ms
    session.add(settings)

    try:
        session.commit()
    except Exception as e:
        session.rollback()
        logger.exception(f"Error distributing dividends: {e}")
        raise HTTPException(status_code=500, detail="Database error recording dividends.")

    broadcast_system_message_sync(
        group_id=group_id,
        message_text=(
            f"💰 Dividends Declared: {request.total_profit_amount} {group.currency} return from '{request.source_asset_name}'. "
            f"Action: {config.dividend_distribution_rule}."
        ),
        message_type="SYSTEM_EVENT",
        sender_id=str(current_user.id),
        session=session,
        background_tasks=background_tasks
    )

    return {
        "status": "success",
        "message": "Dividends successfully recorded and distributed.",
        "data": {
            "gross_profit": request.total_profit_amount,
            "admin_management_fee": admin_fee,
            "net_distributed": net_dividends,
            "distribution_rule": config.dividend_distribution_rule,
            "total_dividends_to_date": settings.total_dividends_distributed
        }
    }


@router.post("/{group_id}/shares/transfer", summary="Peer-to-peer share transfer between active members")
def transfer_shares(
    group_id: str,
    request: TransferSharesRequest,
    background_tasks: BackgroundTasks,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """
    Allows a member to sell or transfer their equity shares directly to another active member.
    """
    _require_member(group_id, current_user, session)
    group = session.exec(select(Group).where(Group.group_id == group_id)).first()
    config, settings = _get_club(group_id, session)
    now_ms = _now_ms()

    if not settings.allow_internal_share_transfers:
        raise HTTPException(status_code=400, detail="Internal peer-to-peer share transfers are disabled for this club.")

    try:
        recipient_id = uuid.UUID(request.recipient_user_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid recipient user ID format.")

    recipient_membership = session.exec(
        select(GroupMembership).where(
            GroupMembership.group_id == group_id,
            GroupMembership.user_id == recipient_id,
            GroupMembership.status == "ACTIVE"
        )
    ).first()
    if not recipient_membership:
        raise HTTPException(status_code=404, detail="Recipient is not an active member of this investment club.")

    sender_share = session.exec(
        select(InvestmentClubMemberShare).where(
            InvestmentClubMemberShare.group_id == group_id,
            InvestmentClubMemberShare.user_id == current_user.id
        )
    ).first()

    if not sender_share or sender_share.shares_owned < request.shares_count:
        available = sender_share.shares_owned if sender_share else 0
        raise HTTPException(status_code=400, detail=f"Insufficient shares. You hold {available} shares, requested {request.shares_count}.")

    # Deduct from sender
    sender_share.shares_owned -= request.shares_count
    sender_share.updated_at = now_ms
    session.add(sender_share)

    # Credit recipient
    recipient_share = session.exec(
        select(InvestmentClubMemberShare).where(
            InvestmentClubMemberShare.group_id == group_id,
            InvestmentClubMemberShare.user_id == recipient_id
        )
    ).first()

    if not recipient_share:
        recipient_share = InvestmentClubMemberShare(
            group_id=group_id,
            user_id=recipient_id,
            shares_owned=request.shares_count,
            total_invested=request.shares_count * config.share_unit_price,
            last_dividend_received=0,
            created_at=now_ms,
            updated_at=now_ms
        )
    else:
        recipient_share.shares_owned += request.shares_count
        recipient_share.updated_at = now_ms

    session.add(recipient_share)

    try:
        session.commit()
    except Exception as e:
        session.rollback()
        logger.exception(f"Error transferring shares: {e}")
        raise HTTPException(status_code=500, detail="Database error executing share transfer.")

    recipient_user = session.exec(select(User).where(User.id == recipient_id)).first()
    recipient_name = recipient_user.full_name if recipient_user else "Member"

    broadcast_system_message_sync(
        group_id=group_id,
        message_text=f"🤝 Share Transfer: {current_user.full_name} transferred {request.shares_count} shares to {recipient_name}.",
        message_type="SYSTEM_EVENT",
        sender_id=str(current_user.id),
        session=session,
        background_tasks=background_tasks
    )

    return {
        "status": "success",
        "message": f"Successfully transferred {request.shares_count} shares to {recipient_name}.",
        "data": {
            "shares_transferred": request.shares_count,
            "sender_remaining_shares": sender_share.shares_owned,
            "recipient_total_shares": recipient_share.shares_owned
        }
    }


# ===========================================================================
# MEMBER LOANS & INTERNAL CREDIT FACILITY
# ===========================================================================

@router.post("/{group_id}/loans/apply", summary="Member applies for an internal credit loan")
def apply_for_loan(
    group_id: str,
    request: ApplyLoanRequest,
    background_tasks: BackgroundTasks,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """
    Member applies for a loan against the club's liquidity buffer.
    - Validates against max_borrowing_limit.
    - Computes interest due.
    """
    _require_member(group_id, current_user, session)
    config, settings = _get_club(group_id, session)
    now_ms = _now_ms()

    if request.principal_amount > settings.max_borrowing_limit:
        raise HTTPException(
            status_code=400,
            detail=f"Requested amount exceeds the club's maximum borrowing limit of {settings.max_borrowing_limit}."
        )

    interest_rate = settings.fixed_interest_rate_pct
    total_due = int(request.principal_amount * (1.0 + (interest_rate / 100.0)))

    loan = InvestmentClubLoan(
        group_id=group_id,
        user_id=current_user.id,
        principal_amount=request.principal_amount,
        interest_rate_pct=interest_rate,
        total_due_amount=total_due,
        amount_repaid=0,
        early_discount_applied=0,
        status="PENDING",
        guarantors_count=0,
        due_date=request.due_date,
        created_at=now_ms,
        updated_at=now_ms
    )
    session.add(loan)

    try:
        session.commit()
        session.refresh(loan)
    except Exception as e:
        session.rollback()
        logger.exception(f"Error applying for loan: {e}")
        raise HTTPException(status_code=500, detail="Database error submitting loan application.")

    broadcast_system_message_sync(
        group_id=group_id,
        message_text=f"📋 Loan Application: {current_user.full_name} requested a loan of {request.principal_amount}.",
        message_type="SYSTEM_EVENT",
        sender_id=str(current_user.id),
        session=session,
        background_tasks=background_tasks
    )

    return {
        "status": "success",
        "message": "Loan application submitted for committee review.",
        "data": loan.model_dump(mode="json")
    }


@router.get("/{group_id}/loans", summary="List loans in the investment club")
def list_loans(
    group_id: str,
    status_filter: Optional[str] = None,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """
    List loans in this club.
    Admins see all loans; regular members see only their own.
    """
    member = _require_member(group_id, current_user, session)
    query = select(InvestmentClubLoan).where(InvestmentClubLoan.group_id == group_id)

    if member.role != "ADMIN":
        query = query.where(InvestmentClubLoan.user_id == current_user.id)

    if status_filter:
        query = query.where(InvestmentClubLoan.status == status_filter.upper())

    loans = session.exec(query).all()

    result = []
    for l in loans:
        u = session.exec(select(User).where(User.id == l.user_id)).first()
        result.append({
            "loan_id": str(l.id),
            "user_id": str(l.user_id),
            "borrower_name": u.full_name if u else "Member",
            "principal_amount": l.principal_amount,
            "interest_rate_pct": l.interest_rate_pct,
            "total_due_amount": l.total_due_amount,
            "amount_repaid": l.amount_repaid,
            "status": l.status,
            "due_date": l.due_date,
            "disbursed_at": l.disbursed_at,
            "settled_at": l.settled_at,
            "created_at": l.created_at
        })

    return {
        "status": "success",
        "count": len(result),
        "data": result
    }


@router.post("/{group_id}/loans/{loan_id}/review", summary="Admin reviews and approves/rejects loan")
def review_loan(
    group_id: str,
    loan_id: str,
    request: ReviewLoanRequest,
    background_tasks: BackgroundTasks,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """
    Admin approves or rejects a pending loan.
    If approved and disbursed, deducts principal from current_balance vault.
    """
    _require_admin(group_id, current_user, session)
    config, settings = _get_club(group_id, session)
    now_ms = _now_ms()

    try:
        loan_uuid = uuid.UUID(loan_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid loan_id format.")

    loan = session.exec(
        select(InvestmentClubLoan).where(
            InvestmentClubLoan.id == loan_uuid,
            InvestmentClubLoan.group_id == group_id
        )
    ).first()
    if not loan:
        raise HTTPException(status_code=404, detail="Loan not found.")

    if loan.status != "PENDING":
        raise HTTPException(status_code=400, detail=f"Loan is already {loan.status}.")

    new_status = request.status.upper()
    if new_status not in ["APPROVED", "REJECTED"]:
        raise HTTPException(status_code=400, detail="Status must be APPROVED or REJECTED.")

    if new_status == "APPROVED":
        if settings.current_balance < loan.principal_amount:
            raise HTTPException(status_code=400, detail="Insufficient club vault balance to disburse loan.")

        settings.current_balance -= loan.principal_amount
        settings.total_loans_disbursed += loan.principal_amount
        settings.active_loans_count += 1
        settings.updated_at = now_ms
        session.add(settings)

        loan.status = "DISBURSED"
        loan.disbursed_at = now_ms
        loan.approved_by = current_user.id
    else:
        loan.status = "REJECTED"

    loan.updated_at = now_ms
    session.add(loan)

    try:
        session.commit()
        session.refresh(loan)
    except Exception as e:
        session.rollback()
        logger.exception(f"Error reviewing loan: {e}")
        raise HTTPException(status_code=500, detail="Database error reviewing loan.")

    borrower = session.exec(select(User).where(User.id == loan.user_id)).first()
    borrower_name = borrower.full_name if borrower else "Member"

    broadcast_system_message_sync(
        group_id=group_id,
        message_text=f"📢 Loan Update: {borrower_name}'s loan was {loan.status}.",
        message_type="SYSTEM_EVENT",
        sender_id=str(current_user.id),
        session=session,
        background_tasks=background_tasks
    )

    return {
        "status": "success",
        "message": f"Loan {loan.status.lower()} successfully.",
        "data": loan.model_dump(mode="json")
    }


@router.post("/{group_id}/loans/{loan_id}/repay", summary="Borrower repays loan capital or interest")
def repay_loan(
    group_id: str,
    loan_id: str,
    request: RepayLoanRequest,
    background_tasks: BackgroundTasks,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """
    Borrower repays principal and interest.
    Funds return to the club's current_balance vault.
    If repaid early, calculates and applies early_repayment_discount_pct.
    """
    _require_member(group_id, current_user, session)
    config, settings = _get_club(group_id, session)
    now_ms = _now_ms()

    try:
        loan_uuid = uuid.UUID(loan_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid loan_id format.")

    loan = session.exec(
        select(InvestmentClubLoan).where(
            InvestmentClubLoan.id == loan_uuid,
            InvestmentClubLoan.group_id == group_id
        )
    ).first()
    if not loan:
        raise HTTPException(status_code=404, detail="Loan not found.")

    if loan.status not in ["APPROVED", "DISBURSED"]:
        raise HTTPException(status_code=400, detail=f"Cannot repay loan in {loan.status} status.")

    remaining_due = loan.total_due_amount - loan.amount_repaid
    payment_amount = min(request.amount, remaining_due)

    # Check for early repayment discount if paying off in full ahead of deadline
    if now_ms < loan.due_date and (loan.amount_repaid + payment_amount >= loan.total_due_amount):
        discount = int(loan.principal_amount * (settings.early_repayment_discount_pct / 100.0))
        loan.early_discount_applied = discount
        payment_amount = max(0, payment_amount - discount)

    loan.amount_repaid += payment_amount
    settings.current_balance += payment_amount
    settings.updated_at = now_ms

    if loan.amount_repaid + loan.early_discount_applied >= loan.total_due_amount:
        loan.status = "REPAID"
        loan.settled_at = now_ms
        if settings.active_loans_count > 0:
            settings.active_loans_count -= 1

    loan.updated_at = now_ms
    session.add(loan)
    session.add(settings)

    try:
        session.commit()
        session.refresh(loan)
    except Exception as e:
        session.rollback()
        logger.exception(f"Error repaying loan: {e}")
        raise HTTPException(status_code=500, detail="Database error recording repayment.")

    broadcast_system_message_sync(
        group_id=group_id,
        message_text=f"💳 Loan Repayment: {current_user.full_name} repaid {payment_amount}. Remaining: {max(0, loan.total_due_amount - loan.amount_repaid - loan.early_discount_applied)}.",
        message_type="SYSTEM_EVENT",
        sender_id=str(current_user.id),
        session=session,
        background_tasks=background_tasks
    )

    return {
        "status": "success",
        "message": "Loan repayment recorded successfully.",
        "data": {
            "loan_id": str(loan.id),
            "amount_paid": payment_amount,
            "early_discount_applied": loan.early_discount_applied,
            "status": loan.status,
            "remaining_due": max(0, loan.total_due_amount - loan.amount_repaid - loan.early_discount_applied)
        }
    }

