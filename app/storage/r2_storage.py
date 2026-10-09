import boto3
from botocore.config import Config
from app.core.config import settings

def get_r2_client():
    return boto3.client(
        's3',
        endpoint_url=settings.R2_ENDPOINT_URL,
        aws_access_key_id=settings.R2_ACCESS_KEY_ID,
        aws_secret_access_key=settings.R2_SECRET_ACCESS_KEY,
        config=Config(signature_version='s3v4'),
        region_name='auto'
    )

def generate_presigned_url(object_name: str, expiration=900):
    s3_client = get_r2_client()
    try:
        response = s3_client.generate_presigned_url('get_object',
                                                    Params={'Bucket': settings.R2_BUCKET_NAME,
                                                            'Key': object_name},
                                                    ExpiresIn=expiration)
    except Exception as e:
        return None
    return response

def upload_file_to_r2(file_obj, object_name: str, content_type: str = None):
    s3_client = get_r2_client()
    extra_args = {}
    if content_type:
        extra_args['ContentType'] = content_type
    s3_client.upload_fileobj(file_obj, settings.R2_BUCKET_NAME, object_name, ExtraArgs=extra_args)
    return object_name
