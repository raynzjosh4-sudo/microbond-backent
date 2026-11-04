import uuid
import pytest
from sqlmodel import Session, SQLModel, create_engine
from sqlmodel.pool import StaticPool
from fastapi.testclient import TestClient

from app.main import app
from app.core.database import get_session
from app.api.dependencies import get_optional_current_user
from app.models.user.user import User
from app.models.group.group import Group, GroupMembership
from app.models.group.settings.group_visibility_settings import GroupVisibilitySettings
from app.models.group.settings.group_governance_settings import GroupGovernanceSettings
from app.models.group.health.group_health import GroupHealth
from app.models.group.rotating.rotating_group_details import RotatingGroupDetails


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


def test_public_groups_appear_and_private_excluded(db_session: Session):
    creator = User(id=uuid.uuid4(), phone_number="+256701111001", full_name="Creator One", kyc_tier=2, trust_score=85)
    db_session.add(creator)
    db_session.commit()

    # 1. Public group (Discoverable)
    g_public = Group(
        group_id="grp_pub_001",
        name="Public Kampala Chama",
        description="A vibrant public circle",
        group_image_url="https://example.com/pub.png",
        type="MERRY_GO_ROUND",
        payment_mode="OBLIGATION",
        visibility="PUBLIC",
        status="ACTIVE",
        created_by_user_id=creator.id,
        member_count=3,
        max_members=10,
    )
    vis_public = GroupVisibilitySettings(group_id="grp_pub_001", invite_only_discoverability=False)

    # 2. Private group (Excluded)
    g_private = Group(
        group_id="grp_priv_002",
        name="Secret Friends Chama",
        description="Members only",
        group_image_url="https://example.com/priv.png",
        type="MERRY_GO_ROUND",
        payment_mode="OBLIGATION",
        visibility="PRIVATE",
        status="ACTIVE",
        created_by_user_id=creator.id,
        member_count=5,
        max_members=10,
    )

    # 3. Public group marked invite-only discoverability (Excluded)
    g_invite_only = Group(
        group_id="grp_inv_003",
        name="Unlisted Investment Club",
        description="Public charter but invite only link",
        group_image_url="https://example.com/inv.png",
        type="INVESTMENT_CLUB",
        payment_mode="VOLUNTARY",
        visibility="PUBLIC",
        status="ACTIVE",
        created_by_user_id=creator.id,
        member_count=2,
        max_members=10,
    )
    vis_invite_only = GroupVisibilitySettings(group_id="grp_inv_003", invite_only_discoverability=True)

    db_session.add_all([g_public, vis_public, g_private, g_invite_only, vis_invite_only])
    db_session.commit()

    app.dependency_overrides[get_session] = lambda: db_session
    app.dependency_overrides[get_optional_current_user] = lambda: None
    client = TestClient(app)

    response = client.get("/api/v1/groups/explore")
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["total"] == 1
    assert len(data["items"]) == 1
    assert data["items"][0]["group_id"] == "grp_pub_001"
    assert data["items"][0]["name"] == "Public Kampala Chama"

    app.dependency_overrides.clear()


def test_search_and_type_filters(db_session: Session):
    creator = User(id=uuid.uuid4(), phone_number="+256701111002", full_name="Creator Two", kyc_tier=2)
    db_session.add(creator)
    db_session.commit()

    g1 = Group(
        group_id="grp_kampala",
        name="Kampala Tech Traders",
        description="Daily micro-savings",
        group_image_url="",
        type="MERRY_GO_ROUND",
        payment_mode="OBLIGATION",
        visibility="PUBLIC",
        status="ACTIVE",
        created_by_user_id=creator.id,
        member_count=4,
    )
    g2 = Group(
        group_id="grp_entebbe",
        name="Entebbe Builders Circle",
        description="Saving for construction tools",
        group_image_url="",
        type="TARGET_SAVINGS",
        payment_mode="VOLUNTARY",
        visibility="PUBLIC",
        status="ACTIVE",
        created_by_user_id=creator.id,
        member_count=6,
    )
    db_session.add_all([g1, g2])
    db_session.commit()

    app.dependency_overrides[get_session] = lambda: db_session
    app.dependency_overrides[get_optional_current_user] = lambda: None
    client = TestClient(app)

    # Search keyword
    res_q = client.get("/api/v1/groups/explore?q=Kampala")
    assert res_q.status_code == 200
    assert res_q.json()["total"] == 1
    assert res_q.json()["items"][0]["group_id"] == "grp_kampala"

    # Type filter
    res_type = client.get("/api/v1/groups/explore?type=TARGET_SAVINGS")
    assert res_type.status_code == 200
    assert res_type.json()["total"] == 1
    assert res_type.json()["items"][0]["group_id"] == "grp_entebbe"

    app.dependency_overrides.clear()


def test_capacity_and_caller_eligibility(db_session: Session):
    creator = User(id=uuid.uuid4(), phone_number="+256701111003", full_name="Creator Three", kyc_tier=3)
    user_alice = User(id=uuid.uuid4(), phone_number="+256701111004", full_name="Alice User", kyc_tier=1, trust_score=60)
    db_session.add_all([creator, user_alice])
    db_session.commit()

    # Group with strict governance (KYC Tier 2, Trust Score 80)
    g_strict = Group(
        group_id="grp_strict_01",
        name="High Roller Chama",
        description="Strict circle",
        group_image_url="",
        type="MERRY_GO_ROUND",
        payment_mode="OBLIGATION",
        visibility="PUBLIC",
        status="ACTIVE",
        created_by_user_id=creator.id,
        member_count=2,
        max_members=5,
    )
    gov_strict = GroupGovernanceSettings(
        group_id="grp_strict_01",
        minimum_kyc_tier=2,
        minimum_trust_score=80,
        requires_admin_approval=True,
    )

    # Group that is full
    g_full = Group(
        group_id="grp_full_02",
        name="Capacity Filled Circle",
        description="No space",
        group_image_url="",
        type="MERRY_GO_ROUND",
        payment_mode="OBLIGATION",
        visibility="PUBLIC",
        status="ACTIVE",
        created_by_user_id=creator.id,
        member_count=5,
        max_members=5,
    )

    db_session.add_all([g_strict, gov_strict, g_full])
    db_session.commit()

    app.dependency_overrides[get_session] = lambda: db_session
    app.dependency_overrides[get_optional_current_user] = lambda: user_alice
    client = TestClient(app)

    # Alice views explore (hide_full=True by default)
    res = client.get("/api/v1/groups/explore")
    assert res.status_code == 200
    items = res.json()["items"]
    assert len(items) == 1
    strict_card = items[0]
    assert strict_card["group_id"] == "grp_strict_01"
    # Alice is ineligible due to KYC 1 < 2 and trust 60 < 80
    assert strict_card["caller_status"]["is_eligible"] is False
    assert len(strict_card["caller_status"]["ineligibility_reasons"]) == 2

    # If Alice passes eligible_only=True, strict group should be filtered out
    res_elig = client.get("/api/v1/groups/explore?eligible_only=true")
    assert res_elig.status_code == 200
    assert res_elig.json()["total"] == 0

    # If Alice asks to show full groups (hide_full=False), full group appears
    res_full = client.get("/api/v1/groups/explore?hide_full=false")
    assert res_full.status_code == 200
    assert res_full.json()["total"] == 2

    app.dependency_overrides.clear()


def test_already_joined_group_is_excluded(db_session: Session):
    user_bob = User(id=uuid.uuid4(), phone_number="+256701111005", full_name="Bob Member", kyc_tier=2)
    db_session.add(user_bob)
    db_session.commit()

    g = Group(
        group_id="grp_bob_joined",
        name="Bob's Existing Group",
        description="Public group Bob joined",
        group_image_url="",
        type="MERRY_GO_ROUND",
        payment_mode="OBLIGATION",
        visibility="PUBLIC",
        status="ACTIVE",
        created_by_user_id=user_bob.id,
        member_count=1,
    )
    membership = GroupMembership(
        membership_id="mem_bob_01",
        group_id="grp_bob_joined",
        user_id=user_bob.id,
        role="ADMIN",
        status="ACTIVE",
    )
    db_session.add_all([g, membership])
    db_session.commit()

    app.dependency_overrides[get_session] = lambda: db_session
    app.dependency_overrides[get_optional_current_user] = lambda: user_bob
    client = TestClient(app)

    # Bob should not see groups he's already actively in
    res = client.get("/api/v1/groups/explore")
    assert res.status_code == 200
    assert res.json()["total"] == 0

    app.dependency_overrides.clear()


def test_categories_and_preview_endpoints(db_session: Session):
    admin = User(id=uuid.uuid4(), phone_number="+256701111006", full_name="Admin Chief", kyc_tier=3)
    db_session.add(admin)
    db_session.commit()

    g = Group(
        group_id="grp_preview_01",
        name="Precious Chama",
        description="Previewable group",
        group_image_url="",
        type="MERRY_GO_ROUND",
        payment_mode="OBLIGATION",
        visibility="PUBLIC",
        status="ACTIVE",
        created_by_user_id=admin.id,
        member_count=3,
        max_members=12,
    )
    rot = RotatingGroupDetails(
        group_id="grp_preview_01",
        contribution_amount=20000.0,
        saving_days_per_cycle=7,
        payouts_per_cycle=1,
        collection_frequency_days=7,
        group_start_time=1700000000000,
        payout_order_strategy="Randomized by App",
        total_expected_pool_per_cycle=240000.0,
        minimum_kyc_tier=1,
        require_guarantor=False,
        guarantor_default_action="COVER_OBLIGATION",
        allow_partial_payments=False,
        allow_advance_deposits=True,
    )
    health = GroupHealth(
        group_id="grp_preview_01",
        health_grade="A+",
        risk_level="LOW",
        on_time_repayment_rate_pct=99.2,
    )
    db_session.add_all([g, rot, health])
    db_session.commit()

    app.dependency_overrides[get_session] = lambda: db_session
    app.dependency_overrides[get_optional_current_user] = lambda: admin
    client = TestClient(app)

    # 1. Test Categories
    cat_res = client.get("/api/v1/groups/explore/categories")
    assert cat_res.status_code == 200
    cats = cat_res.json()["categories"]
    assert len(cats) >= 3
    # Check category IDs exist
    cat_ids = [c["id"] for c in cats]
    assert "trending_rotating" in cat_ids
    assert "high_trust_circles" in cat_ids

    # 2. Test Preview
    prev_res = client.get("/api/v1/groups/explore/grp_preview_01/preview")
    assert prev_res.status_code == 200
    pdata = prev_res.json()
    assert pdata["group"]["group_id"] == "grp_preview_01"
    assert pdata["creator_name"] == "Admin Chief"
    assert pdata["payout_order_strategy"] == "Randomized by App"
    assert len(pdata["join_requirements_checklist"]) > 0

    # 3. Test Preview 404 for non-existent or private group
    prev_404 = client.get("/api/v1/groups/explore/non_existent_group_xyz/preview")
    assert prev_404.status_code == 404

    app.dependency_overrides.clear()

