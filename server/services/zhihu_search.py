# -*- coding: utf-8 -*-
"""Zhihu Open Platform search API — zhihu_search + global_search.

Supports both file-based token loading and explicit token parameter.
"""
import time
from typing import Optional

import httpx

from .logger import get_logger

_log = get_logger(__name__)


def _get_token() -> str:
    """Load Zhihu access secret from config.json (fallback)."""
    import json
    from pathlib import Path
    config_path = Path(__file__).resolve().parents[2] / "config.json"
    try:
        cfg = json.loads(config_path.read_text("utf-8"))
        return cfg.get("zhihu_access_secret", "")
    except Exception:
        return ""


def search_zhihu(query: str, count: int = 10,
                 token: Optional[str] = None) -> Optional[dict]:
    """Search Zhihu for stock-related content via Open Platform API.

    Args:
        query: Search keywords.
        count: Max results (max 10).
        token: Explicit access token. If not provided, reads from config.json.

    Returns decoded response Data dict on success, None on any failure.
    """
    token = token or _get_token()
    if not token:
        return None

    try:
        resp = httpx.get(
            "https://developer.zhihu.com/api/v1/content/zhihu_search",
            params={"Query": query, "Count": min(count, 10)},
            headers={
                "Authorization": f"Bearer {token}",
                "X-Request-Timestamp": str(int(time.time())),
                "Content-Type": "application/json",
            },
            timeout=10.0,
        )
        data = resp.json()
        code = data.get("Code", -1)
        if code == 30001:
            _log.warning("zhihu_search rate limited query=%s", query)
            return None
        if code == 20001:
            _log.error("zhihu_search auth failed")
            return None
        if code != 0:
            _log.warning("zhihu_search api error query=%s code=%s msg=%s",
                         query, code, data.get('Message', ''))
            return None
        return data.get("Data", {})
    except httpx.TimeoutException:
        _log.warning("zhihu_search timeout query=%s", query)
        return None
    except Exception as e:
        _log.error("zhihu_search exception query=%s %s", query, e)
        return None


def search_global(query: str, count: int = 10,
                  filter_str: str = "", search_db: str = "all",
                  token: Optional[str] = None) -> Optional[dict]:
    """Search global web via Zhihu Open Platform.

    Args:
        query: Search keywords.
        count: Max results (max 20).
        filter_str: Optional filter.
        search_db: Search database scope.
        token: Explicit access token. If not provided, reads from config.json.

    Returns decoded response Data dict on success, None on any failure.
    """
    token = token or _get_token()
    if not token:
        return None

    params = {"Query": query, "Count": min(count, 20)}
    if filter_str:
        params["Filter"] = filter_str
    if search_db:
        params["SearchDB"] = search_db

    try:
        resp = httpx.get(
            "https://developer.zhihu.com/api/v1/content/global_search",
            params=params,
            headers={
                "Authorization": f"Bearer {token}",
                "X-Request-Timestamp": str(int(time.time())),
                "Content-Type": "application/json",
            },
            timeout=15.0,
        )
        data = resp.json()
        code = data.get("Code", -1)
        if code == 30001:
            _log.warning("global_search rate limited query=%s", query)
            return None
        if code == 20001:
            _log.error("global_search auth failed")
            return None
        if code != 0:
            _log.warning("global_search api error query=%s code=%s", query, code)
            return None
        return data.get("Data", {})
    except httpx.TimeoutException:
        _log.warning("global_search timeout query=%s", query)
        return None
    except Exception as e:
        _log.error("global_search exception query=%s %s", query, e)
        return None
