from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials
from firebase_admin import auth
from app.core import firebase_config  # Ensures SDK initialization runs
from app.api.dependencies.auth.bearer_scheme import security

def get_current_firebase_user(
    credentials: HTTPAuthorizationCredentials = Depends(security)
) -> dict:
    """
    Validates the incoming Firebase ID token from the Bearer header.
    Returns the decoded token dictionary containing 'uid' and 'phone_number'.
    """
    token = credentials.credentials
    try:
        decoded_token = auth.verify_id_token(token)
        return decoded_token
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired Firebase ID token.",
            headers={"WWW-Authenticate": "Bearer"},
        )
