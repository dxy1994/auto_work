"""游戏执行端读取 RustFS / S3 中的物品识别图片。"""

from __future__ import annotations

from common.object_storage import (
    ObjectStorageError,
    S3ConnectionSettings,
    create_s3_client,
    read_object_bytes,
)
from game_executor import config


class StorageImageError(RuntimeError):
    pass


_client = None


def is_enabled() -> bool:
    return bool(
        config.STORAGE_ENDPOINT
        and config.STORAGE_BUCKET
        and config.STORAGE_ACCESS_KEY
        and config.STORAGE_SECRET_KEY
    )


def object_key(relative_address: str) -> str:
    """把总控的 /uploads/... 相对地址转换为 RustFS 对象键。"""
    value = str(relative_address or "").strip().replace("\\", "/")
    if value.startswith("/uploads/"):
        value = value[len("/uploads/"):]
    elif value.startswith("uploads/"):
        value = value[len("uploads/"):]
    else:
        value = value.lstrip("/")
    parts = tuple(part for part in value.split("/") if part)
    if not parts or any(part in {".", ".."} for part in parts):
        raise StorageImageError(f"无效的 RustFS 图片相对地址: {relative_address}")
    return "/".join(parts)


def _get_client():
    global _client
    if _client is not None:
        return _client
    if not is_enabled():
        raise StorageImageError("游戏执行端尚未配置完整的 RustFS 连接参数")
    try:
        _client = create_s3_client(
            S3ConnectionSettings(
                endpoint=config.STORAGE_ENDPOINT,
                region=config.STORAGE_REGION,
                access_key=config.STORAGE_ACCESS_KEY,
                secret_key=config.STORAGE_SECRET_KEY,
                path_style=config.STORAGE_PATH_STYLE,
            ),
        )
    except ImportError as exc:
        raise StorageImageError("游戏执行端缺少 boto3，无法读取 RustFS") from exc
    except Exception as exc:
        raise StorageImageError(f"RustFS 客户端初始化失败: {exc}") from exc
    return _client


def read_image(relative_address: str, max_bytes: int = 1_048_576) -> tuple[bytes, str]:
    """读取识别图，返回图片字节与便于排查的 s3:// 地址。"""
    key = object_key(relative_address)
    display_address = f"s3://{config.STORAGE_BUCKET}/{key}"
    try:
        raw = read_object_bytes(
            _get_client(),
            config.STORAGE_BUCKET,
            key,
            max_bytes,
        )
    except StorageImageError:
        raise
    except ObjectStorageError as exc:
        raise StorageImageError(str(exc)) from exc
    except Exception as exc:
        raise StorageImageError(
            f"RustFS 读取识别图片失败: {display_address}"
        ) from exc
    return raw, display_address
