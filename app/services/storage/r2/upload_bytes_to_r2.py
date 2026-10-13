import asyncio
import io
import uuid
import logging
from typing import Optional
from botocore.exceptions import ClientError

from app.core.config import settings
from app.services.storage.r2.client import get_r2_client
from app.services.storage.r2.upload_file_to_r2 import _upload_to_s3_sync

logger = logging.getLogger(__name__)


async def upload_bytes_to_r2(
    file_bytes: bytes,
    folder: str,
    content_type: str,
    extension: str,
) -> Optional[str]:
    """
    Uploads raw bytes to R2.
    Returns the public CDN URL or object key.
    """
    client = get_r2_client()
    if not client:
        return None

    try:
        unique_filename = f"{uuid.uuid4()}.{extension}"
        object_key = f"{folder}/{unique_filename}"

        await asyncio.to_thread(
            _upload_to_s3_sync,
            client,
            io.BytesIO(file_bytes),
            settings.R2_BUCKET_NAME,
            object_key,
            content_type,
        )

        if getattr(settings, "R2_PUBLIC_DOMAIN", None):
            base_url = settings.R2_PUBLIC_DOMAIN.rstrip("/")
            return f"{base_url}/{object_key}"

        return object_key

    except ClientError as e:
        logger.error(f"[R2] ClientError uploading bytes: {e}")
        return None
    except Exception as e:
        logger.error(f"[R2] Unexpected error uploading bytes: {e}", exc_info=True)
        return None
