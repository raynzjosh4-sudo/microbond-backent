from fastapi import APIRouter
from .pin.set_pin import set_app_pin
from .pin.verify_pin import verify_app_pin
from .pin.change_pin import change_app_pin
from .pin.forgot_pin.request_otp import request_forgot_pin_otp
from .pin.forgot_pin.verify_otp import verify_forgot_pin_otp
from .phone_change.request_otp import request_phone_change_otp
from .phone_change.verify_otp import verify_phone_change_otp
from .recovery.request_otp import request_recovery_otp
from .recovery.verify_otp import verify_recovery_otp

router = APIRouter(tags=["Account Recovery"])
router.include_router(request_recovery_otp.router)
router.include_router(verify_recovery_otp.router)
router.include_router(set_app_pin.router)
router.include_router(verify_app_pin.router)
router.include_router(change_app_pin.router)
router.include_router(request_forgot_pin_otp.router)
router.include_router(verify_forgot_pin_otp.router)
router.include_router(request_phone_change_otp.router)
router.include_router(verify_phone_change_otp.router)

__all__ = [
    "router",
    "request_recovery_otp",
    "verify_recovery_otp",
    "set_app_pin",
    "verify_app_pin",
    "change_app_pin",
    "request_forgot_pin_otp",
    "verify_forgot_pin_otp",
    "request_phone_change_otp",
    "verify_phone_change_otp",
]
