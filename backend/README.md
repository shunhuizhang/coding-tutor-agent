# 编程答疑 Agent · 后端

完整项目说明（目录结构、密钥配置、启动部署、接口清单、排查指南）见项目根目录 **[`../README.md`](../README.md)**。

## 本目录快速参考

```powershell
# 启动（在 backend 目录下）
D:\code\ai_xuexi\.venv\Scripts\python.exe -m uvicorn app.main:app --host 0.0.0.0 --port 8000

# 自测
D:\code\ai_xuexi\.venv\Scripts\python.exe -u test_chat.py
D:\code\ai_xuexi\.venv\Scripts\python.exe -u test_upload.py
```

- 密钥：复制 `.env.example` 为 `.env` 填写（或直接用 `D:\code\ai_xuexi\.env` 覆盖）
- 数据库：`app.db`（SQLite，首次启动自动建表）
- 文档：`http://127.0.0.1:8000/docs`

## 目录结构

```
backend/
├── app/
│   ├── main.py          # FastAPI 入口（/health + 静态页面托管）
│   ├── config.py        # .env 配置（默认关闭 LangSmith 追踪）
│   ├── database.py      # SQLite：users / sessions / messages
│   ├── security.py      # 密码哈希 + JWT 鉴权
│   ├── oss_client.py    # OSS 上传 + object_key 还原 + 签名 URL
│   ├── agent_llm.py     # qwen3.8-max 客户端 + Tavily 工具 + ReAct Agent + 视觉识别
│   └── routes/
│       ├── auth.py      # /api/auth/register, /api/auth/login
│       ├── upload.py    # /api/upload（需鉴权）
│       └── chat.py      # /api/chat, /api/chat/stream, /api/sessions（需鉴权）
├── .env.example / .env
└── requirements.txt
```
