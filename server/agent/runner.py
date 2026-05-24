# -*- coding: utf-8 -*-
"""ReAct agent loop — the core LLM-tool-observation cycle."""
import asyncio
import json
import time
from typing import Any, Callable, Optional

from .client_ext import LLMClient
from .tools import _make_tools
from ..services.logger import get_logger

log = get_logger(__name__)

# Budget guard: if less than this many seconds remain before next LLM call, abort.
_MIN_STEP_BUDGET_S = 8.0


async def run_agent_loop(
    messages: list[dict],
    config: dict,
    tickflow,
    *,
    max_steps: int = 10,
    max_wall_clock: float = 120.0,
    progress_callback: Optional[Callable] = None,
) -> dict:
    """Run the ReAct agent loop.

    Args:
        messages: Conversation history (system + user + tool messages).
        config: App config dict (deepseek_api_key, model, etc.).
        tickflow: TickFlow free-tier instance.
        max_steps: Max tool-calling iterations.
        max_wall_clock: Total time budget in seconds.
        progress_callback: Async callable to emit SSE events to the frontend.
            Receives dicts like {type: "tool_start", tool: "get_klines", ...}.

    Returns:
        {content: str, chart_specs: list[dict], steps: int, session_id: str}
    """
    client = LLMClient(
        api_key=config["deepseek_api_key"],
        model=config.get("deepseek_model", "deepseek-v4-flash"),
        base_url=config.get("deepseek_base_url", "https://api.deepseek.com"),
    )

    tools = _make_tools(tickflow, config)
    tool_defs = [t for t in tools]  # keep metadata for handler lookup
    tool_schemas = [{"type": t["type"], "function": t["function"]} for t in tools]
    tool_map = {t["function"]["name"]: t for t in tools}

    deadline = time.monotonic() + max_wall_clock
    tool_results_cache: dict[str, dict] = {}

    for step in range(1, max_steps + 1):
        remaining = deadline - time.monotonic()
        if remaining < _MIN_STEP_BUDGET_S and step > 1:
            log.warning("timeout step=%d remaining=%.1fs", step, remaining)
            return {
                "content": "分析已超时，以下是目前已获取的信息。请重新提问获取更完整的分析。",
                "chart_specs": [],
                "steps": step - 1,
            }

        # LLM call
        if progress_callback:
            await progress_callback({
                "type": "thinking",
                "step": step,
                "message": "正在分析..." if step == 1 else f"正在进一步分析（第 {step} 步）...",
            })

        log.info("step %d/%d LLM call", step, max_steps)
        llm_start = time.monotonic()
        try:
            response = await client.chat_with_tools(messages, tool_schemas)
        except Exception as e:
            log.error("step %d/%d LLM call failed: %s %s",
                      step, max_steps, type(e).__name__, e, exc_info=True)
            return {
                "content": f"AI 服务调用失败: {type(e).__name__}。请检查 API 配置或稍后重试。",
                "chart_specs": [],
                "steps": step - 1,
            }
        llm_elapsed = time.monotonic() - llm_start
        choice = response.get("choices", [{}])[0]
        msg = choice.get("message", {})

        # Check for tool calls
        tool_calls = msg.get("tool_calls") or []
        if tool_calls:
            log.info("step %d/%d LLM done (%.3fs) tools=%d", step, max_steps, llm_elapsed, len(tool_calls))
            # Append assistant message (must include reasoning_content if present)
            assistant_msg = {"role": "assistant", "content": msg.get("content") or "", "tool_calls": tool_calls}
            if msg.get("reasoning_content"):
                assistant_msg["reasoning_content"] = msg["reasoning_content"]
            messages.append(assistant_msg)

            for tc in tool_calls:
                tc_id = tc.get("id", "")
                func = tc.get("function", {})
                tool_name = func.get("name", "")
                tool_args = func.get("arguments", "{}")

                if isinstance(tool_args, str):
                    try:
                        tool_args = json.loads(tool_args)
                    except json.JSONDecodeError:
                        tool_args = {}

                tool_info = tool_map.get(tool_name, {})
                display_name = tool_info.get("display_name", tool_name)

                if progress_callback:
                    await progress_callback({
                        "type": "tool_start",
                        "tool": tool_name,
                        "display_name": display_name,
                        "args": {k: str(v)[:100] for k, v in tool_args.items()},
                    })

                # Check cache
                cache_key = f"{tool_name}:{json.dumps(tool_args, sort_keys=True, default=str)}"
                if cache_key in tool_results_cache:
                    result = tool_results_cache[cache_key]
                    log.info("step %d/%d tool=%s cache hit", step, max_steps, tool_name)
                else:
                    handler = tool_info.get("handler")
                    tool_start = time.monotonic()
                    if handler:
                        try:
                            result = await asyncio.to_thread(handler, tool_args)
                        except Exception as e:
                            result = {"error": str(e), "retriable": False}
                            log.error("step %d/%d tool=%s exception: %s",
                                      step, max_steps, tool_name, e, exc_info=True)
                    else:
                        log.warning("step %d/%d unknown tool=%s", step, max_steps, tool_name)
                        result = {"error": f"Unknown tool: {tool_name}", "retriable": False}
                    tool_elapsed = time.monotonic() - tool_start
                    result_size = len(json.dumps(result, ensure_ascii=False, default=str))
                    is_error = "error" in result
                    log.info("step %d/%d tool=%s done %.3fs result=%dKB%s",
                             step, max_steps, tool_name, tool_elapsed,
                             result_size // 1024, " ERROR" if is_error else "")
                    tool_results_cache[cache_key] = result

                # Build summary for UI
                summary = _build_tool_summary(tool_name, result)

                if progress_callback:
                    await progress_callback({
                        "type": "tool_done",
                        "tool": tool_name,
                        "display_name": display_name,
                        "summary": summary,
                    })

                # Append tool result
                messages.append({
                    "role": "tool",
                    "tool_call_id": tc_id,
                    "content": json.dumps(result, ensure_ascii=False, default=str),
                })
        else:
            # Final answer — no tool calls
            content = msg.get("content", "")
            chart_specs = _extract_chart_specs(content)
            log.info("step %d/%d LLM done (%.3fs) final answer charts=%d", step, max_steps, llm_elapsed, len(chart_specs))

            if progress_callback:
                await progress_callback({
                    "type": "done",
                    "content": content,
                    "chart_specs": chart_specs,
                    "steps": step,
                })

            return {
                "content": content,
                "chart_specs": chart_specs,
                "steps": step,
            }

    # Exhausted max steps
    log.warning("max steps exhausted steps=%d", max_steps)
    return {
        "content": "分析已超过最大步数限制。请尝试更具体的问题。",
        "chart_specs": [],
        "steps": max_steps,
    }


def _build_tool_summary(tool_name: str, result: dict) -> str:
    """Build a short Chinese summary of tool result for the UI progress display."""
    if result.get("error"):
        return f"失败: {result['error'][:50]}"
    if tool_name in ("search_zhihu", "search_global"):
        return f"找到 {result.get('count', 0)} 条结果"
    if tool_name == "get_klines":
        latest = result.get("latest", {})
        return f"{latest.get('date', '')} 收盘 {latest.get('close', 'N/A')}"
    if tool_name == "get_realtime_quote":
        return f"{result.get('name', '')} {result.get('price', 'N/A')} ({result.get('change_pct', 0):+.2f}%)"
    if tool_name == "get_instrument_info":
        return f"{result.get('name', '')} ({result.get('type', '')})"
    return "完成"


def _extract_chart_specs(content: str) -> list[dict]:
    """Extract chart specifications from the agent's response.

    The agent may include chart specs in a JSON code block labeled `chart_specs`.
    Fallback: if the content mentions a stock code with K-line data context,
    try to parse chart hints from the text (heuristic).
    """
    specs = []
    # Try to find ```chart_specs ... ``` blocks
    import re
    pattern = r'```chart_specs\s*\n(.*?)```'
    matches = re.findall(pattern, content, re.DOTALL)
    for m in matches:
        try:
            spec = json.loads(m.strip())
            if isinstance(spec, list):
                specs.extend(spec)
            elif isinstance(spec, dict):
                specs.append(spec)
        except json.JSONDecodeError:
            pass
    return specs
