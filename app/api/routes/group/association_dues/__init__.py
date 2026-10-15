from fastapi import APIRouter
from .create_association_dues_group import router as create_association_dues_group_router, create_association_dues_group
from .get_association_dashboard import router as get_association_dashboard_router, get_association_dashboard
from .update_association_settings import router as update_association_settings_router, update_association_settings
from .pay_dues import router as pay_dues_router, pay_dues
from .trigger_treasury_sweep import router as trigger_treasury_sweep_router, trigger_treasury_sweep
from .list_defaulters import router as list_defaulters_router, list_defaulters
from .grant_fee_exemption import router as grant_fee_exemption_router, grant_fee_exemption
from .list_fee_exemptions import router as list_fee_exemptions_router, list_fee_exemptions
from .update_fee_exemption import router as update_fee_exemption_router, update_fee_exemption
from .revoke_fee_exemption import router as revoke_fee_exemption_router, revoke_fee_exemption

router = APIRouter(prefix="/api/v1/groups/association-dues", tags=["Association Dues Groups"])
router.include_router(create_association_dues_group_router)
router.include_router(get_association_dashboard_router)
router.include_router(update_association_settings_router)
router.include_router(pay_dues_router)
router.include_router(trigger_treasury_sweep_router)
router.include_router(list_defaulters_router)
router.include_router(grant_fee_exemption_router)
router.include_router(list_fee_exemptions_router)
router.include_router(update_fee_exemption_router)
router.include_router(revoke_fee_exemption_router)
router.router = router

__all__ = [
    "router",
    "create_association_dues_group",
    "get_association_dashboard",
    "update_association_settings",
    "pay_dues",
    "trigger_treasury_sweep",
    "list_defaulters",
    "grant_fee_exemption",
    "list_fee_exemptions",
    "update_fee_exemption",
    "revoke_fee_exemption",
]
