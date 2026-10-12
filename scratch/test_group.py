import uuid
from sqlmodel import Session, select
from app.core.database import engine
from app.models.group.group import Group, GroupMembership, utc_now
from app.models.group.rotating import RotatingGroupDetails
from app.models.group.wallet import GroupWallet
from app.models.user.user import User

with Session(engine) as session:
    user = session.exec(select(User)).first()
    if not user:
        print("No user found")
        exit(0)

    test_gid = str(uuid.uuid4())
    g = Group(
        group_id=test_gid,
        name="Test Rotating Group",
        description="Testing BigInt & Defaults",
        group_image_url="https://example.com/group.png",
        type="rotating group",
        payment_mode="OBLIGATION",
        created_by_user_id=user.id,
        invite_code=str(uuid.uuid4())[:8].upper()
    )
    session.add(g)

    r_details = RotatingGroupDetails(
        group_id=test_gid,
        contribution_amount=50000.0,
        payouts_per_cycle=1,
        number_of_cycles=10,
        collection_frequency_days=7,
        collection_time="18:00",
        group_start_time=utc_now(),
        payout_order_strategy="Randomized Draw",
        is_payout_order_locked=False,
        total_expected_pool_per_cycle=500000.0,
        minimum_kyc_tier=1,
        require_guarantor=False,
        guarantor_default_action="Skip",
        allow_partial_payments=False,
        allow_advance_deposits=True,
        enforce_payout_holds=False
    )
    session.add(r_details)

    mem = GroupMembership(
        membership_id=str(uuid.uuid4()),
        group_id=test_gid,
        user_id=user.id,
        role="ADMIN",
        title="Creator",
        status="ACTIVE"
    )
    session.add(mem)

    gw = GroupWallet(group_id=test_gid)
    session.add(gw)

    session.commit()
    print("SUCCESSFULLY CREATED ALL MODELS! Group ID:", g.id, "created_at:", g.created_at)

    # Clean up test rows
    session.delete(gw)
    session.delete(mem)
    session.delete(r_details)
    session.delete(g)
    session.commit()
    print("Cleaned up test group successfully!")
