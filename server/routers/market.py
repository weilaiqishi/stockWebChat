# -*- coding: utf-8 -*-
"""Stock market data endpoints — K-line + instrument info from tickflow."""
import datetime, calendar
from fastapi import APIRouter, HTTPException, Query

from ..app import get_tickflow, normalize_code
from ..services.logger import get_logger

router = APIRouter(prefix="/api/stock", tags=["market"])
_log = get_logger(__name__)


@router.get("/klines")
async def get_stock_klines(
    symbol: str = Query(..., description="股票代码，如 600000.SH"),
    period: str = Query("1d", description="K线周期: 1d, 1w, 1M, 1Q, 1Y"),
    count: int = Query(100, description="数据条数，最大1000"),
    start_time: int | None = Query(None, description="起始时间戳(毫秒)，用于增量加载历史数据"),
    end_time: int | None = Query(None, description="结束时间戳(毫秒)，用于增量加载历史数据"),
    start_date: str | None = Query(None, description="起始日期(YYYY-MM-DD)，LLM 输出 chart_specs 使用"),
    end_date: str | None = Query(None, description="结束日期(YYYY-MM-DD)，LLM 输出 chart_specs 使用"),
):
    """Get K-line data for chart rendering. Supports count-based, time-range, and date-range queries."""
    tf = get_tickflow()
    symbol = normalize_code(symbol)
    count = max(1, min(count, 1000))
    valid_periods = {"1d", "1w", "1M", "1Q", "1Y"}
    if period not in valid_periods:
        raise HTTPException(status_code=400, detail=f"Invalid period. Must be one of: {valid_periods}")

    _log.info("stock.klines symbol=%s period=%s count=%d start_date=%s end_date=%s",
              symbol, period, count, start_date or "", end_date or "")

    _date_to_ts = lambda d: int(datetime.datetime.strptime(d, "%Y-%m-%d").timestamp() * 1000)

    # Build tickflow params: start_date/end_date take precedence for LLM-facing API
    params: dict = {"symbol": symbol, "period": period, "as_dataframe": True}
    if start_date is not None:
        params["start_time"] = _date_to_ts(start_date)
    if end_date is not None:
        # end_date = end of that day
        dt = datetime.datetime.strptime(end_date, "%Y-%m-%d")
        params["end_time"] = int(dt.replace(hour=23, minute=59, second=59).timestamp() * 1000)
    if start_time is not None:
        params["start_time"] = start_time
    if end_time is not None:
        params["end_time"] = end_time
    # Always pass count to avoid tickflow default limits
    params["count"] = count

    import time
    start_ts = time.monotonic()
    try:
        df = tf.klines.get(**params)
        records = df.to_dict(orient="records")
        for r in records:
            if "timestamp" in r:
                r["timestamp"] = int(r["timestamp"])
        elapsed = time.monotonic() - start_ts
        _log.info("stock.klines done %s %s count=%d elapsed=%.3fs", symbol, period, len(records), elapsed)
        return {"data": records, "count": len(records)}
    except Exception as e:
        elapsed = time.monotonic() - start_ts
        _log.error("stock.klines failed %s %s %.3fs %s", symbol, period, elapsed, e)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/instrument")
async def get_stock_instrument(
    symbol: str = Query(..., description="股票代码，如 600000.SH"),
):
    """Get stock instrument info."""
    tf = get_tickflow()
    symbol = normalize_code(symbol)
    try:
        info = tf.instruments.batch(symbols=[symbol])
        if not info:
            raise HTTPException(status_code=404, detail="Instrument not found")
        return {"data": info[0]}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
