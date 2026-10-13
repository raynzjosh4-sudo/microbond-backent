from fastapi import APIRouter
from .link_backup_email import router as link_router, link_backup_email
from .verify_backup_email import router as verify_router, verify_backup_email
from .export_individual_statement import (
    router as export_router,
    export_individual_statement,
)

router = APIRouter(prefix="/email", tags=["User Email Management"])
router.include_router(link_router)
router.include_router(verify_router)
router.include_router(export_router)

__all__ = [
    "router",
    "link_backup_email",
    "verify_backup_email",
    "export_individual_statement",
]
