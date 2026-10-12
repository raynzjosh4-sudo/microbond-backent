from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from pydantic import BaseModel, Field
from sqlmodel import Session, select
from typing import Optional, List, Dict, Any
import time
import uuid

from app.core.database import get_session
from app.api.dependencies import get_current_user
from app.models.user.user import User
from app.models.group.group import GroupMembership
from app.models.group.auction import GroupAuction, AuctionBid
from app.services.websocket_manager import ws_manager

# No prefix here because it is mounted inside rotating_endpoints.py which already has prefix="/api/v1/groups/rotating"
router = APIRouter(tags=["Rotating Auctions"])


class StartAuctionRequest(BaseModel):
    cycle_number: int = Field(default=1, ge=1, description="Cycle number for the payout auction")
    duration_minutes: int = Field(default=60, ge=1, le=10080, description="Auction duration in minutes (default 60)")


class SubmitBidRequest(BaseModel):
    bid_amount: float = Field(..., gt=0, description="The discount amount the user is bidding")


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
        
    if auction.status != "ACTIVE":
        raise HTTPException(status_code=400, detail=f"Auction is currently {auction.status}.")
        
    if current_time >= auction.end_time:
        # Time ran out before they locked the row
        auction.status = "CLOSED"
        session.commit()
        raise HTTPException(status_code=400, detail="The bidding window has closed.")

    # 3. Check current highest bid (Inside the lock)
    highest_bid = session.query(AuctionBid).filter(
        AuctionBid.auction_id == auction_id,
        AuctionBid.status == "ACTIVE"
    ).order_by(AuctionBid.bid_amount.desc()).first()

    if highest_bid:
        if request.bid_amount <= highest_bid.bid_amount:
            # Rejects identical tie-bids immediately
            raise HTTPException(
                status_code=400, 
                detail=f"A bid of {highest_bid.bid_amount} or higher already exists. Please submit a higher bid."
            )
        
        # Mark the previous winner as OUTBID
        highest_bid.status = "OUTBID"
        session.add(highest_bid)
        
        # Notify the outbid user instantly via WebSocket
        background_tasks.add_task(
            ws_manager.broadcast_to_group,
            group_id,
            {"event_type": "USER_OUTBID", "user_id": highest_bid.user_id, "amount": highest_bid.bid_amount}
        )

    # 4. Save the new winning bid
    new_bid = AuctionBid(
        auction_id=auction_id,
        user_id=str(current_user.id),
        bid_amount=request.bid_amount,
        status="ACTIVE"
    )
    session.add(new_bid)

    # 5. Anti-Sniping (Popcorn Bidding Rule)
    # If the bid is placed with less than 60 seconds remaining, extend the clock by exactly 60 seconds.
    time_remaining_ms = auction.end_time - current_time
    if time_remaining_ms < 60_000:
        auction.end_time = current_time + 60_000 # Reset clock to exactly 60s from now
        session.add(auction)
        
        # Notify everyone that the clock was extended
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
