# -*- coding: utf-8 -*-
"""Action registry — single source of truth for user action → API mapping."""

ACTIONS = {
    "chat.send": {"api": "POST /api/chat/stream", "internal": ["agent loop", "tools"]},
    "chat.summary": {"api": "POST /api/chat/summarize"},
    "deep.analysis": {"api": "POST /api/chat/deep-analysis", "internal": ["agent loop", "tools"]},
    "stock.klines": {"api": "GET /api/stock/klines"},
    "session.list": {"api": "GET /api/chat/sessions"},
    "session.delete": {"api": "DELETE /api/chat/sessions/{id}"},
    "config.load": {"api": "GET /api/config"},
    "config.save": {"api": "POST /api/config"},
}


def parse_action_id(action_id: str) -> dict:
    """Parse action_id into components."""
    parts = action_id.split(".")
    if len(parts) >= 4:
        return {
            "action": f"{parts[0]}.{parts[1]}",
            "domain": parts[0],
            "operation": parts[1],
            "timestamp": int(parts[2]),
            "rand": parts[3],
        }
    return {"action": action_id}
