from typing import Optional
from sqlmodel import SQLModel, Field
import uuid
from app.utils.time.now_epoch_ms import now_epoch_ms

class KycDocument(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: uuid.UUID = Field(foreign_key="user.id", index=True)
    
    document_type: str = Field(description="NATIONAL_ID, PASSPORT, etc.")
    document_number: str
    
    front_image_path: str
    back_image_path: Optional[str] = Field(default=None)
    selfie_image_path: Optional[str] = Field(default=None)
    
    extracted_full_name: Optional[str] = Field(default=None)
    date_of_birth: Optional[str] = Field(default=None)
    
    status: str = Field(default="PENDING")
    rejection_reason: Optional[str] = Field(default=None)
    
    submitted_at: int = Field(default_factory=now_epoch_ms)
    verified_at: Optional[int] = Field(default=None)
    expiry_date: Optional[int] = Field(default=None)
