# -*- coding: utf-8 -*-
"""Agent tool definitions — JSON Schema + async handler for each tool."""
import time
from typing import Any

from ..services.logger import get_logger

_log = get_logger(__name__)

# Each tool is a dict: {name, display_name, description, parameters, handler}


def _make_tools(tickflow, config: dict) -> list[dict]:
    """Build tool list with handlers bound to tickflow instance and config."""

    tools = []

    # ---- search_zhihu ----
    tools.append({
        "type": "function",
        "function": {
            "name": "search_zhihu",
            "description": "搜索知乎站内的股票相关内容，获取知乎用户对特定股票/行业的观点、分析和讨论。",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "搜索关键词，如股票名称、代码或行业话题"},
                    "count": {"type": "integer", "description": "返回条数，默认5，最大10"},
                },
                "required": ["query"],
            },
        },
        "handler": lambda args: _zhihu_search(config, args.get("query", ""), args.get("count", 5)),
        "display_name": "知乎搜索",
    })

    # ---- search_global ----
    tools.append({
        "type": "function",
        "function": {
            "name": "search_global",
            "description": "全网搜索股票相关的最新新闻、公告和资讯。当需要获取站外信息、新闻报道时使用。",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "搜索关键词"},
                    "count": {"type": "integer", "description": "返回条数，默认5，最大10"},
                },
                "required": ["query"],
            },
        },
        "handler": lambda args: _global_search(config, args.get("query", ""), args.get("count", 5)),
        "display_name": "全网搜索",
    })

    # ---- get_klines ----
    tools.append({
        "type": "function",
        "function": {
            "name": "get_klines",
            "description": "获取股票的历史K线数据（OHLCV）。用于技术分析、趋势判断、均线计算等。",
            "parameters": {
                "type": "object",
                "properties": {
                    "symbol": {"type": "string", "description": "股票代码，格式如 600519.SH 或 000001.SZ"},
                    "period": {"type": "string", "description": "周期: 1d(日)/1w(周)/1M(月)/1Q(季)/1Y(年)，默认1d"},
                    "count": {"type": "integer", "description": "数据条数，默认120，最大500"},
                },
                "required": ["symbol"],
            },
        },
        "handler": lambda args: _get_klines(tickflow, args),
        "display_name": "获取K线数据",
    })

    # ---- get_realtime_quote ----
    tools.append({
        "type": "function",
        "function": {
            "name": "get_realtime_quote",
            "description": "获取股票的实时行情（最新价、涨跌幅等）。用于了解当前价格状态。",
            "parameters": {
                "type": "object",
                "properties": {
                    "symbol": {"type": "string", "description": "股票代码，如 600519.SH"},
                },
                "required": ["symbol"],
            },
        },
        "handler": lambda args: _get_quote(tickflow, args.get("symbol", "")),
        "display_name": "获取实时行情",
    })

    # ---- get_instrument_info ----
    tools.append({
        "type": "function",
        "function": {
            "name": "get_instrument_info",
            "description": "获取股票的基本信息（名称、上市日期、总股本等）。用于确认股票代码和了解基本面。",
            "parameters": {
                "type": "object",
                "properties": {
                    "symbol": {"type": "string", "description": "股票代码，如 600519.SH"},
                },
                "required": ["symbol"],
            },
        },
        "handler": lambda args: _get_instrument(tickflow, args.get("symbol", "")),
        "display_name": "获取标的信息",
    })

    return tools


# ---------------------------------------------------------------------------
# Tool handlers (synchronous wrappers, called via asyncio.to_thread)
# ---------------------------------------------------------------------------

def _zhihu_search(config: dict, query: str, count: int) -> dict:
    token = config.get("zhihu_access_secret", "")
    if not token:
        _log.warning("zhihu_search no token")
        return {"error": "知乎搜索未配置 (缺少 zhihu_access_secret)", "retriable": False}
    _log.info("zhihu_search query=%s count=%d", query, count)
    start = time.time()
    try:
        from ..services.zhihu_search import search_zhihu
        data = search_zhihu(query, min(count, 10), token=token)
        if data is None:
            _log.warning("zhihu_search failed query=%s", query)
            return {"error": "知乎搜索失败（认证/频率限制/超时）", "retriable": False}
        items = data.get("Items", [])
        results = []
        for item in items:
            results.append({
                "title": item.get("Title", ""),
                "type": item.get("ContentType", ""),
                "summary": (item.get("ContentText", "") or "")[:300],
                "author": item.get("AuthorName", ""),
                "votes": item.get("VoteUpCount", 0),
                "url": item.get("Url", ""),
            })
        elapsed = time.time() - start
        _log.info("zhihu_search done query=%s hits=%d %.3fs", query, len(results), elapsed)
        return {"results": results, "count": len(results)}
    except Exception as e:
        _log.error("zhihu_search exception query=%s %s", query, e)
        return {"error": str(e), "retriable": True}


def _global_search(config: dict, query: str, count: int) -> dict:
    token = config.get("zhihu_access_secret", "")
    if not token:
        _log.warning("global_search no token")
        return {"error": "全网搜索未配置 (缺少 zhihu_access_secret)", "retriable": False}
    _log.info("global_search query=%s count=%d", query, count)
    start = time.time()
    try:
        from ..services.zhihu_search import search_global
        data = search_global(query, min(count, 10), token=token)
        if data is None:
            _log.warning("global_search failed query=%s", query)
            return {"error": "全网搜索失败", "retriable": False}
        items = data.get("Items", [])
        results = []
        for item in items:
            results.append({
                "title": item.get("Title", ""),
                "type": item.get("ContentType", ""),
                "summary": (item.get("ContentText", "") or "")[:300],
                "author": item.get("AuthorName", ""),
                "url": item.get("Url", ""),
            })
        elapsed = time.time() - start
        _log.info("global_search done query=%s hits=%d %.3fs", query, len(results), elapsed)
        return {"results": results, "count": len(results)}
    except Exception as e:
        _log.error("global_search exception query=%s %s", query, e)
        return {"error": str(e), "retriable": True}


def _get_klines(tf, args: dict) -> dict:
    symbol = args.get("symbol", "").strip().upper()
    if not symbol:
        return {"error": "symbol is required", "retriable": False}
    period = args.get("period", "1d")
    count = max(1, min(int(args.get("count", 120)), 500))
    valid = {"1d", "1w", "1M", "1Q", "1Y"}
    if period not in valid:
        period = "1d"
    _log.info("get_klines symbol=%s period=%s count=%d", symbol, period, count)
    start = time.time()
    try:
        df = tf.klines.get(symbol, period=period, count=count, as_dataframe=True)
        if df.empty:
            _log.warning("get_klines empty symbol=%s period=%s", symbol, period)
            return {"error": f"未找到 {symbol} 的K线数据", "retriable": False}
        records = df.tail(30).to_dict(orient="records")
        for r in records:
            if "timestamp" in r:
                r["timestamp"] = int(r["timestamp"])
        latest = records[-1]
        elapsed = time.time() - start
        _log.info("get_klines done symbol=%s period=%s total=%d %.3fs", symbol, period, len(df), elapsed)
        return {
            "symbol": symbol,
            "period": period,
            "total_count": len(df),
            "latest": {
                "date": str(latest.get("trade_date", "")),
                "open": float(latest["open"]),
                "high": float(latest["high"]),
                "low": float(latest["low"]),
                "close": float(latest["close"]),
                "volume": int(latest.get("volume", 0)),
            },
            "records_count": len(records),
        }
    except Exception as e:
        _log.error("get_klines exception symbol=%s period=%s %s", symbol, period, e)
        return {"error": f"获取K线数据失败: {e}", "retriable": True}


def _get_quote(tf, symbol: str) -> dict:
    symbol = symbol.strip().upper()
    if not symbol:
        return {"error": "symbol is required", "retriable": False}
    _log.info("get_realtime_quote symbol=%s", symbol)
    start = time.time()
    try:
        info = tf.instruments.batch(symbols=[symbol])
        if not info:
            _log.warning("get_realtime_quote not found symbol=%s", symbol)
            return {"error": f"未找到 {symbol}", "retriable": False}
        item = info[0]
        name = item.get("name", symbol)
        # Try to get latest kline for price
        df = tf.klines.get(symbol, period="1d", count=2, as_dataframe=True)
        if df.empty:
            return {"symbol": symbol, "name": name, "note": "暂无行情数据"}
        row = df.iloc[-1]
        prev = df.iloc[-2] if len(df) >= 2 else row
        change_pct = float((row["close"] - prev["close"]) / prev["close"] * 100) if prev["close"] != 0 else 0
        elapsed = time.time() - start
        _log.info("get_realtime_quote done symbol=%s name=%s price=%s %.3fs", symbol, name, row["close"], elapsed)
        return {
            "symbol": symbol,
            "name": name,
            "price": float(row["close"]),
            "open": float(row["open"]),
            "high": float(row["high"]),
            "low": float(row["low"]),
            "volume": int(row.get("volume", 0)),
            "change_pct": round(change_pct, 2),
        }
    except Exception as e:
        _log.error("get_realtime_quote exception symbol=%s %s", symbol, e)
        return {"error": f"获取行情失败: {e}", "retriable": True}


def _get_instrument(tf, symbol: str) -> dict:
    symbol = symbol.strip().upper()
    if not symbol:
        return {"error": "symbol is required", "retriable": False}
    _log.info("get_instrument_info symbol=%s", symbol)
    start = time.time()
    try:
        info = tf.instruments.batch(symbols=[symbol])
        if not info:
            _log.warning("get_instrument_info not found symbol=%s", symbol)
            return {"error": f"未找到 {symbol}", "retriable": False}
        item = info[0]
        elapsed = time.time() - start
        _log.info("get_instrument_info done symbol=%s name=%s %.3fs", symbol, item.get("name", ""), elapsed)
        return {
            "symbol": symbol,
            "name": item.get("name", ""),
            "type": item.get("type", ""),
            "exchange": item.get("exchange", ""),
        }
    except Exception as e:
        _log.error("get_instrument_info exception symbol=%s %s", symbol, e)
        return {"error": f"获取标的信息失败: {e}", "retriable": True}
