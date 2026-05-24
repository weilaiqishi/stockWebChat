# -*- coding: utf-8 -*-
"""Multi-turn conversation session management (in-memory, v1)."""
import uuid
import time
from typing import Optional


class ConversationManager:
    def __init__(self):
        self._sessions: dict[str, dict] = {}

    def create_session(self, title: str = "") -> str:
        sid = uuid.uuid4().hex[:12]
        self._sessions[sid] = {
            "id": sid,
            "title": title or f"对话 {len(self._sessions) + 1}",
            "messages": [],
            "created_at": time.time(),
        }
        return sid

    def add_message(self, session_id: str, role: str, content: str) -> None:
        if session_id not in self._sessions:
            return
        self._sessions[session_id]["messages"].append({
            "role": role,
            "content": content,
        })

    def get_history(self, session_id: str) -> list[dict]:
        if session_id not in self._sessions:
            return []
        return list(self._sessions[session_id]["messages"])

    def delete_session(self, session_id: str) -> None:
        self._sessions.pop(session_id, None)

    def list_sessions(self) -> list[dict]:
        return sorted(
            [
                {"id": s["id"], "title": s["title"], "created_at": s["created_at"],
                 "msg_count": len(s["messages"])}
                for s in self._sessions.values()
            ],
            key=lambda x: x["created_at"],
            reverse=True,
        )

    def has_session(self, session_id: str) -> bool:
        return session_id in self._sessions

    async def summarize(self, session_id: str,
                        deepseek_api_key: str,
                        deepseek_model: str = "deepseek-v4-flash",
                        deepseek_base_url: str = "https://api.deepseek.com") -> str:
        """Summarize the conversation using LLM."""
        history = self.get_history(session_id)
        if not history:
            return "没有对话内容可总结。"

        # Build summary prompt
        conversation_text = ""
        for msg in history:
            role = "用户" if msg["role"] == "user" else "助手" if msg["role"] == "assistant" else msg["role"]
            content = (msg["content"] or "")[:500]
            conversation_text += f"{role}: {content}\n"

        from .client_ext import LLMClient
        client = LLMClient(
            api_key=deepseek_api_key,
            model=deepseek_model,
            base_url=deepseek_base_url,
        )
        prompt = f"""请总结以下股票分析对话的核心内容，包括：
1. 讨论的主要股票/标的
2. 关键分析观点和结论
3. 使用的分析策略（如有）

对话内容：
{conversation_text}

请用简洁的中文总结（200字以内）。"""

        return await client.simple_chat([{"role": "user", "content": prompt}])
