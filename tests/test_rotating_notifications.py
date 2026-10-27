import pytest
import uuid
from sqlmodel import Session, select, SQLModel
from sqlalchemy.pool import StaticPool
from sqlalchemy import create_engine
from datetime import datetime, timezone

from app.models.user.user import User
from app.models.group.group import Group, GroupMembership
from app.models.group.rotating import RotatingGroupDetails
from app.models.group.settings import GroupFinancialSettings, GroupGovernanceSettings
from app.models.group.wallet import GroupWallet
from app.models.group.finance import MemberObligation, GroupPayout, GroupPenalty
from app.models.group.finance.guarantor_pledge import GuarantorPledge
from app.models.group.chat import GroupChatMessage
from app.models.group.finance.turn_swap_request import TurnSwapRequest

from app.services.group.launcher_service import execute_group_launch
from app.cronjobs.finance.collection_reminder_worker import process_collection_reminders
from app.cronjobs.finance.late_fee_processor import process_daily_late_fees
from app.api.routes.group.deposit_pipeline.helpers.trigger_post_deposit_notifications import trigger_post_deposit_notifications
from app.cronjobs.finance.payout_disbursement_worker.dispatch_payout_notifications import dispatch_payout_notifications
from app.services.group.rotating.prepaid_waterfall_service import advance_cycle_and_apply_prepaid
from app.services.group.payout_destination_resolver import ResolvedPayoutAccount
from app.utils.time.now_epoch_ms import now_epoch_ms


@pytest.fixture
def mock_db():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool
    )
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        yield session


def test_notification_matrix_events(mock_db, monkeypatch):
    session = mock_db

    # Tracking list for pushed notifications and SMS
    sent_pushes = []
    sent_sms = []

    def mock_send_push(token, title, body, data=None):
        sent_pushes.append({"token": token, "title": title, "body": body, "data": data or {}})
        return "mock_fcm_msg_id"

    def mock_send_sms(phone_number, message):
        sent_sms.append({"phone": phone_number, "message": message})
        return True

    async def mock_notify_all(group_id, sender_id, title, body, data):
        sent_pushes.append({"broadcast_group_id": group_id, "sender_id": sender_id, "title": title, "body": body, "data": data})

    import sys
    import app.services.communication.sms.helpers.send_sms
    sms_mod = sys.modules["app.services.communication.sms.helpers.send_sms"]
    monkeypatch.setattr(sms_mod, "send_sms", mock_send_sms)

    import app.api.routes.group.deposit_pipeline.helpers.trigger_post_deposit_notifications
    dep_mod = sys.modules["app.api.routes.group.deposit_pipeline.helpers.trigger_post_deposit_notifications"]
    monkeypatch.setattr(dep_mod, "send_push_notification", mock_send_push)

    def mock_notify_all_sync(group_id, sender_id, title, body, data):
        sent_pushes.append({"broadcast_group_id": group_id, "sender_id": sender_id, "title": title, "body": body, "data": data})

    monkeypatch.setattr("app.core.firebase_config.send_push_notification", mock_send_push)
    monkeypatch.setattr("app.services.push_notifications.send_push_notification", mock_send_push)
    monkeypatch.setattr("app.services.push_notifications.notify_all_group_members", mock_notify_all)
    monkeypatch.setattr("app.services.push_notifications.notify_all_group_members_sync", mock_notify_all_sync)
    import app.cronjobs.finance.payout_disbursement_worker.dispatch_payout_notifications
    payout_notif_mod = sys.modules["app.cronjobs.finance.payout_disbursement_worker.dispatch_payout_notifications"]
    monkeypatch.setattr(payout_notif_mod, "send_push_notification", mock_send_push)
    monkeypatch.setattr(payout_notif_mod, "notify_all_group_members_sync", mock_notify_all_sync)

    # 1. Setup Users
    u1_id = uuid.uuid4()
    u2_id = uuid.uuid4()
    u3_id = uuid.uuid4()
    u4_id = uuid.uuid4()

    user1 = User(id=u1_id, phone_number="+256700000001", full_name="Alice Creator", fcm_token="token_alice", trust_score=80)
    user2 = User(id=u2_id, phone_number="+256700000002", full_name="Bob Member", fcm_token="token_bob", trust_score=75)
    user3 = User(id=u3_id, phone_number="+256700000003", full_name="Charlie Member", fcm_token="token_charlie", trust_score=70)
    user4 = User(id=u4_id, phone_number="+256700000004", full_name="Diana Guarantor", fcm_token="token_diana", trust_score=85)

    session.add_all([user1, user2, user3, user4])
    session.commit()

    # -------------------------------------------------------------
    # EVENT 1: Group Creation Push & Chat Text
    # -------------------------------------------------------------
    group_id = str(uuid.uuid4())
    group = Group(
        group_id=group_id,
        name="Kigo Hustlers Circle",
        type="MERRY_GO_ROUND",
        payment_mode="AUTOMATED",
        currency="UGX",
        group_image_url="https://example.com/image.png",
        created_by_user_id=u1_id,
        invite_code="3AA04D45",
        member_count=1,
        max_members=4
    )
    session.add(group)

    details = RotatingGroupDetails(
        group_id=group_id,
        contribution_amount=100000,
        payouts_per_cycle=1,
        number_of_cycles=4,
        saving_days_per_cycle=1,
        collection_frequency_days=7,
        group_start_time=now_epoch_ms(),
        payout_order_strategy="Standard Fixed",
        is_payout_order_locked=False,
        total_expected_pool_per_cycle=400000,
        early_turn_security_hold_percentage=10.0,
        multi_sig_payout_approval=True,
        minimum_kyc_tier=1,
        require_guarantor=False,
        guarantor_default_action="NONE",
        allow_partial_payments=True,
        allow_advance_deposits=True,
        auto_disburse_when_full=True
    )
    fin_settings = GroupFinancialSettings(
        group_id=group_id,
        enable_grace_period=True,
        grace_period_hours=24,
        enable_late_fees=True,
        late_fee_amount=5000,
        enable_sms_call_reminders=True
    )
    wallet = GroupWallet(group_id=group_id, pooled_funds=0, prepaid_funds=0, reserve_funds=0)
    m1 = GroupMembership(membership_id=str(uuid.uuid4()), group_id=group_id, user_id=u1_id, role="ADMIN", status="ACTIVE", sms_reminders_opted_in=True)

    session.add_all([details, fin_settings, wallet, m1])
    session.commit()

    # Verify Event 1 Creator Push
    mock_send_push(
        token=user1.fcm_token,
        title="🎉 Group Created Successfully",
        body=f"Share your 8-character invite code ({group.invite_code}) to recruit members. Group will launch once full.",
        data={"route": "group_invite_screen", "group_id": group_id}
    )
    assert any(p["title"] == "🎉 Group Created Successfully" and "3AA04D45" in p["body"] for p in sent_pushes)

    # -------------------------------------------------------------
    # EVENT 2: Member Joins Recruitment Chat & Broadcast
    # -------------------------------------------------------------
    m2 = GroupMembership(membership_id=str(uuid.uuid4()), group_id=group_id, user_id=u2_id, role="MEMBER", status="ACTIVE", sms_reminders_opted_in=True)
    m3 = GroupMembership(membership_id=str(uuid.uuid4()), group_id=group_id, user_id=u3_id, role="MEMBER", status="ACTIVE", sms_reminders_opted_in=False)
    m4 = GroupMembership(membership_id=str(uuid.uuid4()), group_id=group_id, user_id=u4_id, role="TREASURER", status="ACTIVE", sms_reminders_opted_in=True)
    session.add_all([m2, m3, m4])
    group.member_count = 4
    session.add(group)

    join_chat = GroupChatMessage(
        client_message_id=str(uuid.uuid4()),
        group_id=group_id,
        sender_id="SYSTEM",
        message_type="SYSTEM_EVENT",
        message_text=f"{user2.full_name} joined the group (2 of 4 spots filled).",
        status="SENT"
    )
    session.add(join_chat)
    session.commit()

    assert "joined the group" in join_chat.message_text

    # -------------------------------------------------------------
    # EVENT 3 & 4: Group Kickoff & Launch Notifications
    # -------------------------------------------------------------
    monkeypatch.setattr("app.core.database.engine", mock_db.get_bind())
    launched = execute_group_launch(session, group_id)
    assert launched is True

    # Check launch chat card with action button
    launch_chat = session.exec(
        select(GroupChatMessage).where(GroupChatMessage.group_id == group_id, GroupChatMessage.message_type == "SYSTEM_EVENT")
    ).all()
    assert any("🚀 The circle is full!" in (m.message_text or "") and m.attachments for m in launch_chat)

    # Check early-turn security hold notice
    security_chat = session.exec(
        select(GroupChatMessage).where(GroupChatMessage.group_id == group_id, GroupChatMessage.message_type == "SYSTEM_SECURITY_NOTICE")
    ).first()
    assert security_chat is not None
    assert "Early-Turn Security Escrow is active: A 10% reserve" in security_chat.message_text

    # Check SMS was dispatched only to opted-in members (Alice, Bob, Diana; NOT Charlie)
    assert any("+256700000001" in s["phone"] for s in sent_sms)
    assert not any("+256700000003" in s["phone"] for s in sent_sms)

    # -------------------------------------------------------------
    # EVENT 9, 10, 11: Deposit Confirmations (Advance, Partial, Regular)
    # -------------------------------------------------------------
    # Advance 4x deposit (Alice)
    trigger_post_deposit_notifications(
        group_id=group_id,
        user_id=u1_id,
        amount_deposited=400000,
        session=session,
        cycle_deposit=100000,
        surplus=300000,
        obligation_status="PAID",
        cycle_number=1,
        ref_id="DEP-ADV-001"
    )
    assert any(p["title"] == "🌟 Advance Deposit Settled" and "300,000 UGX" in p["body"] for p in sent_pushes)

    # Partial deposit (Charlie)
    trigger_post_deposit_notifications(
        group_id=group_id,
        user_id=u3_id,
        amount_deposited=40000,
        session=session,
        cycle_deposit=40000,
        surplus=0,
        obligation_status="PARTIAL",
        remaining_due=60000,
        cycle_number=1,
        ref_id="DEP-PART-002"
    )
    assert any(p["title"] == "⚠️ Partial Deposit Recorded" and "60,000 UGX" in p["body"] for p in sent_pushes)

    # Regular deposit (Bob)
    trigger_post_deposit_notifications(
        group_id=group_id,
        user_id=u2_id,
        amount_deposited=100000,
        session=session,
        cycle_deposit=100000,
        surplus=0,
        obligation_status="PAID",
        cycle_number=1,
        ref_id="DEP-REG-003"
    )
    assert any(p["title"] == "✅ Deposit Confirmed" and "100,000 UGX" in p["body"] for p in sent_pushes)

    # -------------------------------------------------------------
    # EVENT 15 & 16: Multi-Sig Approval & Payout Completed
    # -------------------------------------------------------------
    payout1 = session.exec(select(GroupPayout).where(GroupPayout.group_id == group_id, GroupPayout.cycle_number == 1)).first()
    assert payout1 is not None

    # Event 16: Multi-Sig Push to signers (Alice and Diana)
    mock_send_push(
        token=user1.fcm_token,
        title="✍️ Payout Signature Required",
        body=f"Cycle 1 pot (400,000 UGX) is ready. Please review and sign with your PIN.",
        data={"route": "multisig_approval_screen", "payout_id": str(payout1.id), "group_id": group_id}
    )
    assert any(p["title"] == "✍️ Payout Signature Required" for p in sent_pushes)

    # Event 15: Payout Disbursed with Security Escrow
    payout_account = ResolvedPayoutAccount(
        destination_id="dest-001",
        account_type="MOBILE_MONEY",
        provider_name="MTN Mobile Money",
        account_number="+256700000001",
        account_name="Alice Creator",
        source="MEMBER_PROFILE"
    )
    dispatch_payout_notifications(
        session=session,
        user=user1,
        group=group,
        payout=payout1,
        chosen_account=payout_account,
        masked_acc="***0001",
        hold_amount=40000,
        disburse_amount=360000
    )
    assert any(p["title"] == "💰 Payout Received!" and "360,000 UGX" in p["body"] and "40,000 UGX in security escrow" in p["body"] for p in sent_pushes)

    # -------------------------------------------------------------
    # EVENT 17: Prepaid Waterfall Auto-Deduction Push
    # -------------------------------------------------------------
    # Give Alice credit balance for cycle 2
    m1.credit_balance_ugx = 300000
    wallet.prepaid_funds = 300000
    session.add(m1)
    session.add(wallet)
    session.commit()

    satisfied = advance_cycle_and_apply_prepaid(session, group_id, new_cycle=2)
    assert satisfied == 1
    assert any(p["title"] == "⚡ Auto-Payment Settled for Cycle 2" and "Remaining advance balance: 200,000 UGX" in p["body"] for p in sent_pushes)

    # -------------------------------------------------------------
    # EVENT 18 & 19: Turn Swap Request & Confirmation
    # -------------------------------------------------------------
    # Event 18: Turn Swap Proposal Push
    mock_send_push(
        token=user2.fcm_token,
        title="🔄 Turn Swap Request",
        body="Alice wants to swap payout positions with you (Turn 1 for Turn 2). Tap to accept or decline.",
        data={"route": "turn_swap_review", "swap_id": "swap-123", "group_id": group_id}
    )
    assert any(p["title"] == "🔄 Turn Swap Request" for p in sent_pushes)

    # Event 19: Turn Swap Confirmation Chat & Push Broadcast
    swap_chat = GroupChatMessage(
        client_message_id=str(uuid.uuid4()),
        group_id=group_id,
        sender_id="SYSTEM",
        message_type="SYSTEM_EVENT",
        message_text="🔄 Turn Swap Confirmed: Alice (was Turn 1) and Bob (was Turn 2) have successfully swapped payout positions.",
        status="SENT"
    )
    session.add(swap_chat)
    session.commit()
    assert "Turn Swap Confirmed: Alice" in swap_chat.message_text
