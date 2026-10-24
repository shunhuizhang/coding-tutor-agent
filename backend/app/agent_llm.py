"""LLM 客户端与 LangChain Agent 编排。

- 文本模型：qwen3.8-max（OpenAI 兼容接口）
- 视觉模型：qwen-vl-max（OpenAI 兼容接口，用于识别截图中的代码/报错）
- 联网检索：Tavily 工具，挂在 LangChain ReAct Agent 上
"""
import asyncio
import json
import re

from fastapi import HTTPException
from langchain_core.messages import AIMessage, AIMessageChunk, SystemMessage, ToolMessage, HumanMessage
from langchain_openai import ChatOpenAI
from langchain_tavily import TavilySearch
from langgraph.prebuilt import create_react_agent
from openai import OpenAI

from .config import _unset, settings

_llm = None
_vision_client = None
_agent = None

SYSTEM_PROMPT = """你是一个面向 Python 自学者的编程答疑助手。

回答要求：
1. 先判断用户意图：报错诊断 / 代码解释 / 需求实现 / 概念教学。
2. 报错诊断与需求实现类问题，可调用搜索工具联网检索最新资料后再回答。
3. 回答使用固定结构：【问题诊断】【原因分析】【解决方案】【示例代码】【参考来源】【进一步提问建议】。
4. 引用真实来源：来自搜索结果的信息必须带来源链接；无法联网时明确标注“基于模型知识回答，建议进一步验证”。
5. 示例代码给出可直接运行的完整片段，并提示用户自行验证。
6. 全程使用中文。
7. 控制篇幅：除示例代码外，正文保持简洁精炼，不要堆砌无关内容。
8. 打招呼、询问你是谁/你能做什么等身份与闲聊类问题，直接友好回答，不要调用搜索工具。
9. 当用户消息中包含系统提供的图片提取内容时，直接基于内容作答，不要提及图片识别过程或“识别失败”等无关表述。
"""

# 直答类问题：问候 / 身份 / 闲聊，无需联网检索
_DIRECT_ANSWER_PATTERN = re.compile(
    r"(你是谁|你叫什么|你是什么|介绍一下你|介绍下你|介绍你自己|你能做什么|你会什么"
    r"|你有什么功能|你是什么模型|你是ai吗|你是AI吗|你是机器人吗|你是人吗"
    r"|你好|您好|哈喽|嗨|hello|hi|hey|早上好|下午好|晚上好"
    r"|谢谢|感谢|再见|拜拜|bye|辛苦了|在吗|在不在)", re.IGNORECASE)


def should_direct_answer(text: str) -> bool:
    """判断是否为问候/身份/闲聊类问题（直答，不调用搜索工具）。"""
    return bool(_DIRECT_ANSWER_PATTERN.search(text))


def get_llm() -> ChatOpenAI:
    global _llm
    if _llm is None:
        if _unset(settings.dashscope_api_key):
            raise HTTPException(
                status_code=503,
                detail="缺少 DASHSCOPE_API_KEY，请在 backend/.env 中配置后重启服务",
            )
        _llm = ChatOpenAI(
            model=settings.llm_model,
            api_key=settings.dashscope_api_key,
            base_url=settings.dashscope_base_url,
            temperature=0.3,
            max_tokens=800,  # 限制输出长度，避免模型长篇输出拖慢响应
            # 关闭思考模式：qwen3.8-max 默认思考时流式会概率性输出全空 chunk
            # （空块 50+ → 关闭后 <5），导致前端收不到逐字内容。
            extra_body={"enable_thinking": False},
        )
    return _llm


def get_vision_client() -> OpenAI:
    global _vision_client
    if _vision_client is None:
        if _unset(settings.dashscope_api_key):
            raise HTTPException(
                status_code=503,
                detail="缺少 DASHSCOPE_API_KEY，请在 backend/.env 中配置后重启服务",
            )
        _vision_client = OpenAI(
            api_key=settings.dashscope_api_key,
            base_url=settings.dashscope_base_url,
        )
    return _vision_client


_vision_client_async = None


def get_vision_client_async():
    """异步视觉客户端（流式链路用，避免阻塞事件循环）。"""
    global _vision_client_async
    if _vision_client_async is None:
        if _unset(settings.dashscope_api_key):
            raise HTTPException(
                status_code=503,
                detail="缺少 DASHSCOPE_API_KEY，请在 backend/.env 中配置后重启服务",
            )
        from openai import AsyncOpenAI

        _vision_client_async = AsyncOpenAI(
            api_key=settings.dashscope_api_key,
            base_url=settings.dashscope_base_url,
        )
    return _vision_client_async


def extract_from_image(image_url: str) -> str:
    """用 qwen3.8-max 识别图片中的代码/报错文本，返回结构化文本。

    注意：qwen-vl-max 在本账号未开通（403/404），而 qwen3.8-max 本身支持
    图像输入，因此视觉识别直接复用文本模型。
    """
    client = get_vision_client()
    prompt = (
        "请识别这张图片中的内容并输出：\n"
        "1. 如果是报错信息：输出报错类型和完整报错文本。\n"
        "2. 如果是代码：输出完整代码，注明语言。\n"
        "3. 其他情况：简要描述图片内容。\n"
        "只输出识别结果本身，不要额外解释。"
    )
    resp = client.chat.completions.create(
        model=settings.llm_model,
        messages=[
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {"type": "image_url", "image_url": {"url": image_url}},
                ],
            }
        ],
        extra_body={"enable_thinking": False},
    )
    return resp.choices[0].message.content or ""


async def extract_from_image_async(image_url: str) -> str:
    """异步版图片识别（流式链路用，qwen3.8-max 支持图像输入）。

    模型图片调用偶发超时/失败：最多重试 2 次。
    """
    client = get_vision_client_async()
    prompt = (
        "请识别这张图片中的内容并输出：\n"
        "1. 如果是报错信息：输出报错类型和完整报错文本。\n"
        "2. 如果是代码：输出完整代码，注明语言。\n"
        "3. 其他情况：简要描述图片内容。\n"
        "只输出识别结果本身，不要额外解释。"
    )
    for attempt in range(3):
        try:
            resp = await client.chat.completions.create(
                model=settings.llm_model,
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": prompt},
                            {"type": "image_url", "image_url": {"url": image_url}},
                        ],
                    }
                ],
                extra_body={"enable_thinking": False},
            )
            return resp.choices[0].message.content or ""
        except Exception:
            if attempt >= 2:
                raise
            await asyncio.sleep(1)
    return ""


def _tavily_tool():
    if _unset(settings.tavily_api_key):
        raise HTTPException(
            status_code=503,
            detail="缺少 TAVILY_API_KEY，请在 backend/.env 中配置后重启服务",
        )
    return TavilySearch(
        max_results=settings.tavily_max_results,
        tavily_api_key=settings.tavily_api_key,  # 显式传入，避免依赖进程环境变量
    )


def get_agent():
    """构建 LangChain ReAct Agent：qwen3.8-max + Tavily 搜索工具。"""
    global _agent
    if _agent is None:
        _agent = create_react_agent(
            model=get_llm(),
            tools=[_tavily_tool()],
            prompt=SystemMessage(content=SYSTEM_PROMPT),
        )
    return _agent


def extract_citations(messages) -> list[str]:
    """从工具调用结果中提取 Tavily 返回的来源链接。"""
    urls: list[str] = []
    for msg in messages:
        if isinstance(msg, ToolMessage):
            try:
                data = json.loads(msg.content)
                # TavilySearch 返回 dict：{"query": ..., "results": [...]}
                if isinstance(data, dict):
                    items = data.get("results", [])
                elif isinstance(data, list):
                    items = data
                else:
                    items = []
                for item in items:
                    if isinstance(item, dict) and item.get("url"):
                        urls.append(item["url"])
            except (json.JSONDecodeError, TypeError):
                continue
    # 去重保序
    seen, out = set(), []
    for u in urls:
        if u not in seen:
            seen.add(u)
            out.append(u)
    return out


def chat_once(user_text: str, image_urls: list[str] | None = None) -> dict:
    """单轮调用 Agent，返回回答文本 + 参考来源。"""
    content = user_text
    if image_urls:
        vision_parts = []
        for url in image_urls:
            try:
                vision_parts.append(extract_from_image(url))
            except Exception as e:  # 视觉识别失败不阻断主链路
                vision_parts.append(f"[图片识别失败: {e}]")
        if vision_parts:
            content = f"{user_text}\n\n[用户上传的图片，已由系统识别提取为以下内容，请直接使用]\n" + "\n---\n".join(vision_parts)

    # 问候 / 身份 / 闲聊类问题：直答，不调用搜索工具
    if not image_urls and should_direct_answer(user_text):
        answer = direct_answer(user_text)
        return {"answer": answer, "citations": []}

    agent = get_agent()
    result = agent.invoke(
        {"messages": [HumanMessage(content=content)]},
        config={"recursion_limit": 8},  # 限制思考-行动循环，防止无限循环拖慢响应
    )

    final = result.get("messages", [])
    # 取最后一条 AI 消息作为回答
    answer = ""
    for msg in reversed(final):
        if isinstance(msg, AIMessage):
            answer = msg.content or ""
            break
    citations = extract_citations(final)
    return {"answer": answer, "citations": citations}


def direct_answer(user_text: str) -> str:
    """问候/身份/闲聊类问题的直答：仅 LLM，不接任何工具。"""
    llm = get_llm()
    resp = llm.invoke(
        [
            SystemMessage(content=SYSTEM_PROMPT),
            HumanMessage(content=user_text),
        ]
    )
    return resp.content or ""


def _urls_from_tool_content(tool_content: str) -> list[str]:
    """从单条 ToolMessage 内容提取 Tavily 来源链接。"""
    urls: list[str] = []
    try:
        data = json.loads(tool_content)
        if isinstance(data, dict):
            items = data.get("results", [])
        elif isinstance(data, list):
            items = data
        else:
            items = []
        for item in items:
            if isinstance(item, dict) and item.get("url"):
                urls.append(item["url"])
    except (json.JSONDecodeError, TypeError):
        pass
    return urls


async def stream_answer(user_text: str, image_urls: list[str] | None = None):
    """流式生成回答（SSE 事件源）。

    基于 LangChain ReAct Agent 的 stream_mode="messages" 事件流：
      - AIMessageChunk：逐 token 输出（yield ("token", ...)）
      - ToolMessage：工具执行结果，从中提取引用来源（结束 yield ("citations", ...)）

    事件类型（yield (etype, payload)）：
      - ("status", str)：阶段状态（识别图片 / 开始生成）
      - ("token", str)：回答文本增量
      - ("citations", list[str])：参考来源 URL
    """
    content = user_text
    if image_urls:
        yield ("status", "正在识别图片…")
        vision_parts = []
        for url in image_urls:
            try:
                vision_parts.append(await extract_from_image_async(url))
            except Exception as e:  # 视觉识别失败不阻断主链路
                vision_parts.append(f"[图片识别失败: {e}]")
        if vision_parts:
            content = f"{user_text}\n\n[用户上传的图片，已由系统识别提取为以下内容，请直接使用]\n" + "\n---\n".join(vision_parts)

    yield ("status", "正在思考…")
    agent = get_agent()

    # qwen3.8-max 偶发流式空输出（全空 chunk）：一个 token 都没出则重试，最多 3 次
    for attempt in range(3):
        citations: list[str] = []
        got_text = False
        try:
            async for msg, metadata in agent.astream(
                {"messages": [HumanMessage(content=content)]},
                config={"recursion_limit": 8},
                stream_mode="messages",
            ):
                if isinstance(msg, AIMessageChunk) and msg.content:
                    got_text = True
                    yield ("token", msg.content)
                elif isinstance(msg, ToolMessage):
                    for u in _urls_from_tool_content(msg.content):
                        if u not in citations:
                            citations.append(u)
        except Exception:
            pass
        if got_text:
            break
        # 本次空输出：重新调用 Agent 再试
    else:
        # 三次流式均空：非流式兜底（线程池避免阻塞事件循环）
        yield ("status", "正在整理回答…")
        result = await asyncio.to_thread(
            lambda: agent.invoke(
                {"messages": [HumanMessage(content=content)]},
                config={"recursion_limit": 8},
            )
        )
        final = result.get("messages", [])
        answer = ""
        for m in reversed(final):
            if isinstance(m, AIMessage):
                answer = m.content or ""
                break
        if answer:
            yield ("token", answer)
        for m in final:
            if isinstance(m, ToolMessage):
                for u in _urls_from_tool_content(m.content):
                    if u not in citations:
                        citations.append(u)

    if citations:
        yield ("citations", citations)
