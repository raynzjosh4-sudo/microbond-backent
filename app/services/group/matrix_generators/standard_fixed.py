from datetime import datetime, timezone
import json
import uuid
from sqlalchemy.orm import Session

from app.models.group.group import GroupMembership
from app.models.group.finance import MemberObligation, GroupPayout
from app.core.microbond_core import generate_cycle_matrix


def generate_standard_fixed_matrix(
    session: Session,
    group_id: str,
    members: list[GroupMembership],
    settings,
    details,
    start_date: datetime,
) -> int:
    """
    Generates the financial matrix (Obligations + Payouts) for a standard fixed rotating group
    using the authoritative microbond_core domain engine.
    """
    if not members:
        return 0

    current_time_epoch = int(datetime.now(timezone.utc).timestamp())
    member_user_ids = [str(m.user_id) for m in members]

    reserve_fund_bps = int(round((getattr(settings, "reserve_fund_percentage", 0.0) or 0.0) * 10_000))
    payouts_per_cycle = getattr(details, "payouts_per_cycle", 1) or 1
    collection_frequency_days = getattr(details, "collection_frequency_days", 7) or 7
    contribution_amount = int(getattr(details, "contribution_amount", 0) or 0)
    saving_days_per_cycle = getattr(details, "saving_days_per_cycle", 1) or 1
    cycle_contribution_amount = contribution_amount * saving_days_per_cycle
    effective_cycle_days = collection_frequency_days * saving_days_per_cycle
    start_epoch = int(start_date.timestamp())

    matrix_json = generate_cycle_matrix(
        member_user_ids=member_user_ids,
        group_type="STANDARD",
        contribution_minor=contribution_amount,
        payouts_per_cycle=payouts_per_cycle,
        reserve_fund_bps=reserve_fund_bps,
        collection_frequency_days=effective_cycle_days,
        start_epoch_seconds=start_epoch,
        created_at_epoch_seconds=current_time_epoch,
    )
    matrix_data = json.loads(matrix_json)

    raw_obligations = matrix_data.get("obligations", [])
    raw_payouts = matrix_data.get("payouts", [])

    from app.utils.time.now_epoch_ms import now_epoch_ms
    now_ms = now_epoch_ms()

    def to_ms(val) -> int:
        ts = int(val)
        return ts * 1000 if ts < 10_000_000_000 else ts

    def to_uuid(val):
        if isinstance(val, uuid.UUID):
            return val
        return uuid.UUID(str(val))

    freq_ms = effective_cycle_days * 86400 * 1000

    obligations = [
        {
            "group_id": group_id,
            "user_id": to_uuid(o["user_id"]),
            "cycle_number": o["cycle_number"],
            "amount_due": o["amount_due"],
            "amount_paid": o.get("amount_paid", 0),
            "due_date": to_ms(o["due_date"]) + freq_ms,
            "status": o.get("status", "PENDING"),
            "created_at": now_ms,
            "updated_at": now_ms,
        }
        for o in raw_obligations
    ]

    payouts = [
        {
            "group_id": group_id,
            "user_id": to_uuid(p["user_id"]),
            "cycle_number": p["cycle_number"],
            "amount_expected": p["amount_expected"],
            "amount_received": p.get("amount_received", p.get("amount_collected", 0)),
            "status": p.get("status", "PENDING"),
            "payout_date": to_ms(p["payout_date"]) + freq_ms,
            "created_at": now_ms,
        }
        for p in raw_payouts
    ]

    if obligations:
        session.bulk_insert_mappings(MemberObligation, obligations)
    if payouts:
        session.bulk_insert_mappings(GroupPayout, payouts)

    # Assign payout positions (1, 2, 3...) to members in rotation order
    for idx, m in enumerate(members, start=1):
        m.payout_position = idx
        session.add(m)

    return matrix_data.get("num_cycles", 0)

