import jwt
from jwt.exceptions import InvalidTokenError
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials
from sqlmodel import Session

from app.core.config import settings
from app.core.database import get_session
from app.models.user.user import User
from app.api.dependencies.auth.bearer_scheme import security

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
