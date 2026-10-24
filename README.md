# 编程答疑 Agent

面向 Python 自学者的编程答疑 Agent：**传图 / 文字提问 → 视觉识别 → Tavily 联网检索 → LangChain Agent 生成 → 结构化回答（附参考来源）**。

- 前端：首页展示（登录态联动）、登录注册页、AI 对话页（侧边栏会话管理 + 流式输出 + 图片预览）
- 后端：FastAPI + LangChain ReAct Agent + 通义千问 qwen3.8-max + Tavily + 阿里云 OSS + SQLite + JWT
- 部署形态：**本地部署**，数据不出本地

<p align="center"><img src="docs/images/homepage-hero.png" alt="编程答疑 Agent 首页" width="720"/></p>

---

## 目录结构

```
agent_demo01/
├── index.html                  # 首页（hero 打字机 + 核心优势 / 方案价格 / 常见问题）
├── login.html                  # 登录 / 注册页
├── chat.html                   # AI 对话页（侧边栏会话 + 流式 Markdown + 图片 Lightbox）
├── 编程答疑Agent_产品文档.md     # 产品需求文档 v1.0
├── README.md                   # 本文档
└── backend/
    ├── app/
    │   ├── main.py             # FastAPI 入口：路由注册 + 静态页面托管 + /health
    │   ├── config.py           # .env 配置读取（默认关闭 LangSmith 追踪）
    │   ├── database.py         # SQLite：users / sessions / messages 三表
    │   ├── security.py         # 密码哈希 + JWT 签发与校验
    │   ├── oss_client.py       # 阿里云 OSS 上传 + object_key 还原 + 签名 URL
    │   ├── agent_llm.py        # qwen3.8-max 客户端 + Tavily 工具 + ReAct Agent + 视觉识别
    │   └── routes/
    │       ├── auth.py         # POST /api/auth/register、/api/auth/login
    │       ├── upload.py       # POST /api/upload（OSS 上传，需鉴权）
    │       └── chat.py         # /api/chat、/api/chat/stream、/api/sessions、/api/sessions/{id}/messages
    ├── .env.example            # 配置模板（复制为 .env 填写）
    ├── .env                    # 真实密钥（本地，勿提交仓库）
    ├── app.db                  # SQLite 数据库（首次启动自动建表）
    ├── requirements.txt
    └── test_chat.py / test_upload.py   # 自测脚本
```

---

## 环境要求

| 依赖 | 说明 |
| --- | --- |
| Windows / macOS / Linux | 本地部署，已适配 Windows 开发环境 |
| Python | 3.10+ |
| 虚拟环境 | 建议使用独立 venv（本项目为 `D:\code\ai_xuexi\.venv`） |
| 网络 | 需可访问阿里云百炼、Tavily、阿里云 OSS |

### 需要的账号与密钥

| 服务 | 用途 | 获取方式 |
| --- | --- | --- |
| 阿里云百炼 | qwen3.8-max 文本 + 图像识别 | [百炼控制台](https://bailian.console.aliyun.com/) → API-KEY |
| Tavily | 联网检索工具 | [tavily.com](https://tavily.com/) → API Key |
| 阿里云 OSS | 图片存储（私有桶） | [OSS 控制台](https://oss.console.aliyun.com/) → AccessKey + 创建 Bucket |

---

## 快速开始

### 1. 安装依赖（虚拟环境）

```powershell
D:\code\ai_xuexi\.venv\Scripts\python.exe -m pip install -r D:\code\ai_xuexi\agent_demo01\backend\requirements.txt
```

### 2. 配置密钥

```powershell
# 复制模板（首次）
Copy-Item -LiteralPath "D:\code\ai_xuexi\agent_demo01\backend\.env.example" -Destination "D:\code\ai_xuexi\agent_demo01\backend\.env"

# 或用你已有的密钥文件直接覆盖（本项目标准做法）
Copy-Item -LiteralPath "D:\code\ai_xuexi\.env" -Destination "D:\code\ai_xuexi\agent_demo01\backend\.env"
```

打开 `backend\.env` 核对以下变量（`.env` 不提交仓库）：

| 变量 | 示例 / 说明 |
| --- | --- |
| `DASHSCOPE_API_KEY` | 百炼 API Key，必填 |
| `DASHSCOPE_BASE_URL` | 固定 `https://dashscope.aliyuncs.com/compatible-mode/v1` |
| `LLM_MODEL` | 文本模型，本项目固定 `qwen3.8-max` |
| `TAVILY_API_KEY` | Tavily Key，必填 |
| `OSS_ACCESS_KEY_ID` / `OSS_ACCESS_KEY_SECRET` | OSS 密钥，必填 |
| `OSS_BUCKET` | Bucket 名称（注意连字符，如 `tmp-7100`），必填 |
| `OSS_ENDPOINT` | **必须与 Bucket 实际地域一致**，如北京 `oss-cn-beijing.aliyuncs.com` |
| `OSS_URL_EXPIRES` | 签名 URL 有效期秒数，默认 300 |
| `SECRET_KEY` | JWT 签名密钥，生产环境请更换为随机长字符串 |
| `DATABASE_PATH` | SQLite 文件路径，默认 `./app.db` |

> `VISION_MODEL` 已弃用：qwen3.8-max 本身支持图像输入，视觉识别由同一模型完成。

### 3. 启动后端服务

```powershell
cd D:\code\ai_xuexi\agent_demo01\backend
D:\code\ai_xuexi\.venv\Scripts\python.exe -m uvicorn app.main:app --host 0.0.0.0 --port 8000
```

启动后访问：

| 地址 | 说明 |
| --- | --- |
| `http://127.0.0.1:8000/` | 首页 |
| `http://127.0.0.1:8000/login.html` | 登录 / 注册页 |
| `http://127.0.0.1:8000/chat.html` | AI 对话页（需登录） |
| `http://127.0.0.1:8000/health` | 健康检查（会列出缺失的密钥配置项） |
| `http://127.0.0.1:8000/docs` | Swagger 接口文档 |

### 4. 测试账号

首次使用请先注册。已有测试账号：**demo / 123456**

---

## 核心功能

### 前端

| 页面 | 功能 |
| --- | --- |
| 首页 | hero 打字机动画、登录态 CTA 切换（未登录"登录/注册"→ 已登录"开始使用"）、核心优势 6 卡片、方案价格 3 档、常见问题手风琴；深浅色主题联动系统 |
| 登录页 | 注册 + 登录，成功后写入 `localStorage.agent_token` 跳转对话页 |
| 对话页 | 左侧会话侧边栏（今天/昨天/7天内/30天内/更早分组，点击加载历史，悬停删除，桌面可折叠为 56px 窄条、状态记忆）、SSE 流式输出（Markdown 渲染 + DOMPurify 净化）、图片粘贴/上传 + Lightbox 全屏预览、多轮上下文复用 `session_id`、顶栏主题切换 / 返回首页 / 退出（左下角亦有账号 + 退出） |

### 界面预览

**首页**

| 功能特性演示 | 核心优势 |
| --- | --- |
| <img src="docs/images/homepage-features.png" alt="功能特性" width="420"/> | <img src="docs/images/homepage-benefits.png" alt="核心优势" width="420"/> |

| 方案价格 | 常见问题 |
| --- | --- |
| <img src="docs/images/homepage-pricing.png" alt="方案价格" width="420"/> | <img src="docs/images/homepage-faq.png" alt="常见问题" width="420"/> |

**登录注册页**

<p align="center"><img src="docs/images/login.png" alt="登录注册页" width="720"/></p>

**AI 对话页**

| 空状态 | 流式回答 |
| --- | --- |
| <img src="docs/images/chat-empty.png" alt="对话页空状态" width="420"/> | <img src="docs/images/chat-conversation.png" alt="流式回答" width="420"/> |

<p align="center"><img src="docs/images/chat-lightbox.png" alt="图片预览" width="720"/></p>

### 后端接口

| 接口 | 方法 | 说明 | 鉴权 |
| --- | --- | --- | --- |
| `/api/auth/register` | POST | 注册（用户名/密码） | 否 |
| `/api/auth/login` | POST | 登录，返回 JWT Token | 否 |
| `/api/upload` | POST | 上传图片至 OSS（jpg/png/webp ≤10MB） | 是 |
| `/api/chat` | POST | 非流式问答（保留） | 是 |
| `/api/chat/stream` | POST | SSE 流式问答，事件 `status/token/citation/error/done` | 是 |
| `/api/sessions` | GET | 当前用户会话列表 | 是 |
| `/api/sessions/{id}` | DELETE | 删除会话（连同消息） | 是 |
| `/api/sessions/{id}/messages` | GET | 会话消息（历史图片自动重新签名） | 是 |

> 鉴权方式：请求头 `Authorization: Bearer <token>`。

### 关键设计

- **流式输出**：`agent.astream(stream_mode="messages")` 逐 token 推送；qwen3.8-max 通过 `extra_body={"enable_thinking": False}` 关闭思考模式，避免空 chunk
- **检索策略**：系统提示允许模型自判——代码解释类问题可直答不检索，时效性问题触发 Tavily
- **图片链路**：上传返回带时效签名 URL → 入库存 `object_key`（`user_uploads/{date}/{uuid}.ext`）→ 读取历史时动态重签，永不过期
- **数据隔离**：会话按 `user_id` 隔离，删除会话双校验归属
- **安全**：密码 bcrypt 哈希、JWT 鉴权、Markdown 渲染经 DOMPurify 消毒

---

## 常见问题排查

| 现象 | 原因与处理 |
| --- | --- |
| `/health` 提示缺少配置 | 检查 `backend\.env` 中 DASHSCOPE_API_KEY / TAVILY_API_KEY / OSS 三项是否填真实值（占位符会被判定为未配置） |
| 上传报错 `NoSuchBucket` | `OSS_BUCKET` 与 `OSS_ENDPOINT` 不匹配：Bucket 带连字符全名 + 地域 endpoint 必须一致 |
| 历史会话图片不显示（403） | 旧版本曾直接存储过期签名 URL；现版本读取时自动从 object_key 重新签名，刷新即可恢复 |
| 流式输出只出 1 个块 / 回答慢 | 确认 `enable_thinking` 已生效（agent_llm.py）；另 LangSmith 追踪已默认关闭，勿手动开启 |
| 页面样式异常 | 浏览器缓存了旧版 HTML，`Ctrl+F5` 强制刷新 |
| 端口被占用 | 换端口启动：`--port 8001`，同时前端页面地址相应调整 |

---

## 自测

```powershell
# 后端目录下运行（需服务已启动）
cd D:\code\ai_xuexi\agent_demo01\backend
D:\code\ai_xuexi\.venv\Scripts\python.exe -u test_chat.py    # 流式问答链路
D:\code\ai_xuexi\.venv\Scripts\python.exe -u test_upload.py  # 图片上传链路
```

---

## 里程碑

- [x] M1 技术验证：Agent 骨架 / Tavily / 多模态识别 / OSS / FastAPI / SQLite / 登录
- [x] M2 全栈落地：前端三页 + 登录鉴权 + SSE 流式 + 会话管理 + 图片链路
- [x] M3 打磨收尾：历史图片重签、侧边栏折叠、输入区美化、首页内容化
- [ ] 效果持续调优（输出长度、检索质量、成本控制）
