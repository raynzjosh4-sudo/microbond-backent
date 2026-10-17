import time
import logging
from typing import Optional
import jwt
from fastapi import APIRouter, Depends, status, Body
from fastapi.security import HTTPAuthorizationCredentials
from sqlmodel import Session

from app.core.config import settings
from app.core.database import get_session
from app.models.user.user import User
from app.api.dependencies import get_current_user
from app.api.dependencies.auth.bearer_scheme import security
from app.core.security import revoke_token, revoke_all_user_tokens
from .schemas import LogoutRequest, LogoutResponse

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post(
    "/logout",
    response_model=LogoutResponse,
    summary="User Logout",
    description="Terminates the user's active session, revokes the JWT token, disables FCM push notifications for this device, and updates presence status.",
    status_code=status.HTTP_200_OK,
)
def logout_user(
    payload: Optional[LogoutRequest] = Body(default=None),
    credentials: HTTPAuthorizationCredentials = Depends(security),
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    token = credentials.credentials
    all_devices = payload.all_devices if payload else False

    # 1. Determine token remaining TTL for blacklisting
    remaining_ttl: Optional[int] = None
    try:
        decoded = jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=[settings.ALGORITHM],
            options={"verify_exp": False},
        )
        exp = decoded.get("exp")
        if exp:
            now_sec = time.time()
            if exp > now_sec:
                remaining_ttl = int(exp - now_sec)
    except Exception as e:
        logger.debug(f"[Logout] Token decode for TTL extraction: {e}")

    # 2. Revoke the current token
    revoke_token(token, expire_seconds=remaining_ttl)

    # 3. If requested, revoke all active sessions for this user
    if all_devices:
        revoke_all_user_tokens(str(current_user.id))

    # 4. Detach FCM Push Notification Token
    current_user.fcm_token = None

    # 5. Mark user offline & record last seen
    current_user.is_online = False
    current_user.last_seen_at = int(time.time() * 1000)

    # 6. Persist user updates
    session.add(current_user)
    session.commit()

    logger.info(
        "User %s successfully logged out (all_devices=%s)",
        current_user.id,
        all_devices,
    )

    msg = (
        "Logged out of all devices successfully."
        if all_devices
        else "Logged out successfully."
    )

    return LogoutResponse(
        status="success",
        message=msg,
        all_devices=all_devices,
    )
