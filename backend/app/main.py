"""FastAPI 入口。"""
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from .config import check_required, settings
from .database import init_db
from .routes import auth, chat, upload

app = FastAPI(
    title="编程答疑 Agent",
    description="面向 Python 自学者的编程答疑后端：图片识别 + 联网检索 + 智能答疑",
    version="0.1.0",
)


@app.on_event("startup")
def on_startup():
    init_db()


@app.get("/health")
def health():
    missing = check_required()
    return {
        "status": "ok",
        "db": str(settings.database_path),
        "llm_model": settings.llm_model,
        "vision_model": settings.vision_model,
        "missing_config": missing,  # 空数组表示密钥已配齐
    }


app.include_router(auth.router)
app.include_router(upload.router)
app.include_router(chat.router)

# 托管前端页面（agent_demo01/index.html），通过 http://127.0.0.1:8000/ 访问。
# 注意：必须放在 API 路由之后注册，保证 /api/* 优先匹配。
STATIC_DIR = Path(__file__).resolve().parent.parent.parent  # agent_demo01/
app.mount("/", StaticFiles(directory=str(STATIC_DIR), html=True), name="static")
