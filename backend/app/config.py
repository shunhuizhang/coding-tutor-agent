"""应用配置：从 .env 读取，缺省值兜底。"""
import os
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# 默认关闭 LangSmith 追踪：实测会拖慢 Agent 响应约 2 倍（启用时单轮 90s+）。
# 如需追踪调试，将下面一行改为 os.environ["LANGSMITH_TRACING"] = os.environ.get("LANGSMITH_TRACING", "true")
os.environ["LANGSMITH_TRACING"] = "false"

BASE_DIR = Path(__file__).resolve().parent.parent  # backend/


class Settings(BaseSettings):
    # 阿里云百炼（通义千问）
    dashscope_api_key: str = ""
    dashscope_base_url: str = "https://dashscope.aliyuncs.com/compatible-mode/v1"
    llm_model: str = "qwen3.8-max"
    vision_model: str = "qwen-vl-max"

    # Tavily
    tavily_api_key: str = ""
    tavily_max_results: int = 5

    # 阿里云 OSS
    oss_access_key_id: str = ""
    oss_access_key_secret: str = ""
    oss_bucket: str = ""
    oss_endpoint: str = "oss-cn-hangzhou.aliyuncs.com"
    oss_url_expires: int = 300

    # JWT
    secret_key: str = "change-me-to-a-random-secret"
    jwt_expire_minutes: int = 43200

    # SQLite
    database_path: str = "./app.db"

    model_config = SettingsConfigDict(
        env_file=str(BASE_DIR / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()

# 占位符标记：.env 未填真实值时的常见占位文本
_PLACEHOLDER_MARKERS = ("你的", "change-me", "YourBucket")


def _unset(value: str) -> bool:
    """配置为空或仍为占位符时视为未配置。"""
    return not value or any(m in value for m in _PLACEHOLDER_MARKERS)


def check_required() -> list[str]:
    """返回缺失的关键配置项列表，便于启动时提示。"""
    missing = []
    if _unset(settings.dashscope_api_key):
        missing.append("DASHSCOPE_API_KEY")
    if _unset(settings.tavily_api_key):
        missing.append("TAVILY_API_KEY")
    if (
        _unset(settings.oss_access_key_id)
        or _unset(settings.oss_access_key_secret)
        or _unset(settings.oss_bucket)
    ):
        missing.append("OSS_ACCESS_KEY_ID/OSS_ACCESS_KEY_SECRET/OSS_BUCKET")
    return missing
