"""图片上传：FastAPI 接收 → 阿里云 OSS → 返回签名 URL。"""
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile

from ..oss_client import oss_client
from ..security import get_current_user

router = APIRouter(prefix="/api", tags=["upload"])

ALLOWED = {"image/jpeg", "image/png", "image/webp"}
MAX_SIZE = 10 * 1024 * 1024  # 10MB


@router.post("/upload")
async def upload_image(
    file: UploadFile = File(...),
    user: dict = Depends(get_current_user),
):
    if file.content_type not in ALLOWED:
        raise HTTPException(status_code=400, detail="仅支持 jpg/png/webp 图片")
    data = await file.read()
    if len(data) > MAX_SIZE:
        raise HTTPException(status_code=400, detail="图片不能超过 10MB")
    if not data:
        raise HTTPException(status_code=400, detail="图片内容为空")

    result = oss_client.upload_image(data, file.filename or "image.png")
    return {"object_key": result["object_key"], "url": result["url"]}
