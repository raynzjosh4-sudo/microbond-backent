import logging
from fastapi import APIRouter, Depends, status
from sqlmodel import Session
from app.core.database import get_session
from app.api.dependencies import get_current_user
from app.models.user.user import User

logger = logging.getLogger(__name__)

router = APIRouter()


@router.delete(
    "/me/fcm-token",
    summary="Invalidate FCM Token on Logout",
    status_code=status.HTTP_200_OK,
)
def deregister_fcm_token(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    if current_user.fcm_token is None:
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
