from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from firebase_admin import auth
from app.core import firebase_config  # Ensures SDK initialization runs

security = HTTPBearer()

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
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired Firebase ID token.",
            headers={"WWW-Authenticate": "Bearer"},
        )

import jwt
from jwt.exceptions import InvalidTokenError
from sqlmodel import Session
from app.core.config import settings
from app.core.database import get_session
from app.models.user.user import User

def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    session: Session = Depends(get_session)
) -> User:
    """
    Validates our internal JWT Token (generated after OTP verification).
    Returns the authenticated User object.
    """
    token = credentials.credentials
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        user_id: str = payload.get("sub")
        scope: str = payload.get("scope", "access")
        if user_id is None or scope != "access":
            raise HTTPException(status_code=401, detail="Invalid token payload or scope")
    except InvalidTokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired access token.",
            headers={"WWW-Authenticate": "Bearer"},
        )
        
    user = session.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
        
    return user

def get_pin_setup_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    session: Session = Depends(get_session)
) -> User:
    """
    Validates a token for setting a PIN.
    Allows 'recovery' scope always.
    Allows 'access' scope ONLY if the user doesn't have a PIN yet (first time setup).
    """
    token = credentials.credentials
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        user_id: str = payload.get("sub")
        scope: str = payload.get("scope", "access")
        if user_id is None:
            raise HTTPException(status_code=401, detail="Invalid token payload")
    except InvalidTokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token.",
            headers={"WWW-Authenticate": "Bearer"},
        )
        
    user = session.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
        
    if scope == "access" and user.hashed_pin is not None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, 
            detail="You already have a PIN. Use the change PIN endpoint or recover your account."
        )
        
    if scope not in ["access", "recovery"]:
        raise HTTPException(status_code=401, detail="Invalid token scope")
        
    return user
