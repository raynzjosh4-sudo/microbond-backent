import jwt
from typing import List, Optional
from fastapi import APIRouter, Depends, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlmodel import Session, select

from app.core.config import settings
from app.core.database import get_session
from app.models.user.core.user import User
from .schemas import ContactSyncRequest, MatchedContact

router = APIRouter()
optional_security = HTTPBearer(auto_error=False)

# Keep SQL IN clause chunks optimal for PostgreSQL query planning & memory
MAX_TOTAL_LOOKUPS = 5000
CHUNK_SIZE = 500


def get_optional_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(optional_security),
    session: Session = Depends(get_session),
) -> Optional[User]:
    """
    Extracts authenticated user if Bearer token is provided; otherwise returns None.
    Allows contact discovery to be called seamlessly both authenticated and in testing.
    """
    if not credentials:
        return None
    try:
        payload = jwt.decode(
            credentials.credentials,
            settings.SECRET_KEY,
            algorithms=[settings.ALGORITHM],
        )
        user_id = payload.get("sub")
        scope = payload.get("scope", "access")
        if not user_id or scope != "access":
            return None
        return session.get(User, user_id)
    except Exception:
        return None


@router.post(
    "/sync",
    response_model=List[MatchedContact],
    summary="Batch Synchronize and Discover Contacts",
    description="Cross-references a batch of normalized phone numbers against registered Microbond users.",
)
def sync_contacts(
    request: ContactSyncRequest,
    session: Session = Depends(get_session),
    current_user: Optional[User] = Depends(get_optional_current_user),
):
    """
    Compares the uploaded address book against the registered user database.
    - Uses Postgres index on 'phone_number' for millisecond lookups
    - Chunks requests to avoid SQL parameter overflow on large contact lists
    - Returns only safe, public profile information
    - Excludes the current user so they don't discover themselves
    """
    if not request.phone_numbers:
        return []

    # 1. Clean, strip, and deduplicate numbers
    unique_numbers = list({
        num.strip()
        for num in request.phone_numbers
        if num and num.strip()
    })

    if not unique_numbers:
        return []

    # Bound lookup size for safety
    bounded_numbers = unique_numbers[:MAX_TOTAL_LOOKUPS]

    # 2. Chunk queries with SQL 'IN' clause
    matched_users: List[User] = []
    current_user_id = str(current_user.id) if current_user else None

    for i in range(0, len(bounded_numbers), CHUNK_SIZE):
        chunk = bounded_numbers[i : i + CHUNK_SIZE]
        statement = select(User).where(User.phone_number.in_(chunk))
        
        # Exclude self if authenticated
        if current_user_id:
            statement = statement.where(User.id != current_user.id)
            
        results = session.exec(statement).all()
        matched_users.extend(results)

    # 3. Return sanitized public profile info
    return [
        MatchedContact(
            user_id=str(user.id),
            phone_number=user.phone_number,
            profile_name=user.full_name or "Microbond Member",
            profile_picture_url=user.profile_picture_url,
            avatar_color=user.avatar_color or "Gray",
            about_status=user.about_status or "Hey there! I am using Microbond.",
        )
        for user in matched_users
    ]
