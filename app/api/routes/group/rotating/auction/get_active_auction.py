import time
from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select
from app.core.database import get_session
from app.api.dependencies import get_current_user
from app.models.user.user import User
from app.models.group.group import GroupMembership
from app.models.group.auction import GroupAuction, AuctionBid

router = APIRouter()

@router.get("/{group_id}/auctions/active", summary="Get the currently active auction and highest bid")
def get_active_auction(
    group_id: str,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """
    Returns the currently active auction for the group, along with the highest bid and time remaining.
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
        raise HTTPException(status_code=403, detail="You must be an active member to view auctions.")

    current_time = int(time.time() * 1000)

    auction = session.exec(
        select(GroupAuction).where(
            GroupAuction.group_id == group_id,
            GroupAuction.status == "ACTIVE"
        )
    ).first()

    if not auction:
        return {
            "status": "success",
            "has_active_auction": False,
            "auction": None
        }

    # If the bidding window expired, mark as CLOSED
    if current_time >= auction.end_time:
        auction.status = "CLOSED"
        session.add(auction)
        session.commit()
        return {
            "status": "success",
            "has_active_auction": False,
            "auction": None
        }

    # Get current highest bid
    highest_bid = session.query(AuctionBid).filter(
        AuctionBid.auction_id == auction.auction_id,
        AuctionBid.status == "ACTIVE"
    ).order_by(AuctionBid.bid_amount.desc()).first()

    return {
        "status": "success",
        "has_active_auction": True,
        "auction": {
            "auction_id": auction.auction_id,
            "cycle_number": auction.cycle_number,
            "start_time": auction.start_time,
            "end_time": auction.end_time,
            "time_remaining_seconds": max(0, int((auction.end_time - current_time) / 1000)),
            "status": auction.status,
            "highest_bid": highest_bid.bid_amount if highest_bid else 0.0,
            "highest_bidder_id": highest_bid.user_id if highest_bid else None
        }
    }
