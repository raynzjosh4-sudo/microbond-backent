"""
cloud_storage facade — redirects to app.services.storage.r2
"""
from app.services.storage.r2 import (
    get_r2_client,
    upload_file_to_r2,
    upload_bytes_to_r2,
    delete_file_from_r2,
)

__all__ = [
    "get_r2_client",
    "upload_file_to_r2",
    "upload_bytes_to_r2",
    "delete_file_from_r2",
]
