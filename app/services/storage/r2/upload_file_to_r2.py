import asyncio
import uuid
import logging
from typing import Optional
from botocore.exceptions import ClientError
from fastapi import UploadFile

from app.core.config import settings
from app.services.storage.r2.client import get_r2_client

logger = logging.getLogger(__name__)


def _upload_to_s3_sync(client, file_obj, bucket, key, content_type):
    client.upload_fileobj(
        file_obj,
        bucket,
        key,
        ExtraArgs={"ContentType": content_type}
    )


async def upload_file_to_r2(file: UploadFile, folder: str = "chat-media") -> Optional[str]:
    """
    Uploads a file to Cloudflare R2 safely and asynchronously.
    Returns the public URL of the uploaded file, or the object key if no public domain is set.
    """
    client = get_r2_client()
    if not client:
        logger.error("R2 Client could not be initialized. Check credentials.")
        return None

    try:
        file_extension = file.filename.split(".")[-1] if file.filename and "." in file.filename else "bin"
        unique_filename = f"{uuid.uuid4()}.{file_extension}"
        object_key = f"{folder}/{unique_filename}"

        await asyncio.to_thread(
            _upload_to_s3_sync,
            client,
            file.file,
            settings.R2_BUCKET_NAME,
            object_key,
            file.content_type or "application/octet-stream"
        )

        if getattr(settings, "R2_PUBLIC_DOMAIN", None):
            base_url = settings.R2_PUBLIC_DOMAIN.rstrip('/')
            return f"{base_url}/{object_key}"

        return object_key

    except ClientError as e:
        logger.error(f"AWS ClientError uploading file to R2: {e}")
        return None
    except Exception as e:
        logger.error(f"Unexpected error during R2 upload: {e}", exc_info=True)
        return None
