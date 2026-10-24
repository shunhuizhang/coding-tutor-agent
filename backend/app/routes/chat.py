"""问答接口：多轮上下文（SQLite）+ 图片识别 + Agent 调用（含 SSE 流式）。"""
import json

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from .. import agent_llm
from ..database import add_message, create_session, delete_session, get_messages, get_sessions
from ..oss_client import object_key_from_url, oss_client
from ..security import get_current_user

router = APIRouter(prefix="/api", tags=["chat"])


class ChatIn(BaseModel):
    message: str = Field(min_length=1)
    image_urls: list[str] = Field(default_factory=list, max_length=3)
    session_id: int | None = None


@router.post("/chat")
def chat(body: ChatIn, user: dict = Depends(get_current_user)):
    # 1. 会话：无 session_id 则新建
    session_id = body.session_id
    if session_id is None:
        session_id = create_session(user["id"], title=body.message[:20])
    else:
        sessions = get_sessions(user["id"])
        if not any(s["id"] == session_id for s in sessions):
            raise HTTPException(status_code=404, detail="会话不存在")

    # 2. 保存用户消息（image_urls 存 object_key，签名 URL 会过期不可入库存）
    add_message(session_id, "user", body.message, image_urls=[object_key_from_url(u) for u in body.image_urls])

    # 3. 调用 Agent（含图片识别 + 联网检索）
    try:
        result = agent_llm.chat_once(body.message, body.image_urls)
    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Agent 调用失败: {e}")

    # 4. 保存回答并返回
    add_message(
        session_id,
        "assistant",
        result["answer"],
        citations=result["citations"],
    )
    return {
        "session_id": session_id,
        "answer": result["answer"],
        "citations": result["citations"],
    }


@router.post("/chat/stream")
async def chat_stream(body: ChatIn, user: dict = Depends(get_current_user)):
    """流式问答（SSE）：识别图片 → 联网检索 → 逐 token 输出回答。"""
    # 1. 会话：无 session_id 则新建
    session_id = body.session_id
    if session_id is None:
        session_id = create_session(user["id"], title=body.message[:20])
    else:
        sessions = get_sessions(user["id"])
        if not any(s["id"] == session_id for s in sessions):
            raise HTTPException(status_code=404, detail="会话不存在")

    # 2. 保存用户消息（image_urls 存 object_key，签名 URL 会过期不可入库存）
    add_message(session_id, "user", body.message, image_urls=[object_key_from_url(u) for u in body.image_urls])

    async def gen():
        full_answer: list[str] = []
        citations: list[str] = []

        def sse(payload: dict) -> str:
            return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"

        try:
            async for etype, payload in agent_llm.stream_answer(body.message, body.image_urls):
                if etype == "token":
                    full_answer.append(payload)
                    yield sse({"type": "token", "content": payload})
                elif etype == "status":
                    yield sse({"type": "status", "message": payload})
                elif etype == "citations":
                    citations = payload
                    yield sse({"type": "citation", "urls": payload})
        except HTTPException as e:
            yield sse({"type": "error", "message": e.detail})
        except Exception as e:
            yield sse({"type": "error", "message": f"Agent 调用失败: {e}"})

        # 3. 保存回答（流结束后落库）
        answer_text = "".join(full_answer)
        if answer_text:
            add_message(session_id, "assistant", answer_text, citations=citations)

        yield sse({"type": "done", "session_id": session_id})

    return StreamingResponse(
        gen(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/sessions")
def list_sessions(user: dict = Depends(get_current_user)):
    return [
        {"id": s["id"], "title": s["title"], "created_at": s["created_at"]}
        for s in get_sessions(user["id"])
    ]


@router.delete("/sessions/{session_id}")
def remove_session(session_id: int, user: dict = Depends(get_current_user)):
    """删除会话（连同其全部消息），仅限归属当前用户的会话。"""
    if not delete_session(session_id, user["id"]):
        raise HTTPException(status_code=404, detail="会话不存在")
    return {"ok": True, "session_id": session_id}


@router.get("/sessions/{session_id}/messages")
def session_messages(session_id: int, user: dict = Depends(get_current_user)):
    sessions = get_sessions(user["id"])
    if not any(s["id"] == session_id for s in sessions):
        raise HTTPException(status_code=404, detail="会话不存在")

    def parse_list(raw) -> list:
        """数据库中以 JSON 字符串存储，解析为数组返回。"""
        if not raw:
            return []
        try:
            data = json.loads(raw)
            return data if isinstance(data, list) else []
        except (json.JSONDecodeError, TypeError):
            return []

    def signed_image_urls(raw) -> list:
        """历史图片重新签名：旧数据可能是已过期的完整 URL，统一还原 key 后重新签名。"""
        urls = []
        for item in parse_list(raw):
            try:
                urls.append(oss_client.signed_url(object_key_from_url(item)))
            except Exception:
                continue  # OSS 异常时跳过，不阻断历史加载
        return urls

    return [
        {
            "id": m["id"],
            "role": m["role"],
            "content": m["content"],
            "image_urls": signed_image_urls(m["image_urls"]),
            "citations": parse_list(m["citations"]),
            "created_at": m["created_at"],
        }
        for m in get_messages(session_id)
    ]
