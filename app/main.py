from fastapi import FastAPI
from app.api.routes.authentication.account_recovery import request_recovery_otp, verify_recovery_otp, set_app_pin, request_phone_change_otp, verify_phone_change_otp, change_app_pin, request_forgot_pin_otp, verify_forgot_pin_otp, verify_app_pin

from app.core.database import init_db
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import settings

import sentry_sdk

if settings.SENTRY_DSN:
    sentry_sdk.init(
        dsn=settings.SENTRY_DSN,
        environment=settings.SENTRY_ENVIRONMENT,
        traces_sample_rate=settings.SENTRY_TRACES_SAMPLE_RATE,
        profiles_sample_rate=settings.SENTRY_TRACES_SAMPLE_RATE,
    )

app = FastAPI(title="Microbond Backend API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)

from app.cronjobs.core.scheduler import start_scheduler
import redis.asyncio as redis
from fastapi_limiter import FastAPILimiter

@app.on_event("startup")
async def on_startup():
    # 1. Initialize Database
    init_db()
    
    # 2. Start Cron Jobs
    if settings.ENABLE_IN_PROCESS_SCHEDULER:
        start_scheduler()
        print("[Scheduler] In-process APScheduler started.")
    else:
        print("[Scheduler] In-process APScheduler disabled. Scheduled tasks are triggered via Cloud Scheduler HTTP endpoints.")
    
    # 3. Initialize Redis Rate Limiting
    try:
        redis_conn = redis.from_url(settings.REDIS_URL, encoding="utf-8", decode_responses=True)
        await FastAPILimiter.init(redis_conn)
        print("[Redis] Rate Limiter initialized successfully")
    except Exception as e:
        print(f"[Redis warning] Could not connect to Redis for Rate Limiting: {e}")

# Auth and Recovery
from app.api.routes.authentication.otp import main_router as otp_router
app.include_router(otp_router.router)
app.include_router(request_recovery_otp.router, tags=["Account Recovery"])
app.include_router(verify_recovery_otp.router, tags=["Account Recovery"])
app.include_router(set_app_pin.router, tags=["Account Recovery"])
app.include_router(verify_app_pin.router, tags=["Account Recovery"])
app.include_router(change_app_pin.router, tags=["Account Recovery"])
app.include_router(request_forgot_pin_otp.router, tags=["Account Recovery"])
app.include_router(verify_forgot_pin_otp.router, tags=["Account Recovery"])
app.include_router(request_phone_change_otp.router, tags=["Account Recovery"])
app.include_router(verify_phone_change_otp.router, tags=["Account Recovery"])

# Profile and KYC
from app.api.routes.user import main_router as user_router
app.include_router(user_router.router)
from app.api.routes.kyc.nin import main_router as nin_router
app.include_router(nin_router.router)
from app.api.routes.kyc.phone import router as phone_kyc_router
app.include_router(phone_kyc_router.router)

# Mobile Money
from app.api.routes.mobile_money import main_router as mobile_money_router
app.include_router(mobile_money_router.router)

# Groups
from app.api.routes.group import group_endpoints
app.include_router(group_endpoints.router)

# Internal Tasks (Cloud Scheduler & Cloud Tasks)
from app.api.routes.internal import router as internal_tasks_router
app.include_router(internal_tasks_router)

# External Payment Gateway Integration
from app.api.routes.payments import router as payments_router
app.include_router(payments_router)

@app.get("/", tags=["System"])
def read_root():
    return {"message": "Microbond Backend API is running"}

@app.get("/healthz", tags=["System"], summary="Liveness probe")
def healthz():
    return {"status": "ok"}

@app.get("/readyz", tags=["System"], summary="Readiness probe")
def readyz():
    """
    Readiness probe for Cloud Run. Ensures database connectivity is functional.
    """
    from sqlmodel import text
    from app.core.database import engine
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return {"status": "ready", "database": "connected"}
    except Exception as e:
        import logging
        logging.getLogger("uvicorn.error").error(f"Readiness probe failed: {e}")
        from fastapi import Response, status
        return Response(
            content='{"status": "unhealthy", "database": "disconnected"}',
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            media_type="application/json"
        )

@app.get("/sentry-debug", tags=["System"])
async def trigger_error():
    """
    Test endpoint to verify Sentry is capturing errors.
    """
    division_by_zero = 1 / 0
    return {"message": "This will never be reached"}


if __name__ == "__main__":
    import os
    import uvicorn

    port = int(os.environ.get("PORT", 8000))
    uvicorn.run("app.main:app", host="0.0.0.0", port=port, reload=True)
