import math
import pandas as pd
from datetime import datetime
import pytz
from sqlalchemy.orm import Session

from app.models.group.group import GroupMembership
from app.models.group.finance import MemberObligation, GroupPayout

def generate_auction_bidding_matrix(session: Session, group_id: str, members: list[GroupMembership], settings, details, start_date: datetime):
    """
    Generates the financial matrix for a Bidding/Auction group.
    Leak 3 Fix: Payouts are generated with NULL recipient_user_id. The members will bid on them later!
    """
    
    member_count = len(members)
    payouts_per_cycle = details.payouts_per_cycle or 1
    num_cycles = math.ceil(member_count / payouts_per_cycle)
    
    gross_pool = details.contribution_amount * member_count
    reserve_percentage = settings.reserve_fund_percentage or 0.0
    net_payout = gross_pool * (1.0 - reserve_percentage)
    
    kampala_tz = pytz.timezone("Africa/Kampala")
    start_date_kampala = start_date.astimezone(kampala_tz)
    
    deadlines = pd.date_range(
        start=start_date_kampala, 
        periods=num_cycles, 
        freq=f"{details.collection_frequency_days}D",
        tz="Africa/Kampala"
    )
    
    cycles_df = pd.DataFrame({
        "cycle_number": range(1, num_cycles + 1),
        "due_date_kampala": deadlines
    })
    cycles_df["due_date"] = cycles_df["due_date_kampala"].apply(lambda x: int(x.astimezone(pytz.UTC).timestamp()))
    members_df = pd.DataFrame([{"user_id": m.user_id, "membership_id": m.membership_id} for m in members])
    matrix_df = cycles_df.merge(members_df, how='cross')
    
    matrix_df["group_id"] = group_id
    matrix_df["amount_due"] = details.contribution_amount
    matrix_df["amount_paid"] = 0.0
    matrix_df["status"] = "PENDING"
    
    current_time_epoch = int(datetime.utcnow().timestamp())
    matrix_df["created_at"] = current_time_epoch
    matrix_df["updated_at"] = current_time_epoch
    
    obligation_cols = ["group_id", "user_id", "cycle_number", "amount_due", "amount_paid", "due_date", "status", "created_at", "updated_at"]
    obligations_records = matrix_df[obligation_cols].to_dict(orient="records")
    
    # Payouts with NO recipients
    payout_records = []
    for cycle_idx in range(num_cycles):
        cycle_number = cycle_idx + 1
        due_date_epoch = cycles_df.iloc[cycle_idx]["due_date"]
        
        for _ in range(payouts_per_cycle):
            payout_records.append({
                "group_id": group_id,
                "cycle_number": cycle_number,
                "user_id": None, # LEAK 3 FIX: NULL recipient. Bids will decide this!
                "amount_expected": net_payout,
                "amount_collected": 0.0,
                "status": "AUCTION_PENDING", # Custom status indicating it's ready for bids
                "payout_date": due_date_epoch,
                "created_at": current_time_epoch,
                "updated_at": current_time_epoch
            })
                
    if obligations_records:
        session.bulk_insert_mappings(MemberObligation, obligations_records)
    if payout_records:
        session.bulk_insert_mappings(GroupPayout, payout_records)
        
    return num_cycles
