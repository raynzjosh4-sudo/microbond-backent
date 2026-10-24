import uuid
import pytest
from sqlmodel import Session, SQLModel, create_engine
from sqlmodel.pool import StaticPool
from fastapi.testclient import TestClient

from app.main import app
from app.core.database import get_session
from app.api.dependencies import get_current_user
from app.models.user.user import User
from app.models.group.group import Group, GroupMembership
from app.models.group.long_term import (
    SharedWalletConfig,
    SharedWalletOperationalSettings,
    FundraiserCampaignConfig,
    FundraiserLiveStats,
    TargetSavingsGroupDetails,
)
from app.models.group.welfare_event import (
    WelfareFundConfig,
    WelfareFundOperationalSettings,
    EventCommitteeConfig,
    EventCommitteeOperationalSettings,
)
from app.models.group.investment_association import (
    InvestmentClubConfig,
    InvestmentClubOperationalSettings,
    AssociationDuesConfig,
    AssociationDuesOperationalSettings,
)
from app.models.group.rotating import RotatingGroupDetails
from app.models.group.bill_split import BillSplitOperationalSettings


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


def make_group(group_id: str, group_type: str, user_id: uuid.UUID) -> Group:
    return Group(
        group_id=group_id,
        name=f"{group_type} Group",
        group_image_url="",
        type=group_type,
        payment_mode="VOLUNTARY",
        created_by_user_id=user_id,
        currency="UGX",
        member_count=1,
        visibility="PRIVATE"
    )


def test_all_group_type_settings_endpoints(db_session: Session):
    admin_id = uuid.uuid4()
    admin_user = User(id=admin_id, phone_number="+256701111222", full_name="Admin Test")
    db_session.add(admin_user)

    app.dependency_overrides[get_session] = lambda: db_session
    app.dependency_overrides[get_current_user] = lambda: admin_user

    client = TestClient(app)

    # 1. SHARED_WALLET
    gid_sw = "group_sw_01"
    db_session.add(make_group(gid_sw, "SHARED_WALLET", admin_id))
    db_session.add(GroupMembership(membership_id=str(uuid.uuid4()), group_id=gid_sw, user_id=admin_id, role="ADMIN", status="ACTIVE"))
    db_session.add(SharedWalletConfig(group_id=gid_sw, category_tags="[]"))
    db_session.add(SharedWalletOperationalSettings(group_id=gid_sw, daily_spending_cap=50000.0, per_transaction_cap=20000.0))
    db_session.commit()

    resp = client.get(f"/api/v1/groups/shared-wallet/{gid_sw}/settings")
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["status"] == "success"
    assert data["data"]["operational_settings"]["daily_spending_cap"] == 50000.0

    patch_sw = client.patch(f"/api/v1/groups/shared-wallet/{gid_sw}/settings", json={"daily_spending_cap": 75000.0})
    assert patch_sw.status_code == 200, patch_sw.text
    assert patch_sw.json()["data"]["daily_spending_cap"] == 75000.0

    # 2. FUNDRAISER
    gid_fr = "group_fr_01"
    db_session.add(make_group(gid_fr, "FUNDRAISER", admin_id))
    db_session.add(GroupMembership(membership_id=str(uuid.uuid4()), group_id=gid_fr, user_id=admin_id, role="ADMIN", status="ACTIVE"))
    db_session.add(FundraiserCampaignConfig(group_id=gid_fr, target_amount=1000000, nominated_account_id="nom_01"))
    db_session.add(FundraiserLiveStats(group_id=gid_fr, allow_overfunding=True))
    db_session.commit()

    resp = client.get(f"/api/v1/groups/fundraiser/{gid_fr}/settings")
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["status"] == "success"
    assert data["data"]["campaign_config"]["target_amount"] == 1000000
    assert data["data"]["live_stats"]["allow_overfunding"] is True

    patch_fr = client.patch(f"/api/v1/groups/fundraiser/{gid_fr}/settings", json={"allow_overfunding": False})
    assert patch_fr.status_code == 200, patch_fr.text
    assert patch_fr.json()["data"]["allow_overfunding"] is False

    # 3. WELFARE_FUND
    gid_wf = "group_wf_01"
    db_session.add(make_group(gid_wf, "WELFARE_FUND", admin_id))
    db_session.add(GroupMembership(membership_id=str(uuid.uuid4()), group_id=gid_wf, user_id=admin_id, role="ADMIN", status="ACTIVE"))
    db_session.add(WelfareFundConfig(group_id=gid_wf, contribution_amount=20000, max_claim_amount_per_incident=200000, annual_claim_limit_per_member=500000))
    db_session.add(WelfareFundOperationalSettings(group_id=gid_wf, minimum_reserve_balance=50000, approval_timeout_hours=48))
    db_session.commit()

    resp = client.get(f"/api/v1/groups/welfare-fund/{gid_wf}/settings")
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["status"] == "success"
    assert data["data"]["operational_settings"]["minimum_reserve_balance"] == 50000

    patch_wf = client.patch(f"/api/v1/groups/welfare-fund/{gid_wf}/settings", json={"approval_timeout_hours": 72})
    assert patch_wf.status_code == 200, patch_wf.text
    assert patch_wf.json()["data"]["approval_timeout_hours"] == 72

    # 4. EVENT_COMMITTEE
    gid_ec = "group_ec_01"
    db_session.add(make_group(gid_ec, "EVENT_COMMITTEE", admin_id))
    db_session.add(GroupMembership(membership_id=str(uuid.uuid4()), group_id=gid_ec, user_id=admin_id, role="ADMIN", status="ACTIVE"))
    db_session.add(EventCommitteeConfig(group_id=gid_ec, event_target_budget=5000000, event_date=1760000000000, collection_deadline=1759000000000))
    db_session.add(EventCommitteeOperationalSettings(group_id=gid_ec, allow_overfunding=True))
    db_session.commit()

    resp = client.get(f"/api/v1/groups/event-committee/{gid_ec}/settings")
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["status"] == "success"
    assert data["data"]["event_config"]["event_target_budget"] == 5000000
    assert data["data"]["operational_settings"]["allow_overfunding"] is True

    patch_ec = client.patch(f"/api/v1/groups/event-committee/{gid_ec}/settings", json={"allow_overfunding": False})
    assert patch_ec.status_code == 200, patch_ec.text
    assert patch_ec.json()["data"]["allow_overfunding"] is False

    # 5. INVESTMENT_CLUB
    gid_ic = "group_ic_01"
    db_session.add(make_group(gid_ic, "INVESTMENT_CLUB", admin_id))
    db_session.add(GroupMembership(membership_id=str(uuid.uuid4()), group_id=gid_ic, user_id=admin_id, role="ADMIN", status="ACTIVE"))
    db_session.add(InvestmentClubConfig(group_id=gid_ic, share_unit_price=10000))
    db_session.add(InvestmentClubOperationalSettings(group_id=gid_ic, minimum_purchase_quota=1))
    db_session.commit()

    resp = client.get(f"/api/v1/groups/investment-club/{gid_ic}/settings")
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["status"] == "success"
    assert data["data"]["investment_config"]["share_unit_price"] == 10000
    assert data["data"]["operational_settings"]["minimum_purchase_quota"] == 1

    patch_ic = client.patch(f"/api/v1/groups/investment-club/{gid_ic}/settings", json={"minimum_purchase_quota": 5})
    assert patch_ic.status_code == 200, patch_ic.text
    assert patch_ic.json()["data"]["minimum_purchase_quota"] == 5

    # 6. ASSOCIATION_DUES
    gid_ad = "group_ad_01"
    db_session.add(make_group(gid_ad, "ASSOCIATION_DUES", admin_id))
    db_session.add(GroupMembership(membership_id=str(uuid.uuid4()), group_id=gid_ad, user_id=admin_id, role="ADMIN", status="ACTIVE"))
    db_session.add(AssociationDuesConfig(group_id=gid_ad, dues_amount=15000, billing_start_date=1760000000000, treasury_account_id="acc_123"))
    db_session.add(AssociationDuesOperationalSettings(group_id=gid_ad, grace_period_days=7))
    db_session.commit()

    resp = client.get(f"/api/v1/groups/association-dues/{gid_ad}/settings")
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["status"] == "success"
    assert data["data"]["association_config"]["dues_amount"] == 15000
    assert data["data"]["operational_settings"]["grace_period_days"] == 7

    patch_ad = client.patch(f"/api/v1/groups/association-dues/{gid_ad}/settings", json={"grace_period_days": 14})
    assert patch_ad.status_code == 200, patch_ad.text
    assert patch_ad.json()["data"]["grace_period_days"] == 14

    # 7. ROTATING
    gid_rot = "group_rot_01"
    db_session.add(make_group(gid_rot, "MERRY_GO_ROUND", admin_id))
    db_session.add(GroupMembership(membership_id=str(uuid.uuid4()), group_id=gid_rot, user_id=admin_id, role="ADMIN", status="ACTIVE"))
    db_session.add(RotatingGroupDetails(
        group_id=gid_rot,
        contribution_amount=50000.0,
        payouts_per_cycle=1,
        number_of_cycles=10,
        collection_frequency_days=7,
        collection_time="18:00",
        group_start_time=1760000000000,
        payout_order_strategy="RANDOM",
        is_payout_order_locked=False,
        total_expected_pool_per_cycle=500000.0,
        minimum_kyc_tier=1,
        require_guarantor=False,
        guarantor_default_action="NONE",
        allow_partial_payments=True,
        allow_advance_deposits=True,
        enforce_payout_holds=False,
    ))
    db_session.commit()

    resp = client.get(f"/api/v1/groups/rotating/{gid_rot}/settings")
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["status"] == "success"
    assert data["data"]["contribution_amount"] == 50000.0

    patch_rot = client.patch(f"/api/v1/groups/rotating/{gid_rot}/settings", json={"allow_partial_payments": False})
    assert patch_rot.status_code == 200, patch_rot.text
    assert patch_rot.json()["data"]["allow_partial_payments"] is False

    # 8. BILL_SPLIT
    gid_bs = "group_bs_01"
    db_session.add(make_group(gid_bs, "BILL_SPLIT", admin_id))
    db_session.add(GroupMembership(membership_id=str(uuid.uuid4()), group_id=gid_bs, user_id=admin_id, role="ADMIN", status="ACTIVE"))
    db_session.add(BillSplitOperationalSettings(group_id=gid_bs, allow_tip_or_extra=True))
    db_session.commit()

    resp = client.get(f"/api/v1/groups/bill-split/{gid_bs}/settings")
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["allow_tip_or_extra"] is True

    # 9. TARGET_SAVINGS
    gid_ts = "group_ts_01"
    db_session.add(make_group(gid_ts, "GOAL_SAVINGS", admin_id))
    db_session.add(GroupMembership(membership_id=str(uuid.uuid4()), group_id=gid_ts, user_id=admin_id, role="ADMIN", status="ACTIVE"))
    db_session.add(TargetSavingsGroupDetails(group_id=gid_ts, target_amount=2000000, target_date=1760000000000))
    db_session.commit()

    resp = client.get(f"/api/v1/groups/target-savings/{gid_ts}/settings")
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["status"] == "success"
    assert data["data"]["target_amount"] == 2000000

    # Clean overrides
    app.dependency_overrides.clear()
