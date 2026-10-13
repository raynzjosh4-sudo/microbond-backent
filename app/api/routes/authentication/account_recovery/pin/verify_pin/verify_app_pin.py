from fastapi import APIRouter, Depends, HTTPException, status
from app.models.user.user import User
from app.core.security import verify_pin
from app.api.dependencies import get_current_user
from app.core.rate_limit import RateLimiter
from .schemas import VerifyAppPinRequest, VerifyAppPinResponse

router = APIRouter()

@router.post(
    "/pin/verify",
    response_model=VerifyAppPinResponse,
    summary="Verify User App PIN",
    description="Validates the user's App PIN for session unlock or client-side checks. Heavily rate limited to prevent brute force.",
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(RateLimiter(times=5, seconds=60))]
)
def verify_app_pin(
    payload: VerifyAppPinRequest,
    current_user: User = Depends(get_current_user)
):
    if not current_user.hashed_pin:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User has not set up an App PIN yet."
        )

    if not verify_pin(payload.pin, current_user.hashed_pin):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect App PIN."
        )

    return VerifyAppPinResponse(
        status="success",
        message="App PIN verified successfully.",
        valid=True
    )
