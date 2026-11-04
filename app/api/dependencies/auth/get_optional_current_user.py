from typing import Optional
import uuid
import jwt
from jwt.exceptions import InvalidTokenError
from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials
from sqlmodel import Session

from app.core.config import settings
from app.core.database import get_session
from app.models.user.user import User
from app.api.dependencies.auth.bearer_scheme import optional_security
from app.core.security import is_token_revoked


def get_optional_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(optional_security),
    session: Session = Depends(get_session),
) -> Optional[User]:
    """
    Extracts authenticated user if Bearer token is provided and valid;
    returns None if anonymous or if token is invalid/expired.
    """
    if not credentials:
        return None

    token = credentials.credentials
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        user_id = payload.get("sub")
        scope = payload.get("scope", "access")
        if not user_id or scope != "access":
            return None

        if is_token_revoked(token, user_id=str(user_id), token_iat=payload.get("iat")):
            return None

        try:
            user_uuid = uuid.UUID(user_id) if isinstance(user_id, str) else user_id
        except (ValueError, AttributeError):
            user_uuid = user_id

        return session.get(User, user_uuid)
    except Exception:
        return None

