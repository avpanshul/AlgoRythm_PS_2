from minio import Minio
from app.core.config import settings

def get_minio_client() -> Minio:
    return Minio(
        endpoint=settings.MINIO_ENDPOINT,
        access_key=settings.MINIO_ACCESS_KEY,
        secret_key=settings.MINIO_SECRET_KEY,
        secure=settings.MINIO_SECURE
    )

def init_minio():
    client = get_minio_client()
    if not client.bucket_exists(settings.MINIO_RAW_BUCKET):
        client.make_bucket(settings.MINIO_RAW_BUCKET)
