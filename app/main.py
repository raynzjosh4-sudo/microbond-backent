from fastapi import FastAPI
from app.api.routes.account_recovery import request_recovery_otp, verify_recovery_otp, set_app_pin, request_phone_change_otp, verify_phone_change_otp
from app.api.routes.group import rotating, target_savings, settings
from app.api.routes import at_otp_auth, firebase_otp_auth, mobile_money, profile_status
from app.api.routes.kyc import nin_kyc
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
app.include_router(at_otp_auth.router)
app.include_router(firebase_otp_auth.router)
app.include_router(request_recovery_otp.router, tags=["Account Recovery"])
app.include_router(verify_recovery_otp.router, tags=["Account Recovery"])
app.include_router(set_app_pin.router, tags=["Account Recovery"])
app.include_router(request_phone_change_otp.router, tags=["Account Recovery"])
app.include_router(verify_phone_change_otp.router, tags=["Account Recovery"])

# Profile and KYC
app.include_router(profile_status.router)
app.include_router(nin_kyc.router)

# Mobile Money
app.include_router(mobile_money.router)

# Groups
app.include_router(rotating.router)
app.include_router(target_savings.router)
app.include_router(settings.router)

@app.get("/")
def read_root():
    return {"message": "Microbond Backend API is running"}
