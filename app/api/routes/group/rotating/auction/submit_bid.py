import time
import json
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlmodel import Session, select
from app.core.database import get_session
from app.api.dependencies import get_current_user
from app.models.user.user import User
from app.models.group.group import GroupMembership
from app.models.group.auction import GroupAuction, AuctionBid
from app.services.websocket_manager import ws_manager
from app.core.microbond_core import validate_auction_bid
from .schemas import SubmitBidRequest

router = APIRouter()

@router.post("/{group_id}/auctions/{auction_id}/bid", summary="Submit a live bid for the payout cycle")
def submit_bid(
    group_id: str,
    auction_id: str,
    request: SubmitBidRequest,
    background_tasks: BackgroundTasks,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """
    Submits a real-time live bid for an active payout cycle auction.
    - Prevents race conditions with row-level locking (`with_for_update()`).
    - Validates membership, auction status, and higher bid amount.
    - Implements anti-sniping (popcorn bidding): extends end time by 60s if bid in final minute.
    - Broadcasts real-time events via WebSocket to all group members.
    """
    # 1. Verify Membership
    membership = session.exec(
        select(GroupMembership).where(
            GroupMembership.group_id == group_id,
            GroupMembership.user_id == current_user.id,
            GroupMembership.status == "ACTIVE"
        )
    ).first()
    
    if not membership:
        raise HTTPException(status_code=403, detail="You must be an active member to bid.")

    current_time = int(time.time() * 1000)

    # 2. ROW-LEVEL LOCKING: Prevent Millisecond Race Conditions
    # We fetch the auction with a strict FOR UPDATE lock so two simultaneous requests queue up sequentially.
    auction = session.query(GroupAuction).filter(GroupAuction.auction_id == auction_id).with_for_update().first()
    
    if not auction or auction.group_id != group_id:
        raise HTTPException(status_code=404, detail="Auction not found.")

    # 3. Check current highest bid (Inside the lock)
    highest_bid = session.query(AuctionBid).filter(
        AuctionBid.auction_id == auction_id,
        AuctionBid.status == "ACTIVE"
    ).order_by(AuctionBid.bid_amount.desc()).first()

    highest_bid_amount = highest_bid.bid_amount if highest_bid else None

    # 4. Authoritative microbond_core Validation & Anti-Sniping Popcorn Engine
    validation_raw = validate_auction_bid(
        auction_status=auction.status,
        current_time_ms=current_time,
        auction_end_time_ms=auction.end_time,
        new_bid_amount=request.bid_amount,
        current_highest_bid_amount=highest_bid_amount,
        anti_sniping_threshold_ms=60_000,
        clock_extension_ms=60_000,
    )
    val = json.loads(validation_raw)

    if not val["is_valid"]:
        if current_time >= auction.end_time:
            auction.status = "CLOSED"
            session.commit()
        raise HTTPException(status_code=400, detail=val["rejection_reason"])

    if highest_bid:
        highest_bid.status = "OUTBID"
        session.add(highest_bid)
        background_tasks.add_task(
            ws_manager.broadcast_to_group,
            group_id,
            {"event_type": "USER_OUTBID", "user_id": highest_bid.user_id, "amount": highest_bid.bid_amount}
        )

    # 5. Save the new winning bid
    new_bid = AuctionBid(
        auction_id=auction_id,
        user_id=str(current_user.id),
        bid_amount=request.bid_amount,
        status="ACTIVE"
    )
    session.add(new_bid)

    # 6. Apply Popcorn Clock Extension if triggered
    if val["clock_extended"]:
        auction.end_time = val["new_end_time"]
        session.add(auction)
        background_tasks.add_task(
            ws_manager.broadcast_to_group,
            group_id,
            {"event_type": "AUCTION_EXTENDED", "new_end_time": auction.end_time}
        )

    # Commit the transaction, releasing the lock
    session.commit()
    session.refresh(new_bid)

    # 6. Broadcast the new high score to the group chat/auction board
    background_tasks.add_task(
        ws_manager.broadcast_to_group,
        group_id,
        {
            "event_type": "NEW_HIGHEST_BID",
            "auction_id": auction_id,
            "bid_amount": new_bid.bid_amount,
            "user_id": str(current_user.id)
        }
    )

    return {
        "status": "success",
        "message": "Bid accepted!",
        "data": {
            "bid_amount": new_bid.bid_amount,
            "new_end_time": auction.end_time
        }
    }
