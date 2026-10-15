from fastapi import APIRouter
from .create_welfare_fund_group import router as create_router, create_welfare_fund_group
from .get_welfare_fund_dashboard import router as dashboard_router, get_welfare_fund_dashboard
from .update_welfare_fund_settings import router as settings_router, update_welfare_fund_settings
from .submit_claim import router as claim_router, submit_claim
from .vote_on_claim import router as vote_router, vote_on_claim
from .release_claim import router as release_router, release_claim

router = APIRouter(prefix="/api/v1/groups/welfare-fund", tags=["Welfare Fund Groups"])
router.include_router(create_router)
router.include_router(dashboard_router)
router.include_router(settings_router)
router.include_router(claim_router)
router.include_router(vote_router)
router.include_router(release_router)
router.router = router

__all__ = [
    "router",
    "create_welfare_fund_group",
    "get_welfare_fund_dashboard",
    "update_welfare_fund_settings",
    "submit_claim",
    "vote_on_claim",
    "release_claim",
]
