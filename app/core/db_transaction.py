from contextlib import contextmanager
from typing import Iterator

from sqlmodel import Session


@contextmanager
def transaction(session: Session) -> Iterator[Session]:
    """Commit a unit of work, or roll it back if any operation fails."""
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
