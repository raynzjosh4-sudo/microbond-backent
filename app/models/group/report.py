from typing import Optional
from sqlmodel import SQLModel, Field
from datetime import datetime, timezone
import uuid
from sqlalchemy import Column, BigInteger

def utc_now():
    return int(datetime.now(timezone.utc).timestamp() * 1000)

class GroupReport(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    report_id: str = Field(default_factory=lambda: str(uuid.uuid4()), unique=True, index=True)
    
    group_id: str = Field(foreign_key="group.group_id", index=True)
    reporter_user_id: uuid.UUID = Field(foreign_key="user.id", index=True)
    
    reason: str = Field(description="High-level category, e.g., SCAM, SPAM, HARASSMENT")
    description: Optional[str] = Field(default=None, description="Detailed user description")
    
    # Status: OPEN, REVIEWING, RESOLVED, DISMISSED
    status: str = Field(default="OPEN", index=True)
    
    created_at: int = Field(default_factory=utc_now, sa_column=Column(BigInteger))
