"""阿里云 OSS：上传图片并生成私有签名 URL（惰性初始化，配置缺失时不阻断启动）。"""
import uuid
from datetime import datetime
from urllib.parse import unquote, urlparse

import oss2
from fastapi import HTTPException

from .config import _unset, settings


def object_key_from_url(url: str) -> str:
    """从签名 URL 中还原 object_key（兼容已存库的完整 URL 与纯 key 两种形态）。"""
    if url.startswith(("http://", "https://")):
        return unquote(urlparse(url).path).lstrip("/")
    return url


class OssClient:
    def __init__(self):
        self._bucket = None

    @property
    def bucket(self):
        if self._bucket is None:
            if (
                _unset(settings.oss_access_key_id)
                or _unset(settings.oss_access_key_secret)
                or _unset(settings.oss_bucket)
            ):
                raise HTTPException(
                    status_code=503,
                    detail="缺少 OSS 配置（OSS_ACCESS_KEY_ID/SECRET/BUCKET），请在 backend/.env 配置后重启",
                )
            self._bucket = oss2.Bucket(
                oss2.Auth(settings.oss_access_key_id, settings.oss_access_key_secret),
                settings.oss_endpoint,
                settings.oss_bucket,
            )
        return self._bucket

    def upload_image(self, data: bytes, filename: str = "") -> dict:
        """上传图片到 user_uploads/{date}/{uuid}.{ext}，返回 object_key + 签名 URL。"""
        ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else "png"
        if ext not in {"jpg", "jpeg", "png", "webp"}:
            ext = "png"
        date_dir = datetime.now().strftime("%Y%m%d")
        object_key = f"user_uploads/{date_dir}/{uuid.uuid4().hex}.{ext}"
        try:
            self.bucket.put_object(object_key, data)
        except HTTPException:
            raise
        except oss2.exceptions.OssError as e:
            raise HTTPException(status_code=502, detail=f"OSS 上传失败: {e.code}")
        return {
            "object_key": object_key,
            "url": self.bucket.sign_url("GET", object_key, settings.oss_url_expires),
        }

    def signed_url(self, object_key: str) -> str:
        return self.bucket.sign_url("GET", object_key, settings.oss_url_expires)


oss_client = OssClient()
