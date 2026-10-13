from typing import Optional
from app.core.config import settings
from app.services.storage.r2.client import get_r2_client


def generate_presigned_url(object_name: str, expiration: int = 900) -> Optional[str]:
    """
    Generate presigned GET URL for an object in R2.
    """
    s3_client = get_r2_client()
    if not s3_client:
        return None
    try:
        response = s3_client.generate_presigned_url(
            'get_object',
            Params={'Bucket': settings.R2_BUCKET_NAME, 'Key': object_name},
            ExpiresIn=expiration
        )
        return response
    except Exception:
        return None
