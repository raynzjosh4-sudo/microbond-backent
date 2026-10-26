import pytest
import uuid
import hashlib
from sqlmodel import Session, select
from fastapi.testclient import TestClient

from app.main import app
from app.models.user.user import User
from app.models.group.group import Group, GroupMembership
from app.models.group.rotating.rotating_group_details import RotatingGroupDetails
from app.models.group.wallet.group_wallet import GroupWallet
from app.models.group.settings.group_financial_settings import GroupFinancialSettings
from app.models.group.finance import MemberObligation, GroupPayout
from app.models.group.ledger.ledger_entry import LedgerEntry
from app.models.group.report.rotating_cycle_report import RotatingCycleReport
from app.models.group.chat import GroupChatMessage
from app.services.group.rotating.rotating_report_service import (
    build_cycle_report_payload,
    generate_and_save_cycle_report,
    post_cycle_report_card_to_chat,
    generate_printable_html,
    generate_csv
)
from sqlmodel import create_engine, SQLModel
from sqlmodel.pool import StaticPool
from app.utils.time.now_epoch_ms import now_epoch_ms
from app.api.dependencies import get_current_user
from app.core.database import get_session


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


def test_rotating_cycle_report_full_lifecycle(db_session: Session, monkeypatch):
    session = db_session
    client = TestClient(app)
    app.dependency_overrides[get_session] = lambda: session

    now_ms = now_epoch_ms()

    # 1. Setup 4 Users
    u1 = User(id=uuid.uuid4(), phone_number="+256701111111", full_name="Alice Nsubuga", fcm_token="tok_1")
    u2 = User(id=uuid.uuid4(), phone_number="+256702222222", full_name="Bob Mukasa", fcm_token="tok_2")
    u3 = User(id=uuid.uuid4(), phone_number="+256703333333", full_name="Charlie Kato", fcm_token="tok_3")
    u4 = User(id=uuid.uuid4(), phone_number="+256704444444", full_name="Diana Namubiru", fcm_token="tok_4")
    outsider = User(id=uuid.uuid4(), phone_number="+256709999999", full_name="Outsider User", fcm_token="tok_out")

    session.add_all([u1, u2, u3, u4, outsider])
    session.commit()

    # 2. Setup Group & Rotating Details
    group_id = f"grp-report-{uuid.uuid4().hex[:8]}"
    group = Group(
        group_id=group_id,
        name="Kigo Hustlers Circle",
        type="MERRY_GO_ROUND",
        payment_mode="OBLIGATION",
        created_by_user_id=u1.id,
        currency="UGX",
        member_count=4,
        max_members=4,
        status="ACTIVE",
        group_image_url="https://example.com/image.png"
    )
    session.add(group)

    details = RotatingGroupDetails(
        group_id=group_id,
        contribution_amount=100000.0,
        payouts_per_cycle=1,
        number_of_cycles=4,
        collection_frequency_days=7,
        collection_time="17:00",
        group_start_time=now_ms,
        payout_order_strategy="RANDOM",
        is_payout_order_locked=True,
        total_expected_pool_per_cycle=400000.0,
        current_cycle=1,
        auto_disburse_when_full=True,
        early_turn_security_hold_percentage=10.0,
        minimum_kyc_tier=1,
        require_guarantor=False,
        guarantor_default_action="NONE",
        allow_partial_payments=True,
        allow_advance_deposits=True
    )
    session.add(details)

    wallet = GroupWallet(
        group_id=group_id,
        currency="UGX",
        pooled_funds=0,
        prepaid_funds=300000,
        reserve_funds=40000
    )
    session.add(wallet)

    fin_settings = GroupFinancialSettings(
        group_id=group_id,
        enforce_payout_holds=True
    )
    session.add(fin_settings)

    # Memberships (Alice has 300,000 UGX in prepaid credit balance)
    m1 = GroupMembership(membership_id=str(uuid.uuid4()), group_id=group_id, user_id=u1.id, role="ADMIN", payout_position=1, credit_balance_ugx=300000, status="ACTIVE")
    m2 = GroupMembership(membership_id=str(uuid.uuid4()), group_id=group_id, user_id=u2.id, role="MEMBER", payout_position=2, credit_balance_ugx=0, status="ACTIVE")
    m3 = GroupMembership(membership_id=str(uuid.uuid4()), group_id=group_id, user_id=u3.id, role="MEMBER", payout_position=3, credit_balance_ugx=0, status="ACTIVE")
    m4 = GroupMembership(membership_id=str(uuid.uuid4()), group_id=group_id, user_id=u4.id, role="MEMBER", payout_position=4, credit_balance_ugx=0, status="ACTIVE")
    session.add_all([m1, m2, m3, m4])

    # Payout 1 (Completed, 360,000 UGX disbursed, 40,000 UGX escrow held)
    payout1 = GroupPayout(
        group_id=group_id,
        cycle_number=1,
        user_id=u1.id,
        amount_expected=400000,
        amount_received=360000,
        status="COMPLETED",
        hold_reason="Security reserve: 40,000 UGX held in escrow until cycle completion.",
        payout_date=now_ms
    )
    # Payout 2 (Pending for next cycle)
    payout2 = GroupPayout(
        group_id=group_id,
        cycle_number=2,
        user_id=u2.id,
        amount_expected=400000,
        amount_received=0,
        status="PENDING",
        payout_date=now_ms + 604800000
    )
    session.add_all([payout1, payout2])

    # Obligations for Cycle 1
    ob1 = MemberObligation(group_id=group_id, cycle_number=1, user_id=u1.id, amount_due=100000, amount_paid=100000, status="PAID", due_date=now_ms + 86400000)
    ob2 = MemberObligation(group_id=group_id, cycle_number=1, user_id=u2.id, amount_due=100000, amount_paid=100000, status="PAID", due_date=now_ms + 86400000)
    ob3 = MemberObligation(group_id=group_id, cycle_number=1, user_id=u3.id, amount_due=100000, amount_paid=100000, status="PAID", due_date=now_ms + 86400000)
    ob4 = MemberObligation(group_id=group_id, cycle_number=1, user_id=u4.id, amount_due=100000, amount_paid=100000, status="PAID", due_date=now_ms + 86400000)
    session.add_all([ob1, ob2, ob3, ob4])

    # Ledger entries for audit verification
    l1 = LedgerEntry(group_id=group_id, obligation_id=1, amount=100000, source_account="MTN_MOMO", destination_account="GROUP_POOLED", transaction_type="DEPOSIT", status="SETTLED", created_at=now_ms - 3000)
    l2 = LedgerEntry(group_id=group_id, obligation_id=2, amount=100000, source_account="MTN_MOMO", destination_account="GROUP_POOLED", transaction_type="DEPOSIT", status="SETTLED", created_at=now_ms - 2000)
    l3 = LedgerEntry(group_id=group_id, obligation_id=3, amount=100000, source_account="MTN_MOMO", destination_account="GROUP_POOLED", transaction_type="DEPOSIT", status="SETTLED", created_at=now_ms - 1000)
    l4 = LedgerEntry(group_id=group_id, obligation_id=4, amount=100000, source_account="MTN_MOMO", destination_account="GROUP_POOLED", transaction_type="DEPOSIT", status="SETTLED", created_at=now_ms - 500)
    l_payout = LedgerEntry(group_id=group_id, payout_id=1, amount=360000, source_account="GROUP_POOLED", destination_account="USER_MOMO", transaction_type="PAYOUT", status="SETTLED", created_at=now_ms)
    session.add_all([l1, l2, l3, l4, l_payout])

    session.commit()

    # -----------------------------------------------------------------
    # A. TEST CORE REPORT GENERATION & PERSISTENCE
    # -----------------------------------------------------------------
    report = generate_and_save_cycle_report(
        session=session,
        group_id=group_id,
        cycle_number=1,
        payout=payout1
    )

    assert report is not None
    assert report.group_id == group_id
    assert report.cycle_number == 1
    assert report.report_type == "ROTATING_CYCLE_COMPLETION"

    # Verify financial totals
    assert report.expected_pool_target == 400000
    assert report.actual_collected_amount == 400000
    assert report.collection_rate_percentage == 100.0
    assert report.gross_payout_amount == 400000
    assert report.early_security_hold_deducted == 40000
    assert report.net_payout_disbursed == 360000

    # Verify recipient details
    assert report.recipient_user_id == u1.id
    assert report.recipient_name == "Alice Nsubuga"
    assert report.recipient_turn_position == 1

    # Verify cryptographic audit hash
    assert len(report.cryptographic_hash_sha256) == 64
    assert report.certified_by == "Microbond Authoritative Ledger Engine"
    assert report.ledger_entries_count >= 1

    # Verify member breakdown
    breakdown = report.report_data["member_performance_breakdown"]
    assert len(breakdown) == 4
    alice_row = next(m for m in breakdown if m["user_id"] == str(u1.id))
    assert alice_row["advance_prepaid_balance"] == 300000
    assert alice_row["status"] == "PAID_ON_TIME"
    assert alice_row["amount_paid_this_cycle"] == 100000

    # -----------------------------------------------------------------
    # B. TEST IN-CHAT INTERACTIVE REPORT CARD
    # -----------------------------------------------------------------
    post_cycle_report_card_to_chat(session=session, report=report)

    chat_msg = session.exec(
        select(GroupChatMessage).where(
            GroupChatMessage.group_id == group_id,
            GroupChatMessage.message_type == "ROTATING_CYCLE_REPORT_CARD"
        )
    ).first()

    assert chat_msg is not None
    assert "Cycle 1 Official Report Card" in chat_msg.message_text
    assert "Pot Collected: 400,000 / 400,000 UGX (100.0%)" in chat_msg.message_text
    assert "Disbursed to Alice Nsubuga: 360,000 UGX" in chat_msg.message_text
    assert "Security Escrow Held: 40,000 UGX" in chat_msg.message_text
    assert "Next Recipient for Cycle 2: Bob Mukasa" in chat_msg.message_text

    # Action chip validation
    assert chat_msg.attachments is not None
    action_chip = chat_msg.attachments[0]
    assert action_chip["has_action_button"] is True
    assert action_chip["action_text"] == "Download Full PDF Statement"
    assert action_chip["action_route"] == "download_cycle_report_pdf"
    assert action_chip["action_payload"]["cycle_number"] == 1
    assert action_chip["action_payload"]["report_id"] == report.report_id

    # -----------------------------------------------------------------
    # C. TEST EXPORT FORMATTERS (HTML & CSV)
    # -----------------------------------------------------------------
    html_output = generate_printable_html(report.report_data)
    assert "Kigo Hustlers Circle" in html_output
    assert "Official Cycle 1 Milestone Statement" in html_output
    assert "Alice Nsubuga" in html_output
    assert "360,000 UGX" in html_output
    assert report.cryptographic_hash_sha256 in html_output

    csv_output = generate_csv(report.report_data)
    assert "MICROBOND AUTHORITATIVE ROTATING GROUP AUDIT REPORT" in csv_output
    assert "Alice Nsubuga" in csv_output
    assert report.cryptographic_hash_sha256 in csv_output

    # -----------------------------------------------------------------
    # D. TEST REST API ENDPOINTS
    # -----------------------------------------------------------------
    app.dependency_overrides[get_current_user] = lambda: u1

    # 1. List cycle reports
    resp_list = client.get(f"/api/v1/groups/{group_id}/reports/cycles")
    assert resp_list.status_code == 200
    list_data = resp_list.json()["data"]
    assert len(list_data) == 1
    assert list_data[0]["cycle_number"] == 1
    assert list_data[0]["net_payout_disbursed"] == 360000

    # 2. Get specific cycle report JSON
    resp_detail = client.get(f"/api/v1/groups/{group_id}/reports/cycle/1")
    assert resp_detail.status_code == 200
    detail_data = resp_detail.json()["data"]
    assert detail_data["report_type"] == "ROTATING_CYCLE_COMPLETION"
    assert detail_data["financial_summary"]["net_payout_disbursed"] == 360000
    assert detail_data["audit_integrity"]["cryptographic_hash_sha256"] == report.cryptographic_hash_sha256

    # 3. Export as HTML
    resp_html = client.get(f"/api/v1/groups/{group_id}/reports/cycle/1/export?format=html")
    assert resp_html.status_code == 200
    assert "text/html" in resp_html.headers["content-type"]
    assert "Kigo Hustlers Circle" in resp_html.text

    # 4. Export as CSV
    resp_csv = client.get(f"/api/v1/groups/{group_id}/reports/cycle/1/export?format=csv")
    assert resp_csv.status_code == 200
    assert "text/csv" in resp_csv.headers["content-type"]
    assert "attachment" in resp_csv.headers["content-disposition"]
    assert "Alice Nsubuga" in resp_csv.text

    # 5. Access control: Outsider forbidden
    app.dependency_overrides[get_current_user] = lambda: outsider
    resp_forbidden = client.get(f"/api/v1/groups/{group_id}/reports/cycle/1")
    assert resp_forbidden.status_code == 403

    app.dependency_overrides.clear()
