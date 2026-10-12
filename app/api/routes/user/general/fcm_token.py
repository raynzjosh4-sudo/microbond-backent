from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlmodel import Session, select
from typing import Optional
import logging

from app.core.database import get_session
from app.api.dependencies import get_current_user
from app.models.user.user import User

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/users", tags=["Push Notifications"])


class FCMTokenRequest(BaseModel):
    token: str = Field(
        ...,
        min_length=10,
        description="FCM device registration token from Firebase SDK (obtained via FirebaseMessaging.getInstance().getToken())"
    )
    platform: Optional[str] = Field(
        default="ANDROID",
        description="Client platform: ANDROID | IOS"
    )


# ---------------------------------------------------------------------------
# POST /api/v1/users/me/fcm-token
# ---------------------------------------------------------------------------

@router.post(
    "/me/fcm-token",
    summary="Register or Refresh FCM Push Notification Token",
    status_code=status.HTTP_200_OK,
)
def register_fcm_token(
    payload: FCMTokenRequest,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """
    Registers or refreshes the FCM device token for the authenticated user.

    The mobile client must call this endpoint:
      - Immediately after a successful login / OTP verification.
      - Whenever Firebase calls `onNewToken(newToken)` (token was rotated by FCM).

    Stale-token collision handling:
      If another user account currently holds the exact same FCM token
      (e.g. the device was factory-reset and a new account was created),
      the token is silently wiped from the old owner before being
      assigned to the current user. This prevents ghost notifications
      being delivered to the wrong account.
    """
    token = payload.token.strip()

    if not token:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="FCM token must not be empty.",
        )

    # ── Stale-token collision check ─────────────────────────────────────────
    # If another user row already holds this token, clear it from them first.
    old_owner = session.exec(
        select(User).where(
            User.fcm_token == token,
            User.id != current_user.id,
        )
    ).first()

    if old_owner:
        logger.info(
            "FCM token collision resolved: wiped stale token from user %s "
            "before assigning to user %s",
            old_owner.id,
            current_user.id,
        )
        old_owner.fcm_token = None
        session.add(old_owner)

    # ── Assign token ────────────────────────────────────────────────────────
    if current_user.fcm_token == token:
        # Token is unchanged — idempotent, no DB write needed.
        return {
            "status": "success",
            "message": "FCM token is already up to date.",
        }

    current_user.fcm_token = token
    session.add(current_user)
    session.commit()

    logger.info("FCM token registered/refreshed for user %s [%s]", current_user.id, payload.platform)

    return {
        "status": "success",
        "message": "FCM token registered successfully. Push notifications are now active.",
    }


# ---------------------------------------------------------------------------
# DELETE /api/v1/users/me/fcm-token
# ---------------------------------------------------------------------------

@router.delete(
    "/me/fcm-token",
    summary="Invalidate FCM Token on Logout",
    status_code=status.HTTP_200_OK,
)
def deregister_fcm_token(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """
    Wipes the stored FCM token for the authenticated user.

    The mobile client must call this endpoint **before** clearing the local
    session / JWT on logout — so the backend can authenticate the request.

    Call this on:
      - Explicit user logout.
      - User disables push notifications in app settings.
      - Account deletion (also handled automatically in account_deletion.py).
    """
    if current_user.fcm_token is None:
        # Already cleared — idempotent response.
        return {
            "status": "success",
            "message": "No FCM token was registered. Nothing to remove.",
        }

    current_user.fcm_token = None
    session.add(current_user)
    session.commit()

    logger.info("FCM token deregistered for user %s", current_user.id)

    return {
        "status": "success",
        "message": "FCM token removed. Push notifications have been disabled for this device.",
    }
