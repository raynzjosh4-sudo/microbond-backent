import time
import uuid
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlmodel import Session, select
from app.core.database import get_session
from app.api.dependencies import get_current_user
from app.models.user.user import User
from app.models.group.group import GroupMembership
from app.models.group.auction import GroupAuction
from app.services.websocket_manager import ws_manager
from .schemas import StartAuctionRequest

router = APIRouter()

@router.post("/{group_id}/auctions/start", summary="Start a live auction for a payout cycle")
def start_auction(
    group_id: str,
    request: StartAuctionRequest,
    background_tasks: BackgroundTasks,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """
    Starts a new live auction for a given cycle number in a rotating group.
    Only the Group Admin can start an auction.
    """
    # 1. Verify Membership and Role
    membership = session.exec(
        select(GroupMembership).where(
            GroupMembership.group_id == group_id,
            GroupMembership.user_id == current_user.id,
            GroupMembership.status == "ACTIVE"
        )
    ).first()
    
    if not membership or membership.role != "ADMIN":
        raise HTTPException(status_code=403, detail="Only the Group Admin can start an auction.")

    current_time = int(time.time() * 1000)

    # 2. Check if an active auction is already running for this group
    existing_active = session.exec(
        select(GroupAuction).where(
            GroupAuction.group_id == group_id,
            GroupAuction.status == "ACTIVE"
        )
    ).first()

    if existing_active:
        if current_time < existing_active.end_time:
            raise HTTPException(
                status_code=400,
                detail=f"An active auction ({existing_active.auction_id}) for cycle {existing_active.cycle_number} is already running."
            )
        else:
            # Mark expired auction as CLOSED
            existing_active.status = "CLOSED"
            session.add(existing_active)
            session.commit()

    # 3. Create the new GroupAuction
    end_time = current_time + (request.duration_minutes * 60 * 1000)
    new_auction = GroupAuction(
        auction_id=str(uuid.uuid4()),
        group_id=group_id,
        cycle_number=request.cycle_number,
        start_time=current_time,
        end_time=end_time,
        status="ACTIVE"
    )
    session.add(new_auction)
    session.commit()
    session.refresh(new_auction)

    # 4. Broadcast AUCTION_STARTED via WebSocket
    background_tasks.add_task(
        ws_manager.broadcast_to_group,
        group_id,
        {
            "event_type": "AUCTION_STARTED",
            "auction_id": new_auction.auction_id,
            "cycle_number": new_auction.cycle_number,
            "start_time": new_auction.start_time,
            "end_time": new_auction.end_time
        }
    )

    return {
        "status": "success",
        "message": "Auction started successfully!",
        "data": {
            "auction_id": new_auction.auction_id,
            "group_id": new_auction.group_id,
            "cycle_number": new_auction.cycle_number,
            "start_time": new_auction.start_time,
            "end_time": new_auction.end_time,
            "status": new_auction.status
        }
    }
