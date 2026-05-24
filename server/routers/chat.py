# -*- coding: utf-8 -*-
"""Agent chat endpoints — SSE streaming + summarization + deep analysis."""
import asyncio
import json
import time
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import Optional

from ..app import get_tickflow, has_config
from ..agent.conversation import ConversationManager
from ..agent.runner import run_agent_loop
from ..services.logger import get_logger

router = APIRouter(prefix="/api/chat", tags=["chat"])

# Shared conversation manager (in-memory, lives as long as server)
_conversations = ConversationManager()
_log = get_logger(__name__)


class ChatRequest(BaseModel):
    message: str
    session_id: Optional[str] = None
    strategy_ids: Optional[list[str]] = None
    action_id: Optional[str] = None


class SummarizeRequest(BaseModel):
    session_id: str


class DeepAnalysisRequest(BaseModel):
    stock_code: str
    session_id: Optional[str] = None
    strategy_ids: Optional[list[str]] = None
    action_id: Optional[str] = None


@router.post("/stream")
async def chat_stream(body: ChatRequest):
    """SSE streaming agent chat."""
    if not has_config():
        raise HTTPException(status_code=503, detail="请先完成配置")

    from ..config_manager import ConfigManager
    config = ConfigManager().load()

    # Resolve session
    session_id = body.session_id
    if not session_id or not _conversations.has_session(session_id):
        session_id = _conversations.create_session()
        _log.info("created new session session=%s", session_id)

    _log.info("chat.stream session=%s message=%.60s", session_id, body.message)

    # Build messages list
    messages = _build_system_message(config, body.strategy_ids)

    # Add conversation history
    history = _conversations.get_history(session_id)
    messages.extend(history)

    # Add user message
    user_msg = body.message
    messages.append({"role": "user", "content": user_msg})
    _conversations.add_message(session_id, "user", user_msg)

    tf = get_tickflow()

    queue: asyncio.Queue = asyncio.Queue()

    async def _run():
        try:
            result = await run_agent_loop(
                messages=messages,
                config=config,
                tickflow=tf,
                progress_callback=queue.put,
            )
            await queue.put(result)
        except Exception as e:
            _log.error("agent loop failed: %s %s", type(e).__name__, e, exc_info=True)
            await queue.put({"type": "error", "message": str(e) or f"{type(e).__name__} (empty detail)"})
        finally:
            await queue.put(None)  # sentinel

    asyncio.ensure_future(_run())

    async def _generate():
        event_count = 0
        done_event = None
        while True:
            event = await queue.get()
            if event is None:
                break
            # If it's the final result (has 'content'), save to conversations
            if isinstance(event, dict) and "content" in event and "type" not in event:
                _conversations.add_message(session_id, "assistant", event["content"])
                event["type"] = "done"
                event["session_id"] = session_id
                done_event = event
            yield f"data: {json.dumps(event, ensure_ascii=False, default=str)}\n\n"
            event_count += 1

        if done_event:
            chart_count = len(done_event.get("chart_specs", []))
            _log.info("chat.stream done session=%s events=%d charts=%d steps=%d",
                      session_id, event_count, chart_count, done_event.get("steps", 0))
        else:
            _log.warning("chat.stream no-done session=%s events=%d", session_id, event_count)

    return StreamingResponse(_generate(), media_type="text/event-stream")


@router.get("/sessions")
async def list_sessions():
    return {"sessions": _conversations.list_sessions()}


@router.delete("/sessions/{session_id}")
async def delete_session(session_id: str):
    _conversations.delete_session(session_id)
    return {"message": "Session deleted"}


@router.post("/summarize")
async def summarize_conversation(body: SummarizeRequest):
    """Generate LLM summary of a conversation."""
    if not has_config():
        raise HTTPException(status_code=503, detail="请先完成配置")

    _log.info("chat.summary session=%s", body.session_id)

    from ..config_manager import ConfigManager
    config = ConfigManager().load()

    start = time.monotonic()
    summary = await _conversations.summarize(
        body.session_id,
        deepseek_api_key=config["deepseek_api_key"],
        deepseek_model=config.get("deepseek_model", "deepseek-v4-flash"),
        deepseek_base_url=config.get("deepseek_base_url", "https://api.deepseek.com"),
    )
    _log.info("chat.summary done session=%s %.3fs", body.session_id, time.monotonic() - start)
    return {"summary": summary}


@router.post("/deep-analysis")
async def deep_analysis(body: DeepAnalysisRequest):
    """Generate a structured deep analysis for a specific stock."""
    if not has_config():
        raise HTTPException(status_code=503, detail="请先完成配置")

    _log.info("deep.analysis stock=%s session=%s", body.stock_code, body.session_id)

    from ..config_manager import ConfigManager
    config = ConfigManager().load()

    messages = _build_system_message(config, body.strategy_ids)

    # Add conversation context if available
    if body.session_id and _conversations.has_session(body.session_id):
        history = _conversations.get_history(body.session_id)
        context = "以下是此前的对话背景：\n" + "\n".join(
            f"{'用户' if m['role'] == 'user' else '助手'}: {(m['content'] or '')[:200]}"
            for m in history[-6:]  # last 6 messages for context
        )
        messages.append({"role": "user", "content": context})

    prompt = f"""请对股票 {body.stock_code} 做一次完整的深度分析。

请按以下结构输出分析结果：

## 基本信息
- 代码/名称/当前价格

## 技术面分析
- 趋势判断
- 均线系统
- 关键支撑/阻力位
- MACD/RSI 等技术指标

## 消息面/舆情
- 近期重要新闻
- 知乎/网络观点摘要

## 风险评估
- 主要风险点
- 需关注的信号

## 操作建议
- 短期建议
- 止损位设置
- 仓位建议

请用 markdown 格式输出，包含具体的价格和日期。"""

    messages.append({"role": "user", "content": prompt})

    tf = get_tickflow()

    start = time.monotonic()
    result = await run_agent_loop(
        messages=messages,
        config=config,
        tickflow=tf,
        max_steps=8,
        max_wall_clock=180.0,
    )
    _log.info("deep.analysis done stock=%s steps=%d charts=%d %.3fs",
              body.stock_code, result.get("steps", 0), len(result.get("chart_specs", [])),
              time.monotonic() - start)

    return {
        "analysis": result["content"],
        "chart_specs": result.get("chart_specs", []),
        "steps": result["steps"],
    }


def _build_system_message(config: dict, strategy_ids: Optional[list[str]] = None) -> list[dict]:
    """Build the system prompt with optional strategy injection."""
    system_text = """你是一个专业的股票分析助手。你可以使用以下工具：
- search_zhihu: 搜索知乎上的股票相关内容
- search_global: 搜索全网新闻和资讯
- get_klines: 获取股票历史K线数据
- get_realtime_quote: 获取股票实时行情
- get_instrument_info: 获取股票基本信息

分析规则：
1. 技术分析时务必先调用 get_klines 获取数据，基于实际数据做判断
2. 需要了解舆论时调用 search_zhihu 或 search_global
3. 回复要具体，包含价格、日期、百分比等实际数字
4. 风险提示要明确，不可模糊
5. 所有建议仅供参考，不构成投资建议
6. 如果你觉得回复中应该包含走势图，请在回复末尾用一个 ```chart_specs 代码块包含图表参数，格式：
```chart_specs
[{"symbol": "600519.SH", "period": "1d", "title": "贵州茅台日K走势"}]
```
如果用户询问了特定的时间范围（如"近3个月""2024年1月到3月""今年以来"等），请将起止日期填入 start_date 和 end_date 字段（YYYY-MM-DD 格式）：
```chart_specs
[{"symbol": "600519.SH", "period": "1d", "start_date": "2024-01-01", "end_date": "2024-03-31", "title": "贵州茅台2024年一季度日K走势"}]
```
可用周期: 日K=1d, 周K=1w, 月K=1M, 年K=1Y。不指定周期则默认日K。
"""

    # Inject strategy instructions if selected
    if strategy_ids:
        from ..services.strategies import load_strategies
        all_strategies = load_strategies()
        strategy_texts = []
        for sid in strategy_ids:
            for s in all_strategies:
                if s["id"] == sid:
                    strategy_texts.append(f"## 使用策略: {s['name']}\n{s['instructions']}")
                    break
        if strategy_texts:
            system_text += "\n\n---\n\n本次分析请重点参考以下策略：\n\n" + "\n\n---\n\n".join(strategy_texts)

    return [{"role": "system", "content": system_text}]
