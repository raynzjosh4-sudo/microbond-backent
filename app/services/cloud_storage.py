import boto3
from botocore.exceptions import ClientError
from botocore.config import Config
from fastapi import UploadFile
import uuid
import logging
import asyncio
from typing import Optional
from functools import lru_cache
from app.core.config import settings

logger = logging.getLogger(__name__)

# 1. Caching: Initialize the S3 client once to save memory and connection time
@lru_cache()
def get_r2_client():
    if not settings.R2_ACCESS_KEY_ID:
        logger.warning("R2_ACCESS_KEY_ID is missing. Cloud storage is disabled.")
        return None
        
    return boto3.client(
        's3',
        endpoint_url=settings.R2_ENDPOINT_URL,
        aws_access_key_id=settings.R2_ACCESS_KEY_ID,
        aws_secret_access_key=settings.R2_SECRET_ACCESS_KEY,
        region_name='auto', # Cloudflare R2 uses 'auto'
        config=Config(retries={'max_attempts': 3, 'mode': 'standard'}) # Auto-retry on transient failures
    )

def _upload_to_s3_sync(client, file_obj, bucket, key, content_type):
    """
    Synchronous wrapper for boto3 upload_fileobj.
    """
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
        # 2. Safe Filenames: Generate a unique filename to prevent collisions and sanitize
        file_extension = file.filename.split(".")[-1] if file.filename and "." in file.filename else "bin"
        unique_filename = f"{uuid.uuid4()}.{file_extension}"
        object_key = f"{folder}/{unique_filename}"

        # 3. Non-Blocking Streaming: Use asyncio.to_thread and upload_fileobj 
        # This prevents the FastAPI event loop from blocking and keeps RAM usage low
        # because upload_fileobj streams the file directly from the temp spool
        await asyncio.to_thread(
            _upload_to_s3_sync,
            client,
            file.file,
            settings.R2_BUCKET_NAME,
            object_key,
            file.content_type or "application/octet-stream"
        )
        
        # 4. URL Construction
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
