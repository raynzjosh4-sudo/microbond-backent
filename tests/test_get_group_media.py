import uuid
import pytest
from app.api.routes.group.chat.get_group_media import (
    extract_links_from_text,
    _build_gallery_items_from_message,
    MediaGalleryItem,
    MediaCountsSummary,
    GroupMediaGalleryResponse
)
from app.models.group.chat import GroupChatMessage

def test_extract_links_from_text():
    text = (
        "Check out our website at https://microbond.org and the repo: "
        "www.github.com/microbond/core! Also read http://example.com/doc?id=123."
    )
    links = extract_links_from_text(text)
    assert len(links) == 3
    assert ("https://microbond.org", "microbond.org") in links
    assert ("https://www.github.com/microbond/core", "github.com") in links
    assert ("http://example.com/doc?id=123", "example.com") in links

def test_extract_links_empty_and_no_links():
    assert extract_links_from_text(None) == []
    assert extract_links_from_text("") == []
    assert extract_links_from_text("Hello everyone, how are you?") == []

def test_build_gallery_items_from_single_media():
    msg = GroupChatMessage(
        id=uuid.uuid4(),
        group_id="grp_1",
        sender_id="usr_1",
        message_type="MEDIA",
        media_url="https://r2.dev/groups/grp_1/photo.jpg",
        media_type="IMAGE",
        media_mime_type="image/jpeg",
        media_size_bytes=1048576,
        media_width=1920,
        media_height=1080,
        aspect_ratio=1.778,
        message_text="Photo caption",
        created_at=1700000000000
    )
    items = _build_gallery_items_from_message(
        msg,
        category_filter="MEDIA",
        sender_name="Alice",
        is_outgoing=False
    )
    assert len(items) == 1
    item = items[0]
    assert item.category == "MEDIA"
    assert item.media_url == "https://r2.dev/groups/grp_1/photo.jpg"
    assert item.media_type == "IMAGE"
    assert item.width == 1920
    assert item.height == 1080
    assert item.text_content == "Photo caption"
    assert item.sender_name == "Alice"

def test_build_gallery_items_from_multi_attachments():
    msg = GroupChatMessage(
        id=uuid.uuid4(),
        group_id="grp_1",
        sender_id="usr_2",
        message_type="MEDIA",
        message_text="Album of pictures",
        attachments=[
            {
                "attachment_id": "att_1",
                "url": "https://r2.dev/pic1.jpg",
                "media_type": "IMAGE",
                "mime_type": "image/jpeg",
                "size_bytes": 500000,
                "width": 800,
                "height": 600,
                "aspect_ratio": 1.333
            },
            {
                "attachment_id": "att_2",
                "url": "https://r2.dev/video1.mp4",
                "media_type": "VIDEO",
                "mime_type": "video/mp4",
                "size_bytes": 5000000,
                "width": 1280,
                "height": 720,
                "aspect_ratio": 1.778,
                "duration_seconds": 30
            }
        ],
        created_at=1700000005000
    )
    items = _build_gallery_items_from_message(
        msg,
        category_filter="MEDIA",
        sender_name="You",
        is_outgoing=True
    )
    assert len(items) == 2
    assert items[0].item_id == "att_1"
    assert items[0].media_type == "IMAGE"
    assert items[1].item_id == "att_2"
    assert items[1].media_type == "VIDEO"
    assert items[1].duration_seconds == 30
    assert items[1].is_outgoing is True

def test_build_gallery_items_from_document():
    msg = GroupChatMessage(
        id=uuid.uuid4(),
        group_id="grp_1",
        sender_id="usr_1",
        message_type="MEDIA",
        media_url="https://r2.dev/report.pdf",
        media_type="DOCUMENT",
        media_mime_type="application/pdf",
        media_size_bytes=2450000,
        message_text="Financial Statement Q3",
        created_at=1700000010000
    )
    # Asking for DOCS
    doc_items = _build_gallery_items_from_message(
        msg,
        category_filter="DOCS",
        sender_name="Treasurer",
        is_outgoing=False
    )
    assert len(doc_items) == 1
    assert doc_items[0].category == "DOCS"
    assert doc_items[0].media_url == "https://r2.dev/report.pdf"
    assert doc_items[0].size_bytes == 2450000

    # Asking for MEDIA (should return empty for doc message)
    media_items = _build_gallery_items_from_message(
        msg,
        category_filter="MEDIA",
        sender_name="Treasurer",
        is_outgoing=False
    )
    assert len(media_items) == 0

def test_build_gallery_items_from_links():
    msg = GroupChatMessage(
        id=uuid.uuid4(),
        group_id="grp_1",
        sender_id="usr_3",
        message_type="TEXT",
        message_text="Read this article: https://example.com/news",
        created_at=1700000020000
    )
    link_items = _build_gallery_items_from_message(
        msg,
        category_filter="LINKS",
        sender_name="Bob",
        is_outgoing=False
    )
    assert len(link_items) == 1
    assert link_items[0].category == "LINKS"
    assert link_items[0].link_url == "https://example.com/news"
    assert link_items[0].link_domain == "example.com"

def test_api_routes_with_test_client():
    from fastapi.testclient import TestClient
    from sqlmodel import SQLModel, create_engine, Session
    from sqlalchemy.pool import StaticPool
    from app.main import app
    from app.core.database import get_session
    from app.api.dependencies import get_current_user
    from app.models.user.user import User
    from app.models.group.group import GroupMembership
    import sqlite3
    sqlite3.register_adapter(uuid.UUID, lambda u: str(u))

    test_engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool
    )
    SQLModel.metadata.create_all(test_engine)

    user_id = uuid.uuid4()
    test_user = User(
        id=user_id,
        phone_number="+256700111222",
        full_name="Tester",
        is_phone_verified=True
    )
    group_id = "test_grp_media_123"
    membership = GroupMembership(
        membership_id=uuid.uuid4(),
        group_id=group_id,
        user_id=user_id,
        role="MEMBER",
        status="ACTIVE"
    )
    msg1 = GroupChatMessage(
        id=uuid.uuid4(),
        group_id=group_id,
        sender_id=str(user_id),
        message_type="MEDIA",
        media_url="https://r2.dev/pic1.jpg",
        media_type="IMAGE",
        created_at=1700000000000
    )
    msg2 = GroupChatMessage(
        id=uuid.uuid4(),
        group_id=group_id,
        sender_id=str(user_id),
        message_type="MEDIA",
        media_url="https://r2.dev/statement.pdf",
        media_type="DOCUMENT",
        created_at=1700000001000
    )
    msg3 = GroupChatMessage(
        id=uuid.uuid4(),
        group_id=group_id,
        sender_id=str(user_id),
        message_type="TEXT",
        message_text="Check out https://microbond.org for docs",
        created_at=1700000002000
    )

    with Session(test_engine) as s:
        s.add(test_user)
        s.add(membership)
        s.add(msg1)
        s.add(msg2)
        s.add(msg3)
        s.commit()

    def override_get_session():
        with Session(test_engine) as session:
            yield session

    def override_get_current_user():
        with Session(test_engine) as session:
            return session.get(User, user_id)

    app.dependency_overrides[get_session] = override_get_session
    app.dependency_overrides[get_current_user] = override_get_current_user

    try:
        client = TestClient(app)
        
        # 1. Fetch Media (Images/Videos)
        res_media = client.get(f"/api/v1/groups/{group_id}/media?category=MEDIA")
        assert res_media.status_code == 200
        data_media = res_media.json()
        assert data_media["status"] == "success"
        assert data_media["category"] == "MEDIA"
        assert len(data_media["data"]) == 1
        assert data_media["data"][0]["media_type"] == "IMAGE"
        assert data_media["counts"]["media"] == 1
        assert data_media["counts"]["docs"] == 1
        assert data_media["counts"]["links"] == 1

        # 2. Fetch Docs
        res_docs = client.get(f"/api/v1/groups/{group_id}/media?category=DOCS")
        assert res_docs.status_code == 200
        data_docs = res_docs.json()
        assert len(data_docs["data"]) == 1
        assert data_docs["data"][0]["category"] == "DOCS"
        assert data_docs["data"][0]["media_url"] == "https://r2.dev/statement.pdf"

        # 3. Fetch Links
        res_links = client.get(f"/api/v1/groups/{group_id}/media?category=LINKS")
        assert res_links.status_code == 200
        data_links = res_links.json()
        assert len(data_links["data"]) == 1
        assert data_links["data"][0]["category"] == "LINKS"
        assert data_links["data"][0]["link_url"] == "https://microbond.org"

        # 4. Fetch Summary
        res_summary = client.get(f"/api/v1/groups/{group_id}/media/summary")
        assert res_summary.status_code == 200
        data_summary = res_summary.json()
        assert data_summary["counts"]["media"] == 1
        assert data_summary["counts"]["docs"] == 1
        assert data_summary["counts"]["links"] == 1
        assert len(data_summary["recent_media"]) == 1
    finally:
        app.dependency_overrides.clear()

