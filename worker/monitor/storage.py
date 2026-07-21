"""
RustFS / S3 兼容存储同步模块。

浏览器用户数据（Cookie / LocalStorage 等）在任务关闭后打包上传到
RustFS，下次启动时从 RustFS 下载恢复。实现跨机器的登录态共享。

通过 config.STORAGE_ENDPOINT 是否为空决定是否启用。
"""
import os
import tempfile
import zipfile
from typing import Optional

from monitor import config

_EXCLUDE_DIRS = {
    "Cache", "GPUCache", "Code Cache", "DawnGraphiteCache",
    "GrShaderCache", "ShaderCache", "DawnCache",
}
_EXCLUDE_SUFFIXES = (".lock",)
_EXCLUDE_NAMES = {"SingletonLock", "SingletonSocket", "SingletonCookie"}

_PROFILES_PREFIX = "worker-profiles"


def _get_client():
    """懒加载 S3 client，未配置则返回 None。"""
    if not config.STORAGE_ENDPOINT:
        return None
    try:
        import boto3
        from botocore.config import Config as BotoConfig

        return boto3.client(
            "s3",
            endpoint_url=config.STORAGE_ENDPOINT,
            region_name=config.STORAGE_REGION,
            aws_access_key_id=config.STORAGE_ACCESS_KEY,
            aws_secret_access_key=config.STORAGE_SECRET_KEY,
            config=BotoConfig(
                signature_version="s3v4",
                s3={"addressing_style": "path" if config.STORAGE_PATH_STYLE else "virtual"},
            ),
        )
    except ImportError:
        print("[StorageSync] boto3 未安装，无法使用远程存储同步")
        return None
    except Exception as e:
        print(f"[StorageSync] S3 client 初始化失败: {e}")
        return None


def download_file(object_key: str, suffix: str = "") -> Optional[str]:
    """从 RustFS 下载单个文件到临时目录，返回临时文件路径；失败返回 None。"""
    client = _get_client()
    if not client:
        return None
    try:
        client.head_object(Bucket=config.STORAGE_BUCKET, Key=object_key)
    except Exception:
        print(f"[StorageSync] RustFS 中无对象: {object_key}")
        return None

    tmp_path = tempfile.mktemp(suffix=suffix)
    try:
        client.download_file(config.STORAGE_BUCKET, object_key, tmp_path)
        print(f"[StorageSync] 从 RustFS 下载: {object_key} -> {tmp_path}")
        return tmp_path
    except Exception as e:
        print(f"[StorageSync] 下载文件失败 {object_key}: {e}")
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)
        return None


def is_enabled() -> bool:
    """是否启用了远程存储同步。"""
    return bool(config.STORAGE_ENDPOINT)


def _s3_key(account_id: int) -> str:
    return f"{_PROFILES_PREFIX}/{account_id}/profile.zip"


def download(account_id: int, local_dir: str) -> bool:
    """从 RustFS 下载浏览器配置 ZIP 并解压到 local_dir。已有本地数据则跳过。"""
    client = _get_client()
    if not client:
        return False

    if os.path.isdir(local_dir) and os.listdir(local_dir):
        print(f"[StorageSync] 本地已有配置，跳过下载: {local_dir}")
        return False

    key = _s3_key(account_id)
    try:
        client.head_object(Bucket=config.STORAGE_BUCKET, Key=key)
    except Exception:
        print(f"[StorageSync] RustFS 中无账号 {account_id} 的配置，跳过下载")
        return False

    zip_path = tempfile.mktemp(suffix=".zip")
    try:
        client.download_file(config.STORAGE_BUCKET, key, zip_path)
        os.makedirs(local_dir, exist_ok=True)
        with zipfile.ZipFile(zip_path, "r") as zf:
            zf.extractall(local_dir)
        file_count = len(zf.namelist())
        print(f"[StorageSync] 从 RustFS 下载并解压 {file_count} 个文件 -> {local_dir}")
        return True
    except Exception as e:
        print(f"[StorageSync] 下载失败: {e}")
        return False
    finally:
        if os.path.exists(zip_path):
            os.unlink(zip_path)


def upload(account_id: int, local_dir: str) -> bool:
    """将本地浏览器配置目录打包为 ZIP 上传到 RustFS。"""
    client = _get_client()
    if not client:
        return False

    if not os.path.isdir(local_dir):
        print(f"[StorageSync] 本地目录不存在，跳过上传: {local_dir}")
        return False

    zip_path = tempfile.mktemp(suffix=".zip")
    try:
        file_count = 0
        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
            for root, dirs, files in os.walk(local_dir):
                dirs[:] = [d for d in dirs if d not in _EXCLUDE_DIRS]
                for fname in files:
                    if fname.endswith(_EXCLUDE_SUFFIXES) or fname in _EXCLUDE_NAMES:
                        continue
                    full_path = os.path.join(root, fname)
                    arcname = os.path.relpath(full_path, local_dir).replace("\\", "/")
                    zf.write(full_path, arcname)
                    file_count += 1

        key = _s3_key(account_id)
        client.upload_file(zip_path, config.STORAGE_BUCKET, key)
        print(f"[StorageSync] 上传 {file_count} 个文件 -> s3://{config.STORAGE_BUCKET}/{key}")
        return True
    except Exception as e:
        print(f"[StorageSync] 上传失败: {e}")
        return False
    finally:
        if os.path.exists(zip_path):
            os.unlink(zip_path)
