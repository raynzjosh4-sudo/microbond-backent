import uuid

from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, create_engine, select
from sqlmodel.pool import StaticPool

from app.api.dependencies import get_current_user
from app.core.database import get_session
from app.main import app
from app.models.group.chat import GroupChatMessage
from app.models.group.core.group_membership import GroupMembership
from app.models.group.core.group import Group
from app.models.group.target_savings import TargetSavingsGroupDetails
from app.models.user.user import User


def test_chat_open_posts_multi_payout_destination_until_member_sets_one():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)

    with Session(engine) as session:
        user = User(
            id=uuid.uuid4(),
            phone_number="+256700000401",
            full_name="Payout member",
            kyc_tier=2,
        )
        group_id = str(uuid.uuid4())
        group = Group(
            group_id=group_id,
            name="Payout destination test",
            group_image_url="",
            type="GOAL_SAVINGS",
            payment_mode="VOLUNTARY",
            created_by_user_id=user.id,
        )
        membership = GroupMembership(
            membership_id=str(uuid.uuid4()),
            group_id=group_id,
            user_id=user.id,
            role="ADMIN",
            status="ACTIVE",
        )
        session.add_all(
            [
                user,
                group,
                membership,
                TargetSavingsGroupDetails(group_id=group_id, allow_multi_payout=True),
            ]
        )
        session.commit()

        app.dependency_overrides[get_session] = lambda: session
        app.dependency_overrides[get_current_user] = lambda: user
        client = TestClient(app)
        try:
            response = client.get(f"/api/v1/groups/{group_id}/chat/messages")
            assert response.status_code == 200, response.text
            assert response.json()["data"][0]["message_type"] == "MULTIPAYOUT_DESTINATION"
            assert response.json()["data"][0]["sender_id"] == str(user.id)
            assert response.json()["data"][0]["is_outgoing"] is True

            prompt = session.exec(
                select(GroupChatMessage).where(
                    GroupChatMessage.group_id == group_id,
                    GroupChatMessage.message_type == "MULTIPAYOUT_DESTINATION",
                )
            ).first()
            assert prompt is not None
            assert prompt.sender_id == str(user.id)

            response = client.get(f"/api/v1/groups/{group_id}/chat/messages")
            assert response.status_code == 200, response.text
            assert len(
                session.exec(
                    select(GroupChatMessage).where(
                        GroupChatMessage.group_id == group_id,
                        GroupChatMessage.message_type == "MULTIPAYOUT_DESTINATION",
                    )
                ).all()
            ) == 2

            membership.payout_destination_id = "verified-destination"
            session.add(membership)
            session.commit()

            response = client.get(f"/api/v1/groups/{group_id}/chat/messages")
            assert response.status_code == 200, response.text
            assert len(
                session.exec(
                    select(GroupChatMessage).where(
                        GroupChatMessage.group_id == group_id,
                        GroupChatMessage.message_type == "MULTIPAYOUT_DESTINATION",
                    )
                ).all()
            ) == 2
        finally:
            app.dependency_overrides.clear()
