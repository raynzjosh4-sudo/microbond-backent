import sys
sys.path.insert(0, '.')

from fastapi.testclient import TestClient
from app.main import app
from app.core.database import engine
from sqlmodel import Session, select
from app.models.group.group import Group, GroupMembership
from app.models.group.settings import GroupFinancialSettings
from app.models.user.user import User
from app.api.dependencies import get_current_user

client = TestClient(app)

with Session(engine) as session:
    admin_user = session.exec(select(User)).first()
    group = session.exec(select(Group)).first()
    assert admin_user and group, "Need user and group"

    # Ensure admin membership
    membership = session.exec(
        select(GroupMembership).where(
            GroupMembership.group_id == group.group_id,
            GroupMembership.user_id == admin_user.id
        )
    ).first()
    if not membership:
        import uuid
        membership = GroupMembership(
            membership_id=str(uuid.uuid4()),
            group_id=group.group_id,
            user_id=admin_user.id,
            role="ADMIN",
            status="ACTIVE"
        )
        session.add(membership)
        session.commit()
    else:
        membership.role = "ADMIN"
        session.add(membership)
        session.commit()

    fin = session.exec(select(GroupFinancialSettings).where(GroupFinancialSettings.group_id == group.group_id)).first()
    if not fin:
        fin = GroupFinancialSettings(group_id=group.group_id, late_fee_amount=100.0, reserve_fund_percentage=5.0)
        session.add(fin)
        session.commit()

    orig_name = group.name
    orig_desc = group.description
    orig_reserve = fin.reserve_fund_percentage

    # Override current user
    app.dependency_overrides[get_current_user] = lambda: admin_user

    # Partial update: ONLY send late_fee_amount via PATCH
    response = client.patch(
        f"/api/v1/groups/{group.group_id}/settings/general",
        json={"late_fee_amount": 7500.0}
    )
    assert response.status_code == 200, response.text

    session.expire_all()
    updated_group = session.exec(select(Group).where(Group.group_id == group.group_id)).first()
    updated_fin = session.exec(select(GroupFinancialSettings).where(GroupFinancialSettings.group_id == group.group_id)).first()

    assert updated_fin.late_fee_amount == 7500.0, "late_fee_amount should be updated"
    assert updated_group.name == orig_name, "group name must NOT be overwritten"
    assert updated_group.description == orig_desc, "group description must NOT be overwritten"
    assert updated_fin.reserve_fund_percentage == orig_reserve, "reserve_fund_percentage must NOT be overwritten"

    print("SUCCESS: Partial settings update verified! Untouched fields remain intact.")
