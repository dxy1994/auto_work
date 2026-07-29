"""Worker 角色共用的 RustFS / S3 连接与受限对象读取。"""

from __future__ import annotations

from dataclasses import dataclass


class ObjectStorageError(RuntimeError):
    pass


@dataclass(frozen=True)
class S3ConnectionSettings:
    endpoint: str
    region: str
    access_key: str
    secret_key: str
    path_style: bool = True


def create_s3_client(settings: S3ConnectionSettings):
    """创建与 RustFS/MinIO 兼容的 boto3 S3 客户端。"""
    import boto3
    from botocore.config import Config as BotoConfig

    return boto3.client(
        "s3",
        endpoint_url=settings.endpoint,
        region_name=settings.region,
        aws_access_key_id=settings.access_key,
        aws_secret_access_key=settings.secret_key,
        config=BotoConfig(
            signature_version="s3v4",
            s3={
                "addressing_style": (
                    "path" if settings.path_style else "virtual"
                )
            },
        ),
    )


def read_object_bytes(client, bucket: str, key: str, max_bytes: int) -> bytes:
    """读取不超过 max_bytes 的对象，并保证响应流被关闭。"""
    response = client.get_object(Bucket=bucket, Key=key)
    body = response["Body"]
    try:
        raw = body.read(max_bytes + 1)
    finally:
        close = getattr(body, "close", None)
        if callable(close):
            close()
    if len(raw) > max_bytes:
        raise ObjectStorageError(
            f"S3 对象超过读取限制: s3://{bucket}/{key}，限制={max_bytes} 字节"
        )
    return raw
