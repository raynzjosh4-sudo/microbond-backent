from typing import Optional
from pydantic import BaseModel


class BackupEmailData(BaseModel):
    email: str
    is_verified: bool
    created_at: Optional[int] = None
    verified_at: Optional[int] = None


class GetBackupEmailResponse(BaseModel):
    status: str = "success"
    has_backup_email: bool
    data: Optional[BackupEmailData] = None
