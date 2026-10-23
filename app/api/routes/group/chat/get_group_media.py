import re
import uuid
import logging
from typing import Optional, List
from urllib.parse import urlparse

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlmodel import Session, select, func

from app.core.database import get_session
from app.api.dependencies import get_current_user
from app.models.user.user import User
from app.models.group.group import GroupMembership
from app.models.group.chat import GroupChatMessage

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/groups", tags=["Group Media"])

# Standard regex for extracting URLs from message text
URL_REGEX = re.compile(
    r'(?:https?://|www\.)[^\s<>"\'{}|\\^`\[\]]+',
    re.IGNORECASE
)

# ---------------------------------------------------------
# Schemas
# ---------------------------------------------------------

class MediaCountsSummary(BaseModel):
    media: int = Field(default=0, description="Total image and video files")
    docs: int = Field(default=0, description="Total documents (PDF, DOCX, etc.)")
    links: int = Field(default=0, description="Total shared web links")
    audio: int = Field(default=0, description="Total audio / voice notes")
    total: int = Field(default=0, description="Combined total count")


class MediaGalleryItem(BaseModel):
    item_id: str = Field(description="Unique identifier for this gallery item")
    message_id: str = Field(description="Underlying chat message UUID")
    category: str = Field(description="MEDIA, DOCS, LINKS, or AUDIO")
    
    # Media/File specific attributes
    media_url: Optional[str] = None
    media_type: Optional[str] = None  # IMAGE, VIDEO, DOCUMENT, AUDIO, VOICE_NOTE
    mime_type: Optional[str] = None
    filename: Optional[str] = None
    size_bytes: Optional[int] = None
    width: Optional[int] = None
    height: Optional[int] = None
    aspect_ratio: Optional[float] = None
    duration_seconds: Optional[int] = None
    
    # Link specific attributes
    link_url: Optional[str] = None
    link_domain: Optional[str] = None
    
    # Text / Caption context
    text_content: Optional[str] = None
    
    # Sender Profile
    sender_id: str
    sender_name: str
    is_outgoing: bool = False
    
    # Timestamp
    created_at: int


class GroupMediaGalleryResponse(BaseModel):
    status: str = "success"
    group_id: str
    category: str
    counts: MediaCountsSummary
    data: List[MediaGalleryItem] = Field(default_factory=list)
    has_more: bool = False
    next_cursor: Optional[int] = None


class GroupMediaOverviewResponse(BaseModel):
    status: str = "success"
    group_id: str
    counts: MediaCountsSummary
    recent_media: List[MediaGalleryItem] = Field(default_factory=list)


# ---------------------------------------------------------
# Helper Functions
# ---------------------------------------------------------

def extract_links_from_text(text: Optional[str]) -> List[tuple[str, str]]:
    """
    Extracts all URLs and their root domains from text.
    Returns list of (normalized_url, domain).
    """
    if not text:
        return []
    
    matches = URL_REGEX.findall(text)
    results = []
    seen = set()

    for match in matches:
        raw_url = match.strip(".,;:?!)\"'")
        if not raw_url or raw_url in seen:
            continue
        seen.add(raw_url)

        normalized = raw_url if raw_url.startswith(("http://", "https://")) else f"https://{raw_url}"
        try:
            parsed = urlparse(normalized)
            domain = parsed.netloc or parsed.path.split('/')[0]
            domain = domain.lower()
            if domain.startswith("www."):
                domain = domain[4:]
            results.append((normalized, domain))
        except Exception:
            results.append((normalized, ""))

    return results


def _compute_group_media_counts(session: Session, group_id: str) -> MediaCountsSummary:
    """Executes indexed aggregate counts for group media, docs, links, and audio."""
    # 1. Media (Images & Videos)
    media_count = session.exec(
        select(func.count()).select_from(GroupChatMessage).where(
            GroupChatMessage.group_id == group_id,
            GroupChatMessage.is_deleted == False,
            (
                GroupChatMessage.media_type.in_(["IMAGE", "VIDEO"])
                | (
                    (GroupChatMessage.media_type == None)
                    & (GroupChatMessage.message_type == "MEDIA")
                    & (GroupChatMessage.media_url != None)
                )
            )
        )
    ).one() or 0

    # 2. Docs (Documents)
    docs_count = session.exec(
        select(func.count()).select_from(GroupChatMessage).where(
            GroupChatMessage.group_id == group_id,
            GroupChatMessage.is_deleted == False,
            GroupChatMessage.media_type.in_(["DOCUMENT", "DOC", "FILE"])
        )
    ).one() or 0

    # 3. Links (Messages with web links)
    links_count = session.exec(
        select(func.count()).select_from(GroupChatMessage).where(
            GroupChatMessage.group_id == group_id,
            GroupChatMessage.is_deleted == False,
            (GroupChatMessage.message_text.ilike("%http%")) | (GroupChatMessage.message_text.ilike("%www.%"))
        )
    ).one() or 0

    # 4. Audio (Audio & Voice Notes)
    audio_count = session.exec(
        select(func.count()).select_from(GroupChatMessage).where(
            GroupChatMessage.group_id == group_id,
            GroupChatMessage.is_deleted == False,
            GroupChatMessage.media_type.in_(["AUDIO", "VOICE_NOTE"])
        )
    ).one() or 0

    return MediaCountsSummary(
        media=media_count,
        docs=docs_count,
        links=links_count,
        audio=audio_count,
        total=media_count + docs_count + links_count + audio_count
    )


def _build_gallery_items_from_message(
    m: GroupChatMessage,
    category_filter: str,
    sender_name: str,
    is_outgoing: bool
) -> List[MediaGalleryItem]:
    """Expands message or multi-file attachments into individual gallery items matching the category."""
    items: List[MediaGalleryItem] = []
    cat_upper = category_filter.upper()

    # 1. Links Category
    if cat_upper in ("LINKS", "LINK", "ALL"):
        links = extract_links_from_text(m.message_text)
        for idx, (url, domain) in enumerate(links):
            items.append(
                MediaGalleryItem(
                    item_id=f"{m.id}_link_{idx}",
                    message_id=str(m.id),
                    category="LINKS",
                    link_url=url,
                    link_domain=domain,
                    text_content=m.message_text,
                    sender_id=m.sender_id,
                    sender_name=sender_name,
                    is_outgoing=is_outgoing,
                    created_at=m.created_at
                )
            )
        if cat_upper in ("LINKS", "LINK"):
            return items

    # 2. Multi-Attachment Messages (Albums or batches)
    if m.attachments and isinstance(m.attachments, list):
        for idx, att in enumerate(m.attachments):
            if not isinstance(att, dict):
                continue
            att_type = (att.get("media_type") or m.media_type or "IMAGE").upper()
            att_url = att.get("url") or m.media_url
            if not att_url:
                continue

            # Determine item category
            if att_type in ("IMAGE", "VIDEO"):
                item_cat = "MEDIA"
            elif att_type in ("DOCUMENT", "DOC", "FILE"):
                item_cat = "DOCS"
            elif att_type in ("AUDIO", "VOICE_NOTE"):
                item_cat = "AUDIO"
            else:
                item_cat = "MEDIA"

            if cat_upper != "ALL" and cat_upper not in (item_cat, f"{item_cat}S", item_cat[:-1] if item_cat.endswith("S") else item_cat):
                continue

            items.append(
                MediaGalleryItem(
                    item_id=att.get("attachment_id") or f"{m.id}_att_{idx}",
                    message_id=str(m.id),
                    category=item_cat,
                    media_url=att_url,
                    media_type=att_type,
                    mime_type=att.get("mime_type") or m.media_mime_type,
                    filename=att.get("filename"),
                    size_bytes=att.get("size_bytes") or m.media_size_bytes,
                    width=att.get("width") or m.media_width,
                    height=att.get("height") or m.media_height,
                    aspect_ratio=att.get("aspect_ratio") or m.aspect_ratio,
                    duration_seconds=att.get("duration_seconds") or m.media_duration_seconds,
                    text_content=m.message_text,
                    sender_id=m.sender_id,
                    sender_name=sender_name,
                    is_outgoing=is_outgoing,
                    created_at=m.created_at
                )
            )
        if items:
            return items

    # 3. Single Media Messages
    if m.media_url:
        single_type = (m.media_type or "IMAGE").upper()
        if single_type in ("IMAGE", "VIDEO"):
            item_cat = "MEDIA"
        elif single_type in ("DOCUMENT", "DOC", "FILE"):
            item_cat = "DOCS"
        elif single_type in ("AUDIO", "VOICE_NOTE"):
            item_cat = "AUDIO"
        else:
            item_cat = "MEDIA"

        if cat_upper == "ALL" or cat_upper in (item_cat, f"{item_cat}S", item_cat[:-1] if item_cat.endswith("S") else item_cat):
            items.append(
                MediaGalleryItem(
                    item_id=str(m.id),
                    message_id=str(m.id),
                    category=item_cat,
                    media_url=m.media_url,
                    media_type=single_type,
                    mime_type=m.media_mime_type,
                    filename=None,
                    size_bytes=m.media_size_bytes,
                    width=m.media_width,
                    height=m.media_height,
                    aspect_ratio=m.aspect_ratio,
                    duration_seconds=m.media_duration_seconds,
                    text_content=m.message_text,
                    sender_id=m.sender_id,
                    sender_name=sender_name,
                    is_outgoing=is_outgoing,
                    created_at=m.created_at
                )
            )

    return items


# ---------------------------------------------------------
# Endpoints
# ---------------------------------------------------------

@router.get(
    "/{group_id}/media",
    response_model=GroupMediaGalleryResponse,
    summary="Get Categorized Group Media, Docs, and Links",
    description="WhatsApp-style media gallery endpoint. Returns photos/videos (MEDIA), documents (DOCS), shared links (LINKS), or audio (AUDIO) with badge counts and pagination."
)
@router.get(
    "/{group_id}/chat/media",
    response_model=GroupMediaGalleryResponse,
    summary="Get Categorized Group Media (Alias)",
    include_in_schema=False
)
async def get_group_media(
    group_id: str,
    category: str = Query(
        "MEDIA",
        description="Filter category: 'MEDIA' (Images & Videos), 'DOCS' (Documents/PDFs), 'LINKS' (Shared URLs), 'AUDIO' (Voice notes/Audio), or 'ALL'"
    ),
    limit: int = Query(50, ge=1, le=100, description="Page size limit"),
    before_created_at: Optional[int] = Query(None, description="Cursor timestamp (epoch ms) to fetch older items"),
    include_counts: bool = Query(True, description="Whether to include category totals for tab badges"),
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """
    Returns media, documents, or links for a specific group.
    Supports tabbed browsing like WhatsApp (Media, Docs, Links) with pagination and sender profile tags.
    """
    # 1. Enforce active group membership
    membership = session.exec(
        select(GroupMembership).where(
            GroupMembership.group_id == group_id,
            GroupMembership.user_id == current_user.id,
            GroupMembership.status == "ACTIVE"
        )
    ).first()

    if not membership:
        raise HTTPException(
            status_code=403,
            detail="You must be an active member of this group to view shared media."
        )

    # 2. Build SQL filter based on category
    cat_upper = category.upper()
    stmt = select(GroupChatMessage).where(
        GroupChatMessage.group_id == group_id,
        GroupChatMessage.is_deleted == False
    )

    if cat_upper in ("MEDIA", "IMAGE", "VIDEO"):
        stmt = stmt.where(
            (GroupChatMessage.media_type.in_(["IMAGE", "VIDEO"]))
            | (
                (GroupChatMessage.media_type == None)
                & (GroupChatMessage.message_type == "MEDIA")
                & (GroupChatMessage.media_url != None)
            )
        )
    elif cat_upper in ("DOCS", "DOCUMENTS", "DOCUMENT", "DOC"):
        stmt = stmt.where(
            GroupChatMessage.media_type.in_(["DOCUMENT", "DOC", "FILE"])
        )
    elif cat_upper in ("LINKS", "LINK"):
        stmt = stmt.where(
            (GroupChatMessage.message_text.ilike("%http%"))
            | (GroupChatMessage.message_text.ilike("%www.%"))
        )
    elif cat_upper in ("AUDIO", "VOICE", "VOICE_NOTE"):
        stmt = stmt.where(
            GroupChatMessage.media_type.in_(["AUDIO", "VOICE_NOTE"])
        )
    else:  # ALL
        stmt = stmt.where(
            (GroupChatMessage.media_url != None)
            | (GroupChatMessage.message_type == "MEDIA")
            | (GroupChatMessage.message_text.ilike("%http%"))
            | (GroupChatMessage.message_text.ilike("%www.%"))
        )

    # 3. Apply cursor-based pagination
    if before_created_at:
        stmt = stmt.where(GroupChatMessage.created_at < before_created_at)

    stmt = stmt.order_by(GroupChatMessage.created_at.desc()).limit(limit + 1)
    raw_messages = session.exec(stmt).all()

    has_more = len(raw_messages) > limit
    messages = raw_messages[:limit]

    # 4. Resolve sender profiles
    sender_uuids = set()
    for m in messages:
        if m.sender_id and m.sender_id != "SYSTEM":
            try:
                sender_uuids.add(uuid.UUID(m.sender_id))
            except (ValueError, TypeError):
                pass

    user_map = {}
    if sender_uuids:
        users = session.exec(select(User).where(User.id.in_(sender_uuids))).all()
        user_map = {str(u.id): u for u in users}

    # 5. Expand messages into gallery items
    user_id_str = str(current_user.id)
    items: List[MediaGalleryItem] = []

    for m in messages:
        is_outgoing = (m.sender_id == user_id_str)
        sender_u = user_map.get(m.sender_id)
        if is_outgoing:
            s_name = "You"
        elif m.sender_id == "SYSTEM":
            s_name = "System"
        else:
            s_name = sender_u.full_name if sender_u and sender_u.full_name else "Member"

        msg_items = _build_gallery_items_from_message(
            m,
            category_filter=cat_upper,
            sender_name=s_name,
            is_outgoing=is_outgoing
        )
        items.extend(msg_items)

    # 6. Compute counts for tab badges if requested
    counts = _compute_group_media_counts(session, group_id) if include_counts else MediaCountsSummary()

    next_cursor = messages[-1].created_at if (has_more and messages) else None

    return GroupMediaGalleryResponse(
        status="success",
        group_id=group_id,
        category=cat_upper,
        counts=counts,
        data=items,
        has_more=has_more,
        next_cursor=next_cursor
    )


@router.get(
    "/{group_id}/media/summary",
    response_model=GroupMediaOverviewResponse,
    summary="Get Group Media Overview and Counts",
    description="Returns aggregate counts (media, docs, links, audio) and recent media thumbnails for the group settings screen."
)
@router.get(
    "/{group_id}/chat/media/summary",
    response_model=GroupMediaOverviewResponse,
    summary="Get Group Media Overview and Counts (Alias)",
    include_in_schema=False
)
async def get_group_media_summary(
    group_id: str,
    recent_limit: int = Query(6, ge=1, le=12, description="Number of recent media previews to return"),
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """
    Lightweight summary endpoint for Group Info / Settings screen:
    Provides counts + 4 to 6 recent photo/video thumbnails.
    """
    # 1. Enforce active group membership
    membership = session.exec(
        select(GroupMembership).where(
            GroupMembership.group_id == group_id,
            GroupMembership.user_id == current_user.id,
            GroupMembership.status == "ACTIVE"
        )
    ).first()

    if not membership:
        raise HTTPException(
            status_code=403,
            detail="You must be an active member of this group to view shared media."
        )

    # 2. Get counts
    counts = _compute_group_media_counts(session, group_id)

    # 3. Fetch latest few media messages for thumbnail row
    stmt = select(GroupChatMessage).where(
        GroupChatMessage.group_id == group_id,
        GroupChatMessage.is_deleted == False,
        (
            GroupChatMessage.media_type.in_(["IMAGE", "VIDEO"])
            | (
                (GroupChatMessage.media_type == None)
                & (GroupChatMessage.message_type == "MEDIA")
                & (GroupChatMessage.media_url != None)
            )
        )
    ).order_by(GroupChatMessage.created_at.desc()).limit(recent_limit)

    messages = session.exec(stmt).all()

    # 4. Resolve sender profiles
    sender_uuids = set()
    for m in messages:
        if m.sender_id and m.sender_id != "SYSTEM":
            try:
                sender_uuids.add(uuid.UUID(m.sender_id))
            except (ValueError, TypeError):
                pass

    user_map = {}
    if sender_uuids:
        users = session.exec(select(User).where(User.id.in_(sender_uuids))).all()
        user_map = {str(u.id): u for u in users}

    user_id_str = str(current_user.id)
    recent_items: List[MediaGalleryItem] = []

    for m in messages:
        is_outgoing = (m.sender_id == user_id_str)
        sender_u = user_map.get(m.sender_id)
        s_name = "You" if is_outgoing else (sender_u.full_name if sender_u and sender_u.full_name else "Member")

        items = _build_gallery_items_from_message(
            m,
            category_filter="MEDIA",
            sender_name=s_name,
            is_outgoing=is_outgoing
        )
        recent_items.extend(items)
        if len(recent_items) >= recent_limit:
            recent_items = recent_items[:recent_limit]
            break

    return GroupMediaOverviewResponse(
        status="success",
        group_id=group_id,
        counts=counts,
        recent_media=recent_items
    )
