"""Integration tests for Daily Deposit Widget and Member Drill-down endpoints."""
import uuid
from datetime import datetime
from fastapi import Depends
from fastapi.testclient import TestClient
from sqlmodel import Session, select
import pytest

from app.main import app
from app.core.database import engine, get_session
from app.api.dependencies import get_current_user
from app.models.user.user import User
from app.models.group.group import Group, GroupMembership
from app.models.group.settings import GroupVisibilitySettings
from app.models.group.finance.member_obligation import MemberObligation
from app.models.group.ledger.ledger_entry import LedgerEntry
from app.models.group.rotating.rotating_group_details import RotatingGroupDetails
from app.services.analytics.buckets import LOCAL_TZ

def ms(y, m, d, h=0, mi=0):
    return int(datetime(y, m, d, h, mi, tzinfo=LOCAL_TZ).timestamp() * 1000)

@pytest.fixture(name="widget_test_env", scope="module")
def widget_test_env_fixture():
    admin_id = uuid.uuid4()
    member1_id = uuid.uuid4()
    member2_id = uuid.uuid4()
    member3_id = uuid.uuid4()

    phone_prefix = str(uuid.uuid4().int)[:6]
    
    admin_user = User(
        id=admin_id,
        phone_number=f"+25670{phone_prefix}01",
        full_name="Admin John",
        profile_picture_url="https://example.com/john.jpg",
        is_online=True,
        last_seen_at=ms(2026, 10, 21, 10, 0)
    )
    user_full = User(
        id=member1_id,
        phone_number=f"+25670{phone_prefix}02",
        full_name="Alice Full",
        profile_picture_url="https://example.com/alice.jpg",
        is_online=False,
        last_seen_at=ms(2026, 10, 21, 8, 30)
    )
    user_partial = User(
        id=member2_id,
        phone_number=f"+25670{phone_prefix}03",
        full_name="Bob Partial",
        profile_picture_url=None,
        is_online=True,
        last_seen_at=ms(2026, 10, 21, 11, 0)
    )
    user_unpaid = User(
        id=member3_id,
        phone_number=f"+25670{phone_prefix}04",
        full_name="Charlie Unpaid",
        profile_picture_url=None,
        is_online=False,
        last_seen_at=ms(2026, 10, 20, 19, 0)
    )

    with Session(engine) as session:
        session.add(admin_user)
        session.add(user_full)
        session.add(user_partial)
        session.add(user_unpaid)
        session.commit()

        # Create group
        group_id = str(uuid.uuid4())
        group = Group(
            group_id=group_id,
            name="Deposit Widget Test Group",
            group_image_url="https://example.com/group.png",
            payment_mode="OBLIGATION",
            type="MERRY_GO_ROUND",
            created_by_user_id=admin_id
        )
        session.add(group)

        # Rotating details: 50,000 UGX target per member
        rotating = RotatingGroupDetails(
            group_id=group_id,
            contribution_amount=50000.0,
            payouts_per_cycle=1,
            collection_frequency_days=1,
            group_start_time=ms(2026, 10, 1),
            payout_order_strategy="RANDOM",
            total_expected_pool_per_cycle=200000.0,
            minimum_kyc_tier=1,
            require_guarantor=False,
            guarantor_default_action="NONE",
            allow_partial_payments=True,
            allow_advance_deposits=True,
            enforce_payout_holds=False
        )
        session.add(rotating)

        # Memberships
        for u_id, role in [
            (admin_id, "ADMIN"),
            (member1_id, "MEMBER"),
            (member2_id, "MEMBER"),
            (member3_id, "MEMBER")
        ]:
            m = GroupMembership(
                membership_id=str(uuid.uuid4()),
                group_id=group_id,
                user_id=u_id,
                role=role,
                status="ACTIVE",
                joined_at=ms(2026, 10, 1)
            )
            session.add(m)

        # Visibility settings: ALL_MEMBERS can view
        vis = GroupVisibilitySettings(
            group_id=group_id,
            deposit_widget_visibility="ALL_MEMBERS",
            hide_member_contact_info=True
        )
        session.add(vis)

        # Today is 2026-10-21
        today_noon = ms(2026, 10, 21, 12, 0)

        # Member 1 (Alice): Settled deposit of 50,000 (FULL)
        session.add(LedgerEntry(
            id=uuid.uuid4(),
            group_id=group_id,
            user_id=member1_id,
            amount=50000,
            transaction_type="DEPOSIT",
            status="SETTLED",
            source_account="USER_MOMO",
            destination_account="GROUP_POOLED",
            settled_at=today_noon
        ))

        # Member 2 (Bob): Settled deposit of 20,000 (PARTIAL / HALF)
        session.add(LedgerEntry(
            id=uuid.uuid4(),
            group_id=group_id,
            user_id=member2_id,
            amount=20000,
            transaction_type="DEPOSIT",
            status="SETTLED",
            source_account="USER_MOMO",
            destination_account="GROUP_POOLED",
            settled_at=today_noon + 3600000
        ))

        # Admin John: Settled deposit of 50,000 (FULL)
        session.add(LedgerEntry(
            id=uuid.uuid4(),
            group_id=group_id,
            user_id=admin_id,
            amount=50000,
            transaction_type="DEPOSIT",
            status="SETTLED",
            source_account="USER_MOMO",
            destination_account="GROUP_POOLED",
            settled_at=today_noon
        ))

        # Member 3 (Charlie): 0 deposited (NOT_DEPOSITED)
        session.commit()

    return {
        "group_id": group_id,
        "admin_id": admin_id,
        "member_id": member1_id,
        "bob_id": member2_id,
        "charlie_id": member3_id,
        "today_ms": today_noon
    }

def test_daily_widget_summary_endpoint(widget_test_env):
    group_id = widget_test_env["group_id"]
    admin_id = widget_test_env["admin_id"]
    today_ms = widget_test_env["today_ms"]

    def override_admin():
        with Session(engine) as s:
            return s.get(User, admin_id)

    app.dependency_overrides[get_current_user] = override_admin
    client = TestClient(app)

    res = client.get(
        f"/api/v1/groups/{group_id}/deposits/daily-widget",
        params={"date_ms": today_ms}
    )
    assert res.status_code == 200
    data = res.json()["data"]
    
    assert data["target_amount_per_member"] == 50000
    assert data["total_members"] == 4

    summary = data["summary"]
    # 2 Full (Admin + Alice)
    assert summary["full"]["count"] == 2
    assert summary["full"]["total_amount"] == 100000
    
    # 1 Partial (Bob)
    assert summary["partial"]["count"] == 1
    assert summary["partial"]["total_amount"] == 20000
    
    # 1 Unpaid (Charlie)
    assert summary["not_deposited"]["count"] == 1
    assert summary["not_deposited"]["total_amount"] == 0

    app.dependency_overrides.clear()

def test_drill_down_full_members(widget_test_env):
    group_id = widget_test_env["group_id"]
    member_id = widget_test_env["member_id"]
    today_ms = widget_test_env["today_ms"]

    def override_member():
        with Session(engine) as s:
            return s.get(User, member_id)

    app.dependency_overrides[get_current_user] = override_member
    client = TestClient(app)

    # Drill down into FULL deposits
    res = client.get(
        f"/api/v1/groups/{group_id}/deposits/daily-widget/members",
        params={"status": "FULL", "date_ms": today_ms}
    )
    assert res.status_code == 200
    data = res.json()["data"]
    assert data["filter_status"] == "FULL"
    assert data["count"] == 2

    # Verify fields returned for members
    first_member = data["members"][0]
    assert "user_id" in first_member
    assert "full_name" in first_member
    assert "profile_picture_url" in first_member
    assert "is_online" in first_member
    assert "last_seen_at" in first_member
    assert first_member["amount_paid"] == 50000
    assert first_member["status"] == "FULL"
    assert first_member["percentage_paid"] == 100.0

    app.dependency_overrides.clear()

def test_drill_down_partial_and_unpaid(widget_test_env):
    group_id = widget_test_env["group_id"]
    member_id = widget_test_env["member_id"]
    today_ms = widget_test_env["today_ms"]

    def override_member():
        with Session(engine) as s:
            return s.get(User, member_id)

    app.dependency_overrides[get_current_user] = override_member
    client = TestClient(app)

    # Partial
    res_partial = client.get(
        f"/api/v1/groups/{group_id}/deposits/daily-widget/members",
        params={"status": "PARTIAL", "date_ms": today_ms}
    )
    assert res_partial.status_code == 200
    partial_data = res_partial.json()["data"]
    assert partial_data["count"] == 1
    assert partial_data["members"][0]["full_name"] == "Bob Partial"
    assert partial_data["members"][0]["amount_paid"] == 20000
    assert partial_data["members"][0]["percentage_paid"] == 40.0
    assert partial_data["members"][0]["can_nudge"] is True

    # Unpaid
    res_unpaid = client.get(
        f"/api/v1/groups/{group_id}/deposits/daily-widget/members",
        params={"status": "NOT_DEPOSITED", "date_ms": today_ms}
    )
    assert res_unpaid.status_code == 200
    unpaid_data = res_unpaid.json()["data"]
    assert unpaid_data["count"] == 1
    assert unpaid_data["members"][0]["full_name"] == "Charlie Unpaid"
    assert unpaid_data["members"][0]["amount_paid"] == 0
    assert unpaid_data["members"][0]["can_nudge"] is True

    app.dependency_overrides.clear()

def test_permission_gate_and_admin_toggle(widget_test_env):
    group_id = widget_test_env["group_id"]
    admin_id = widget_test_env["admin_id"]
    member_id = widget_test_env["member_id"]
    today_ms = widget_test_env["today_ms"]

    # 1. Admin switches visibility to ADMIN_ONLY
    def override_admin():
        with Session(engine) as s:
            return s.get(User, admin_id)

    app.dependency_overrides[get_current_user] = override_admin
    client = TestClient(app)

    res_patch = client.patch(
        f"/api/v1/groups/{group_id}/settings/deposit-widget-visibility",
        json={"visibility": "ADMIN_ONLY"}
    )
    assert res_patch.status_code == 200
    assert res_patch.json()["deposit_widget_visibility"] == "ADMIN_ONLY"

    # 2. Member tries to view widget -> should get 403 Forbidden!
    def override_member():
        with Session(engine) as s:
            return s.get(User, member_id)

    app.dependency_overrides[get_current_user] = override_member
    res_forbidden = client.get(
        f"/api/v1/groups/{group_id}/deposits/daily-widget",
        params={"date_ms": today_ms}
    )
    assert res_forbidden.status_code == 403
    assert "restricted" in res_forbidden.json()["detail"].lower()

    # 3. Restore visibility to ALL_MEMBERS
    app.dependency_overrides[get_current_user] = override_admin
    res_restore = client.patch(
        f"/api/v1/groups/{group_id}/settings/deposit-widget-visibility",
        json={"visibility": "ALL_MEMBERS"}
    )
    assert res_restore.status_code == 200

    app.dependency_overrides.clear()
