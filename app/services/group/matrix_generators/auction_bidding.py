from datetime import datetime, timezone
import json
from sqlalchemy.orm import Session

from app.models.group.group import GroupMembership
from app.models.group.finance import MemberObligation, GroupPayout
from app.core.microbond_core import generate_cycle_matrix


def generate_auction_bidding_matrix(
    session: Session,
    group_id: str,
    members: list[GroupMembership],
    settings,
    details,
    start_date: datetime,
) -> int:
    """
    Generates the financial matrix for a Bidding/Auction group using the microbond_core domain engine.
    Payouts are generated with NULL user_id and AUCTION_PENDING status for subsequent member bidding.
    """
    if not members:
        return 0

    current_time_epoch = int(datetime.now(timezone.utc).timestamp())
    member_user_ids = [str(m.user_id) for m in members]

    reserve_fund_bps = int(round((getattr(settings, "reserve_fund_percentage", 0.0) or 0.0) * 10_000))
    payouts_per_cycle = getattr(details, "payouts_per_cycle", 1) or 1
    collection_frequency_days = getattr(details, "collection_frequency_days", 7) or 7
    contribution_amount = int(getattr(details, "contribution_amount", 0) or 0)
    start_epoch = int(start_date.timestamp())

    matrix_json = generate_cycle_matrix(
        member_user_ids=member_user_ids,
        group_type="BIDDING",
        contribution_minor=contribution_amount,
        payouts_per_cycle=payouts_per_cycle,
        reserve_fund_bps=reserve_fund_bps,
        collection_frequency_days=collection_frequency_days,
        start_epoch_seconds=start_epoch,
        created_at_epoch_seconds=current_time_epoch,
    )
    matrix_data = json.loads(matrix_json)

    raw_obligations = matrix_data.get("obligations", [])
    raw_payouts = matrix_data.get("payouts", [])

    obligations = [
        {
            "group_id": group_id,
            "user_id": o["user_id"],
            "cycle_number": o["cycle_number"],
            "amount_due": o["amount_due"],
            "amount_paid": o.get("amount_paid", 0),
            "due_date": o["due_date"],
            "status": o.get("status", "PENDING"),
            "created_at": o.get("created_at", current_time_epoch),
            "updated_at": o.get("updated_at", current_time_epoch),
        }
        for o in raw_obligations
    ]

    payouts = [
        {
            "group_id": group_id,
            "user_id": p["user_id"],
            "cycle_number": p["cycle_number"],
            "amount_expected": p["amount_expected"],
            "amount_received": p.get("amount_received", p.get("amount_collected", 0)),
            "status": p.get("status", "PENDING"),
            "payout_date": p["payout_date"],
            "created_at": p.get("created_at", current_time_epoch),
        }
        for p in raw_payouts
    ]

    if obligations:
        session.bulk_insert_mappings(MemberObligation, obligations)
    if payouts:
        session.bulk_insert_mappings(GroupPayout, payouts)

    return matrix_data.get("num_cycles", 0)

