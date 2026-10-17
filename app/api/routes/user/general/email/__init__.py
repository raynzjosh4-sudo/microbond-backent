from fastapi import APIRouter
from .link_backup_email import router as link_router, link_backup_email
from .verify_backup_email import router as verify_router, verify_backup_email
from .export_individual_statement import (
    router as export_router,
    export_individual_statement,
)
from .get_backup_email import router as get_email_router, get_backup_email

router = APIRouter(prefix="/email", tags=["User Email Management"])
router.include_router(get_email_router)
router.include_router(link_router)
router.include_router(verify_router)
router.include_router(export_router)

__all__ = [
    "router",
    "get_backup_email",
    "link_backup_email",
    "verify_backup_email",
    "export_individual_statement",
]
