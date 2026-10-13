import logging
from botocore.exceptions import ClientError
from app.core.config import settings
from app.services.storage.r2.client import get_r2_client

logger = logging.getLogger(__name__)


def delete_file_from_r2(public_url_or_key: str) -> bool:
    """
    Deletes a previously-uploaded object from Cloudflare R2.
    Returns True if deleted (or already gone), False on error.
    """
    client = get_r2_client()
    if not client:
        return False

    try:
        key = public_url_or_key
        if getattr(settings, "R2_PUBLIC_DOMAIN", None) and key.startswith(settings.R2_PUBLIC_DOMAIN):
            base = settings.R2_PUBLIC_DOMAIN.rstrip("/")
            key = key[len(base):].lstrip("/")

        client.delete_object(Bucket=settings.R2_BUCKET_NAME, Key=key)
        logger.info(f"[R2] Deleted object: {key}")
        return True
    except ClientError as e:
        logger.error(f"[R2] ClientError deleting object '{key}': {e}")
        return False
    except Exception as e:
        logger.error(f"[R2] Unexpected error deleting object '{key}': {e}", exc_info=True)
        return False
