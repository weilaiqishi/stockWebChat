# -*- coding: utf-8 -*-
"""Extended LLM client — wraps DeepSeekClient with tool-calling support.

Follows the same httpx-direct pattern as zhihuTrade/analyzer/client.py.
"""
import asyncio
import json
import time
from typing import Optional
import httpx

from ..services.logger import get_logger

_log = get_logger(__name__)


class LLMClient:
    """Lightweight DeepSeek API client with function-calling support."""

    def __init__(self, api_key: str, model: str = "deepseek-v4-flash",
                 base_url: str = "https://api.deepseek.com"):
        self.api_key = api_key
        self.model = model
        self.base_url = base_url
        self.timeout = 120.0

    async def chat_with_tools(
        self,
        messages: list[dict],
        tools: list[dict],
        *,
        temperature: float = 0.1,
        top_p: float = 0.2,
    ) -> dict:
        """Non-streaming call. Returns parsed response dict.

        Response shape:
          - If LLM returns tool_calls: {choices: [{message: {tool_calls: [...]}}]}
          - If LLM returns text:     {choices: [{message: {content: "..."}}]}
        """
        if not self.api_key:
            raise ValueError("DeepSeek API Key 未配置")

        url = f"{self.base_url}/chat/completions"
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "top_p": top_p,
            "frequency_penalty": 0.1,
            "stream": False,
            "tools": tools,
            "tool_choice": "auto",
        }
        _log.info("LLM call model=%s messages=%d tools=%d",
                  self.model, len(messages), len(tools))

        t0 = time.monotonic()
        for attempt in range(3):
            try:
                async with httpx.AsyncClient(timeout=self.timeout) as client:
                    resp = await client.post(url, headers=self._headers(), json=payload)
                break  # success
            except Exception as e:
                elapsed = time.monotonic() - t0
                if attempt < 2:
                    _log.warning("LLM attempt %d/3 failed after %.3fs (%s %s) — retrying",
                                 attempt + 1, elapsed, type(e).__name__, e or "(no detail)")
                    await asyncio.sleep(1.0 * (attempt + 1))
                else:
                    _log.error("LLM request failed after %d attempts (%.3fs): %s %s",
                               attempt + 1, elapsed, type(e).__name__, e or "(no detail)")
                    raise

        elapsed = time.monotonic() - t0
        if resp.status_code != 200:
            text = (await resp.aread())[:500]
            _log.error("LLM HTTP error status=%d elapsed=%.3fs body=%.200s",
                       resp.status_code, elapsed, text)
            raise httpx.HTTPStatusError(
                f"DeepSeek HTTP {resp.status_code}: {text}",
                request=resp.request, response=resp,
            )
        body = await resp.aread()
        _log.info("LLM response status=%d elapsed=%.3fs body_preview=%.200s",
                  resp.status_code, elapsed, body.decode("utf-8", errors="replace")[:200])
        data = json.loads(body)
        usage = data.get("usage", {})
        if usage:
            _log.info("LLM response model=%s elapsed=%.3fs prompt=%d completion=%d total=%d",
                      data.get("model", "?"), elapsed,
                      usage.get("prompt_tokens", 0), usage.get("completion_tokens", 0),
                      usage.get("total_tokens", 0))
        else:
            _log.info("LLM response model=%s elapsed=%.3fs",
                      data.get("model", "?"), elapsed)
        return data

    async def chat_stream(
        self,
        messages: list[dict],
        tools: list[dict],
        *,
        temperature: float = 0.1,
        top_p: float = 0.2,
    ):
        """Streaming call. Yields SSE delta chunks.

        Each chunk is the raw JSON line value from DeepSeek's SSE stream.
        Caller is responsible for accumulating tool_calls/content.
        """
        if not self.api_key:
            raise ValueError("DeepSeek API Key 未配置")

        url = f"{self.base_url}/chat/completions"
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "top_p": top_p,
            "frequency_penalty": 0.1,
            "stream": True,
            "tools": tools,
            "tool_choice": "auto",
        }
        _log.info("LLM stream start model=%s messages=%d tools=%d",
                  self.model, len(messages), len(tools))

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            async with client.stream("POST", url, headers=self._headers(), json=payload) as resp:
                if resp.status_code != 200:
                    text = (await resp.aread())[:500]
                    _log.error("LLM stream HTTP error status=%d body=%.200s",
                               resp.status_code, text)
                    raise httpx.HTTPStatusError(
                        f"DeepSeek HTTP {resp.status_code}: {text}",
                        request=resp.request, response=resp,
                    )
                _log.info("LLM stream connected status=%d", resp.status_code)
                async for line in resp.aiter_lines():
                    if line.startswith("data: "):
                        data = line[6:]
                        if data == "[DONE]":
                            break
                        import json
                        try:
                            yield json.loads(data)
                        except json.JSONDecodeError:
                            continue

    async def simple_chat(self, messages: list[dict], temperature: float = 0.1) -> str:
        """Simple chat without tools. Returns text content."""
        url = f"{self.base_url}/chat/completions"
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "stream": False,
        }
        _log.info("LLM simple_chat model=%s messages=%d", self.model, len(messages))

        t0 = time.monotonic()
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            resp = await client.post(url, headers=self._headers(), json=payload)
            if resp.status_code != 200:
                text = (await resp.aread())[:500]
                _log.error("LLM simple_chat HTTP error status=%d body=%.200s",
                           resp.status_code, text)
                raise httpx.HTTPStatusError(
                    f"DeepSeek HTTP {resp.status_code}: {text}",
                    request=resp.request, response=resp,
                )
            data = resp.json()
            elapsed = time.monotonic() - t0
            usage = data.get("usage", {})
            if usage:
                _log.info("LLM simple_chat done elapsed=%.3fs total_tokens=%d",
                          elapsed, usage.get("total_tokens", 0))
            else:
                _log.info("LLM simple_chat done elapsed=%.3fs", elapsed)
            return data["choices"][0]["message"]["content"]

    def _headers(self) -> dict:
        return {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}",
        }
