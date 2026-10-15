from fastapi import APIRouter
from .change_member_role import router as change_member_role_router, change_member_role
from .remove_or_kick_member import router as remove_or_kick_member_router, remove_or_kick_member
from .transfer_group_ownership import router as transfer_group_ownership_router, transfer_group_ownership
from .helpers import VALID_ROLES, verify_admin

router = APIRouter(prefix="/api/v1/groups", tags=["Group Member Administration"])
router.include_router(change_member_role_router)
router.include_router(remove_or_kick_member_router)
router.include_router(transfer_group_ownership_router)
router.router = router

__all__ = [
    "router",
    "change_member_role",
    "remove_or_kick_member",
    "transfer_group_ownership",
    "VALID_ROLES",
    "verify_admin",
]
