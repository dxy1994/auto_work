"""游戏执行端读写 RustFS / S3 中的图片对象。"""

from __future__ import annotations

import base64
import binascii
import re
import uuid
from datetime import datetime, timezone

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
_TRADE_SCREENSHOT_PREFIX = "trade-screenshots"
_MAX_TRADE_SCREENSHOT_BYTES = 3 * 1024 * 1024


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


def upload_trade_screenshot(assignment_id: str, screenshot_data_url: str) -> str:
    """把最终确认前截图直传 RustFS，并返回后端可保存的相对访问路径。"""
    prefix = "data:image/png;base64,"
    value = str(screenshot_data_url or "")
    if not value.startswith(prefix):
        raise StorageImageError("交易截图不是有效的 PNG Data URL")
    try:
        raw = base64.b64decode(value[len(prefix):], validate=True)
    except (binascii.Error, ValueError) as exc:
        raise StorageImageError("交易截图 Base64 编码无效") from exc
    if not raw:
        raise StorageImageError("交易截图为空")
    if len(raw) > _MAX_TRADE_SCREENSHOT_BYTES:
        raise StorageImageError(
            f"交易截图超过 {_MAX_TRADE_SCREENSHOT_BYTES} 字节限制"
        )

    safe_assignment = re.sub(
        r"[^A-Za-z0-9_-]+", "-", str(assignment_id or "").strip()
    ).strip("-") or "unknown"
    now = datetime.now(timezone.utc)
    key = (
        f"{_TRADE_SCREENSHOT_PREFIX}/{now:%Y/%m/%d}/"
        f"{safe_assignment}-{uuid.uuid4().hex}.png"
    )
    display_address = f"s3://{config.STORAGE_BUCKET}/{key}"
    try:
        _get_client().put_object(
            Bucket=config.STORAGE_BUCKET,
            Key=key,
            Body=raw,
            ContentType="image/png",
            Metadata={"assignment-id": safe_assignment},
        )
    except StorageImageError:
        raise
    except Exception as exc:
        raise StorageImageError(
            f"RustFS 上传交易截图失败: {display_address}"
        ) from exc
    return f"/uploads/{key}"
