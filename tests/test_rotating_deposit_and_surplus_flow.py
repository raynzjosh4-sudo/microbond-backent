import pytest
import uuid
import time
from sqlmodel import Session, SQLModel, create_engine, select
from sqlmodel.pool import StaticPool
from fastapi import HTTPException

from app.models.user.user import User
from app.models.group.group import Group, GroupMembership
from app.models.group.rotating import RotatingGroupDetails
from app.models.group.settings import GroupFinancialSettings, GroupGovernanceSettings
from app.models.group.wallet import GroupWallet
from app.models.group.finance import MemberObligation, GroupPayout
from app.services.group.launcher_service import execute_group_launch
from app.services.group.rotating.prepaid_waterfall_service import advance_cycle_and_apply_prepaid
from app.api.routes.group.deposit_pipeline.direct_deposit import direct_deposit
from app.api.routes.group.deposit_pipeline.schemas.direct_deposit import DirectDepositRequest
from app.api.routes.group.deposit_pipeline.get_deposit_info import get_deposit_info
from app.services.group.dashboard_summary_service import GroupDashboardSummaryService
from app.cronjobs.finance.payout_disbursement_worker.process_single_payout import process_single_payout
from app.services.mobile_money.disbursement_service import DisbursementService, DisbursementResult


@pytest.fixture(name="db_session")
def db_session_fixture():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        yield session


def test_rotating_deposit_and_surplus_lifecycle(db_session: Session, monkeypatch):
    monkeypatch.setattr(
        DisbursementService,
        "disburse",
        lambda destination, amount, narrative, external_id: DisbursementResult(
            success=True,
            transaction_id=f"tx_{uuid.uuid4().hex[:8]}",
            provider=getattr(destination, "provider_name", "MTN Mobile Money"),
            amount=amount,
            account_number=getattr(destination, "account_number", "256700000000")
        )
    )
    import app.api.routes.group.chat.messages.helpers.messages_helpers as mh
    monkeypatch.setattr(mh, "notify_all_group_members", lambda **kwargs: None)
    now_ms = int(time.time() * 1000)
    
    # 1. Create 4 test users
    users = []
    for i in range(4):
        u = User(
            phone_number=f"+25670{i}112233",
            full_name=f"Member {i+1}",
            status="ACTIVE"
        )
        db_session.add(u)
        users.append(u)
    db_session.commit()
    for u in users:
        db_session.refresh(u)

    user_a = users[0]

    # 2. Create Rotating Group with 4 max members, 100k dues
    gid = f"grp-test-rot-{uuid.uuid4().hex[:6]}"
    group = Group(
        group_id=gid,
        name="Circle of 4",
        group_image_url="https://example.com/icon.png",
        type="MERRY_GO_ROUND",
        payment_mode="OBLIGATION",
        currency="UGX",
        max_members=4,
        member_count=1,
        status="FORMING",
        created_by_user_id=user_a.id,
        created_at=now_ms,
        updated_at=now_ms
    )
    db_session.add(group)

    rot = RotatingGroupDetails(
        group_id=gid,
        contribution_amount=100000.0,
        payouts_per_cycle=1,
        number_of_cycles=4,
        saving_days_per_cycle=1,
        collection_frequency_days=7,
        group_start_time=now_ms + 3600000,
        payout_order_strategy="Randomized by App",
        total_expected_pool_per_cycle=400000.0,
        minimum_kyc_tier=1,
        require_guarantor=False,
        guarantor_default_action="NONE",
        allow_partial_payments=False,
        allow_advance_deposits=True,
        auto_disburse_when_full=True,
        current_cycle=1
    )
    db_session.add(rot)

    fin_settings = GroupFinancialSettings(
        group_id=gid,
        reserve_fund_percentage=0.0,
        allow_overpay=True,
        allow_partial_pay=False
    )
    db_session.add(fin_settings)

    gov_settings = GroupGovernanceSettings(
        group_id=gid,
        requires_admin_approval=False
    )
    db_session.add(gov_settings)

    wallet = GroupWallet(
        group_id=gid,
        currency="UGX",
        pooled_funds=0,
        prepaid_funds=0,
        reserve_funds=0,
        total_lifetime_deposits=0,
        total_lifetime_payouts=0
    )
    db_session.add(wallet)

    m1 = GroupMembership(
        membership_id=str(uuid.uuid4()),
        group_id=gid,
        user_id=user_a.id,
        role="ADMIN",
        status="ACTIVE",
        joined_at=now_ms,
        credit_balance_ugx=0
    )
    db_session.add(m1)
    db_session.commit()

    # Helper for async direct_deposit
    import asyncio
    from fastapi import BackgroundTasks
    def call_deposit(u, amt):
        return asyncio.run(
            direct_deposit(
                group_id=gid,
                payload=DirectDepositRequest(amount=amt, payment_method="TEST_WALLET"),
                background_tasks=BackgroundTasks(),
                current_user=u,
                session=db_session
            )
        )

    # 3. VERIFY: Deposit rejected while FORMING
    with pytest.raises(HTTPException) as exc_info:
        call_deposit(user_a, 100000)
    assert exc_info.value.status_code == 400
    assert "still forming" in exc_info.value.detail

    # Verify get_deposit_info also rejects
    with pytest.raises(HTTPException) as exc_info_info:
        get_deposit_info(group_id=gid, current_user=user_a, session=db_session)
    assert exc_info_info.value.status_code == 400
    assert "still forming" in exc_info_info.value.detail

    # 4. Add remaining 3 members to reach capacity
    for idx, u in enumerate(users[1:], start=2):
        m = GroupMembership(
            membership_id=str(uuid.uuid4()),
            group_id=gid,
            user_id=u.id,
            role="MEMBER",
            status="ACTIVE",
            joined_at=now_ms,
            credit_balance_ugx=0
        )
        db_session.add(m)
    group.member_count = 4
    db_session.add(group)
    db_session.commit()

    # Launch group (as triggered when reaching max_members)
    rot.group_start_time = now_ms - 1000 # group schedule started
    rot.is_payout_order_locked = False
    db_session.add(rot)
    db_session.commit()

    execute_group_launch(db_session, gid)
    db_session.refresh(group)
    assert group.status == "ACTIVE"

    # Verify obligations created: 4 members * 4 cycles = 16 obligations
    obs = db_session.exec(select(MemberObligation).where(MemberObligation.group_id == gid)).all()
    assert len(obs) == 16

    # Verify initial Ring Status: 4 expected, 0 paid, 0 missed
    summaries = GroupDashboardSummaryService.get_user_dashboard_summaries(db_session, user_a.id)
    grp_summary = next(s for s in summaries if s.group_id == gid)
    assert grp_summary.ring_status.total_expected_members == 4
    assert grp_summary.ring_status.paid_on_time_count == 0
    assert grp_summary.ring_status.missed_deadline_count == 0

    # 5. User A deposits 400,000 UGX (4x cycle dues)
    dep_res = call_deposit(user_a, 400000)

    # 6. Verify deposit response split
    assert dep_res.cycle_contribution_credited == 100000
    assert dep_res.advance_savings_credited == 300000
    assert dep_res.member_prepaid_balance == 300000

    # 7. Verify GroupWallet balances
    db_session.refresh(wallet)
    assert wallet.pooled_funds == 100000      # Only Cycle 1 pot is funded
    assert wallet.prepaid_funds == 300000     # 300k stored in prepaid escrow

    # 8. Verify Member A's credit balance and obligations
    db_session.refresh(m1)
    assert m1.credit_balance_ugx == 300000

    ob_c1 = db_session.exec(
        select(MemberObligation).where(
            MemberObligation.group_id == gid,
            MemberObligation.user_id == user_a.id,
            MemberObligation.cycle_number == 1
        )
    ).first()
    assert ob_c1.amount_paid == 100000
    assert ob_c1.status == "PAID"

    ob_c2 = db_session.exec(
        select(MemberObligation).where(
            MemberObligation.group_id == gid,
            MemberObligation.user_id == user_a.id,
            MemberObligation.cycle_number == 2
        )
    ).first()
    assert ob_c2.amount_paid == 0
    assert ob_c2.status == "PENDING"

    # 9. Verify Dashboard Ring: Exactly 1 member paid out of 4
    summaries = GroupDashboardSummaryService.get_user_dashboard_summaries(db_session, user_a.id)
    grp_summary = next(s for s in summaries if s.group_id == gid)
    assert grp_summary.ring_status.total_expected_members == 4
    assert grp_summary.ring_status.paid_on_time_count == 1
    assert grp_summary.ring_status.missed_deadline_count == 0

    # 10. Simulate other 3 members paying Cycle 1 dues
    for u in users[1:]:
        call_deposit(u, 100000)

    db_session.refresh(wallet)
    assert wallet.pooled_funds == 400000 # Full 400k for Cycle 1 pot

    # Ring should now show 4/4 paid
    summaries = GroupDashboardSummaryService.get_user_dashboard_summaries(db_session, user_a.id)
    grp_summary = next(s for s in summaries if s.group_id == gid)
    assert grp_summary.ring_status.paid_on_time_count == 4

    # 11. Complete Payout 1 (400,000 UGX to User A)
    payout_1 = db_session.exec(
        select(GroupPayout).where(GroupPayout.group_id == gid, GroupPayout.cycle_number == 1)
    ).first()
    assert payout_1 is not None

    process_single_payout(db_session, payout_1, now_ms=now_ms, force_disburse=True)
    db_session.refresh(payout_1)
    assert payout_1.status == "COMPLETED"

    # 12. VERIFY CYCLE ADVANCE & PREPAID AUTO-DRAW
    db_session.refresh(rot)
    assert rot.current_cycle == 2 # Automatically advanced to Cycle 2!

    db_session.refresh(m1)
    assert m1.credit_balance_ugx == 200000 # 100k drawn for Cycle 2, 200k remaining

    db_session.refresh(wallet)
    assert wallet.prepaid_funds == 200000
    assert wallet.pooled_funds == 100000  # User A's 100k auto-credited into Cycle 2 pool!

    db_session.refresh(ob_c2)
    assert ob_c2.amount_paid == 100000
    assert ob_c2.status == "PAID"         # Cycle 2 obligation is now PAID!

    # 13. Verify Ring in Cycle 2: 1/4 paid (User A auto-paid from advance)
    summaries = GroupDashboardSummaryService.get_user_dashboard_summaries(db_session, user_a.id)
    grp_summary = next(s for s in summaries if s.group_id == gid)
    assert grp_summary.ring_status.total_expected_members == 4
    assert grp_summary.ring_status.paid_on_time_count == 1
    assert grp_summary.ring_status.missed_deadline_count == 0
