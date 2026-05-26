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

    # ---- get_market_indices ----
    tools.append({
        "type": "function",
        "function": {
            "name": "get_market_indices",
            "description": "获取主要市场指数最新行情，包括A股（上证、深证、创业板、沪深300）、港股（恒生）、美股（标普500、纳斯达克）的主要指数数据。",
            "parameters": {
                "type": "object",
                "properties": {
                    "exchange": {
                        "type": "string",
                        "enum": ["A", "HK", "US"],
                        "description": "市场筛选: A=沪深, HK=港股, US=美股。不传则返回全部市场指数。",
                    },
                },
            },
        },
        "handler": lambda args: _get_market_indices(tickflow, args.get("exchange")),
        "display_name": "获取大盘指数",
    })

    # ---- get_sector_rankings ----
    tools.append({
        "type": "function",
        "function": {
            "name": "get_sector_rankings",
            "description": "获取A股行业板块涨跌幅排名。默认返回涨幅前10名，可指定排序方式和返回条数。",
            "parameters": {
                "type": "object",
                "properties": {
                    "top_n": {"type": "integer", "description": "返回条数，默认10，最大30"},
                    "order": {"type": "string", "enum": ["desc", "asc"], "description": "排序: desc=涨幅降序(默认), asc=涨幅升序"},
                },
            },
        },
        "handler": lambda args: _get_sector_rankings(tickflow, args.get("top_n", 10), args.get("order", "desc")),
        "display_name": "行业板块排名",
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


# ---------------------------------------------------------------------------
# Market indices
# ---------------------------------------------------------------------------

INDEX_MAP = {
    "000001.SH": ("上证指数", "A"),
    "399001.SZ": ("深证成指", "A"),
    "399006.SZ": ("创业板指", "A"),
    "000300.SH": ("沪深300", "A"),
    "000688.SH": ("科创50", "A"),
    "HSI": ("恒生指数", "HK"),
    "HSCEI": ("恒生国企指数", "HK"),
    "HSTECH": ("恒生科技指数", "HK"),
    "SPX": ("标普500", "US"),
    "IXIC": ("纳斯达克", "US"),
    "DJI": ("道琼斯", "US"),
}


def _get_market_indices(tf, exchange: str | None = None) -> dict:
    """Get latest quotes for major market indices."""
    _log.info("get_market_indices exchange=%s", exchange or "all")
    start = time.time()
    results = []
    for symbol, (name, market) in INDEX_MAP.items():
        if exchange and market != exchange:
            continue
        try:
            info = tf.instruments.batch(symbols=[symbol])
            display_name = info[0].get("name", name) if info else name
            df = tf.klines.get(symbol, period="1d", count=2, as_dataframe=True)
            if not df.empty:
                row = df.iloc[-1]
                prev = df.iloc[-2] if len(df) >= 2 else row
                change_pct = float((row["close"] - prev["close"]) / prev["close"] * 100) if prev["close"] != 0 else 0
                results.append({
                    "symbol": symbol,
                    "name": display_name,
                    "price": float(row["close"]),
                    "change_pct": round(change_pct, 2),
                    "exchange": market,
                })
            else:
                results.append({"symbol": symbol, "name": display_name, "price": None, "change_pct": None, "exchange": market})
        except Exception as e:
            _log.debug("get_market_indices skip %s: %s", symbol, e)
            results.append({"symbol": symbol, "name": name, "price": None, "change_pct": None, "exchange": market, "note": str(e)[:60]})

    elapsed = time.time() - start
    _log.info("get_market_indices done indices=%d %.3fs", len(results), elapsed)
    return {"indices": results, "count": len(results)}


# ---------------------------------------------------------------------------
# Sector rankings
# ---------------------------------------------------------------------------

def _get_sector_rankings(tf, top_n: int = 10, order: str = "desc") -> dict:
    """Get A-share industry sector rankings.

    Uses akshare as data source (tickflow sector API TBD).
    """
    top_n = max(1, min(int(top_n), 30))
    order = order if order in ("desc", "asc") else "desc"
    _log.info("get_sector_rankings top_n=%d order=%s", top_n, order)
    start = time.time()
    try:
        import akshare as ak
        df = ak.stock_board_industry_name_em()
        if df.empty:
            return {"error": "板块数据为空", "retriable": False}
        change_col = "涨跌幅"
        if change_col not in df.columns:
            # Try to find the change column
            candidates = [c for c in df.columns if "幅" in c or "change" in c.lower()]
            if candidates:
                change_col = candidates[0]
            else:
                return {"error": f"无法识别板块涨跌幅列，可用列: {list(df.columns)}", "retriable": False}
        sorted_df = df.sort_values(change_col, ascending=(order == "asc"))
        results = []
        for _, row in sorted_df.head(top_n).iterrows():
            results.append({
                "sector_name": str(row.get("板块名称", row.get("name", ""))),
                "change_pct": round(float(row.get(change_col, 0)), 2),
            })
        elapsed = time.time() - start
        _log.info("get_sector_rankings done sectors=%d %.3fs", len(results), elapsed)
        return {"sectors": results, "count": len(results)}
    except ImportError:
        return {"error": "板块数据需要安装 akshare: pip install akshare", "retriable": False}
    except Exception as e:
        _log.error("get_sector_rankings exception: %s", e)
        return {"error": f"获取板块排名失败: {e}", "retriable": True}
