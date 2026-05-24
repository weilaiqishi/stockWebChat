# -*- coding: utf-8 -*-
"""Context-aware logging — propagates request_id + action_id via contextvars."""
import contextvars
import logging
import uuid

req_id_ctx = contextvars.ContextVar("request_id", default="")
action_id_ctx = contextvars.ContextVar("action_id", default="")


def gen_req_id() -> str:
    return f"req_{uuid.uuid4().hex[:8]}"


class ContextLogger(logging.LoggerAdapter):
    """LoggerAdapter that auto-injects request_id/action_id from contextvars."""

    def process(self, msg, kwargs):
        rid = req_id_ctx.get()
        aid = action_id_ctx.get()
        parts = []
        if rid:
            parts.append(f"[{rid}]")
        if aid:
            # shorten: chat.send.1745400000.a1b2 → [chat.send.a1b2]
            short = _short_action_id(aid)
            parts.append(f"[{short}]")
        prefix = " ".join(parts)
        return f"{prefix} {msg}" if prefix else msg, kwargs


def _short_action_id(aid: str) -> str:
    """chat.send.1745400000.a1b2 → chat.send.a1b2"""
    parts = aid.split(".")
    if len(parts) >= 4:
        return f"{parts[0]}.{parts[1]}.{parts[-1]}"
    return aid


def get_logger(name: str) -> ContextLogger:
    logger = logging.getLogger(name)
    return ContextLogger(logger, {})


def setup_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        force=True,
    )
