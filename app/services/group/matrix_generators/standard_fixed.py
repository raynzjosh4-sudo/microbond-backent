import math
import pandas as pd
from datetime import datetime
import pytz
from sqlalchemy.orm import Session

from app.models.group.group import GroupMembership
from app.models.group.finance import MemberObligation, GroupPayout

def generate_standard_fixed_matrix(session: Session, group_id: str, members: list[GroupMembership], settings, details, start_date: datetime):
    """
    Generates the financial matrix (Obligations + Payouts) for a standard fixed rotating group using Pandas Cartesian Joins.
    """
    
    # 1. Math: Calculate Cycles & Net Payouts
    member_count = len(members)
    payouts_per_cycle = details.payouts_per_cycle or 1
    # Leak 2 Fix: Multiple Payouts Per Cycle Calculation
    num_cycles = math.ceil(member_count / payouts_per_cycle)
    
    gross_pool = details.contribution_amount * member_count
    # Leak 1 Fix: Net Payout = Gross * (1 - Reserve Holdback)
    reserve_percentage = settings.reserve_fund_percentage or 0.0
    net_payout = gross_pool * (1.0 - reserve_percentage)
    
    # 2. Vectorized Time Math: Generate strictly anchored Kampala deadlines
    # Leak 4 Fix: Using timezone-aware generation to prevent midnight drift
    kampala_tz = pytz.timezone("Africa/Kampala")
    start_date_kampala = start_date.astimezone(kampala_tz)
    
    deadlines = pd.date_range(
        start=start_date_kampala, 
        periods=num_cycles, 
        freq=f"{details.collection_frequency_days}D",
        tz="Africa/Kampala"
    )
    
    # 3. Create DataFrames for the Cartesian Join
    cycles_df = pd.DataFrame({
        "cycle_number": range(1, num_cycles + 1),
        "due_date_kampala": deadlines
    })
    # Convert back to UTC epoch integers for database storage
    cycles_df["due_date"] = cycles_df["due_date_kampala"].apply(lambda x: int(x.astimezone(pytz.UTC).timestamp()))
    
    # Store members in a dataframe (using their UUIDs)
    members_df = pd.DataFrame([{"user_id": m.user_id, "membership_id": m.membership_id} for m in members])
    
    # 4. Cartesian Cross-Join (Creates N_members * N_cycles rows instantly in C-optimized memory)
    matrix_df = cycles_df.merge(members_df, how='cross')
    
    # Add obligation specific fields efficiently
    matrix_df["group_id"] = group_id
    matrix_df["amount_due"] = details.contribution_amount
    matrix_df["amount_paid"] = 0.0
    matrix_df["status"] = "PENDING"
    
    current_time_epoch = int(datetime.utcnow().timestamp())
    matrix_df["created_at"] = current_time_epoch
    matrix_df["updated_at"] = current_time_epoch
    
    # Filter only columns needed for MemberObligation table
    obligation_cols = ["group_id", "user_id", "cycle_number", "amount_due", "amount_paid", "due_date", "status", "created_at", "updated_at"]
    obligations_records = matrix_df[obligation_cols].to_dict(orient="records")
    
    # 5. Assign Payouts (Strategy: Iterate over the sorted list passed in)
    payout_records = []
    member_idx = 0
    for cycle_idx in range(num_cycles):
        cycle_number = cycle_idx + 1
        due_date_epoch = cycles_df.iloc[cycle_idx]["due_date"]
        
        # We assign X payouts per cycle
        for _ in range(payouts_per_cycle):
            if member_idx < member_count:
                recipient = members[member_idx]
                payout_records.append({
                    "group_id": group_id,
                    "cycle_number": cycle_number,
                    "user_id": recipient.user_id,
                    "amount_expected": net_payout,
                    "amount_collected": 0.0,
                    "status": "PENDING",
                    "payout_date": due_date_epoch, # Payout is due when collection finishes
                    "created_at": current_time_epoch,
                    "updated_at": current_time_epoch
                })
                member_idx += 1
                
    # 6. Bulk Insert to PostgreSQL in one massive transaction
    if obligations_records:
        session.bulk_insert_mappings(MemberObligation, obligations_records)
    if payout_records:
        session.bulk_insert_mappings(GroupPayout, payout_records)
        
    return num_cycles
