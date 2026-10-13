import jwt
from jwt.exceptions import InvalidTokenError
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials
from sqlmodel import Session

from app.core.config import settings
from app.core.database import get_session
from app.models.user.user import User
from app.api.dependencies.auth.bearer_scheme import security

def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    session: Session = Depends(get_session)
) -> User:
    """
    Validates internal JWT Token (generated after OTP verification).
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
