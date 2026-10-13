import boto3
from botocore.config import Config
from functools import lru_cache
import logging
from app.core.config import settings

logger = logging.getLogger(__name__)


@lru_cache()
def get_r2_client():
    """
    Initialize the S3/R2 client once to save memory and connection time.
    """
    if not settings.R2_ACCESS_KEY_ID:
        logger.warning("R2_ACCESS_KEY_ID is missing. Cloud storage is disabled.")
        return None

    return boto3.client(
        's3',
        endpoint_url=settings.R2_ENDPOINT_URL,
        aws_access_key_id=settings.R2_ACCESS_KEY_ID,
        aws_secret_access_key=settings.R2_SECRET_ACCESS_KEY,
        region_name='auto',
        config=Config(
            signature_version='s3v4',
            retries={'max_attempts': 3, 'mode': 'standard'}
        )
    )
