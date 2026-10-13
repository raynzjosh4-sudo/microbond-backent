import logging
from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session, select
from app.core.database import get_session
from app.api.dependencies import get_current_user
from app.models.user.user import User
from .schemas import FCMTokenRequest

logger = logging.getLogger(__name__)

router = APIRouter()


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
    token = payload.token.strip()

    if not token:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="FCM token must not be empty.",
        )

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

    if current_user.fcm_token == token:
        return {
            "status": "success",
            "message": "FCM token is already up to date.",
        }

    current_user.fcm_token = token
    session.add(current_user)
    session.commit()

    logger.info(
        "FCM token registered/refreshed for user %s [%s]",
        current_user.id,
        payload.platform,
    )

    return {
        "status": "success",
        "message": "FCM token registered successfully. Push notifications are now active.",
    }
