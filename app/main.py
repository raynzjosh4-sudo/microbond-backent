from fastapi import FastAPI
from app.api.routes.authentication.account_recovery import request_recovery_otp, verify_recovery_otp, set_app_pin, request_phone_change_otp, verify_phone_change_otp

from app.core.database import init_db
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="Microbond Backend API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("startup")
def on_startup():
    init_db()

# Auth and Recovery
# Auth and Recovery
from app.api.routes.authentication.otp import main_router as otp_router
app.include_router(otp_router.router)
app.include_router(request_recovery_otp.router, tags=["Account Recovery"])
app.include_router(verify_recovery_otp.router, tags=["Account Recovery"])
app.include_router(set_app_pin.router, tags=["Account Recovery"])
app.include_router(request_phone_change_otp.router, tags=["Account Recovery"])
app.include_router(verify_phone_change_otp.router, tags=["Account Recovery"])

# Profile and KYC
from app.api.routes.user import main_router as user_router
app.include_router(user_router.router)
from app.api.routes.kyc.nin import main_router as nin_router
app.include_router(nin_router.router)

# Mobile Money
from app.api.routes.mobile_money import main_router as mobile_money_router
app.include_router(mobile_money_router.router)

# Groups
from app.api.routes.group import main_router as group_router
app.include_router(group_router.router)

@app.get("/")
def read_root():
    return {"message": "Microbond Backend API is running"}
