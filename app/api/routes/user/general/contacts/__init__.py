from fastapi import APIRouter
from .sync_contacts import router as sync_router, sync_contacts
from .discover_groups import router as discover_router, discover_groups_by_contacts
from .schemas import (
    ContactSyncRequest,
    MatchedContact,
    DiscoverableContactGroup,
    ContactMemberSummary,
)

router = APIRouter(prefix="/contacts", tags=["Contacts Discovery"])
router.include_router(sync_router)
router.include_router(discover_router)

__all__ = [
    "router",
    "sync_contacts",
    "discover_groups_by_contacts",
    "ContactSyncRequest",
    "MatchedContact",
    "DiscoverableContactGroup",
    "ContactMemberSummary",
]

