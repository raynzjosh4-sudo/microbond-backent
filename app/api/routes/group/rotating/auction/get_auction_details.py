from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select
from app.core.database import get_session
from app.api.dependencies import get_current_user
from app.models.user.user import User
from app.models.group.group import GroupMembership
from app.models.group.auction import GroupAuction, AuctionBid

router = APIRouter()

@router.get("/{group_id}/auctions/{auction_id}", summary="Get auction details and bid history")
def get_auction_details(
    group_id: str,
    auction_id: str,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """
    Returns full details for a specific auction, including all bids placed.
    """
    membership = session.exec(
        select(GroupMembership).where(
            GroupMembership.group_id == group_id,
            GroupMembership.user_id == current_user.id,
            GroupMembership.status == "ACTIVE"
        )
    ).first()
    
    if not membership:
        raise HTTPException(status_code=403, detail="You must be an active member to view auctions.")

    auction = session.exec(
        select(GroupAuction).where(
            GroupAuction.auction_id == auction_id,
            GroupAuction.group_id == group_id
        )
    ).first()

    if not auction:
        raise HTTPException(status_code=404, detail="Auction not found.")

    bids = session.query(AuctionBid).filter(
        AuctionBid.auction_id == auction_id
    ).order_by(AuctionBid.created_at.desc()).all()

    return {
        "status": "success",
        "data": {
            "auction": {
                "auction_id": auction.auction_id,
                "group_id": auction.group_id,
                "cycle_number": auction.cycle_number,
                "start_time": auction.start_time,
                "end_time": auction.end_time,
                "status": auction.status,
                "winning_bid_id": auction.winning_bid_id,
                "winning_user_id": auction.winning_user_id
            },
            "bids": bids
        }
    }
