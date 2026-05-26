# -*- coding: utf-8 -*-
"""Strategy-specific analysis tool definitions and handlers.

Each strategy can register one or more analysis functions that the LLM
can call during analysis. Tools are appended to the base tool set when
the corresponding strategy is selected.
"""
import time
import numpy as np

from ..services.logger import get_logger

_log = get_logger(__name__)

# ---------------------------------------------------------------------------
# Registry: strategy_id → list of tool definitions
# ---------------------------------------------------------------------------

def get_strategy_tools(tickflow, strategy_ids: list[str]) -> list[dict]:
    """Build tool definitions for the given strategy IDs."""
    handlers = {
        "check_volume_breakout": lambda args: _check_volume_breakout(tickflow, args.get("symbol", "")),
        "check_ma_cross": lambda args: _check_ma_cross(tickflow, args.get("symbol", ""),
                                                       args.get("short_ma", 5), args.get("long_ma", 20)),
        "check_shrink_pullback": lambda args: _check_shrink_pullback(tickflow, args.get("symbol", "")),
        "check_bottom_volume": lambda args: _check_bottom_volume(tickflow, args.get("symbol", "")),
        "check_chan_structure": lambda args: _check_chan_structure(tickflow, args.get("symbol", "")),
    }

    # Strategy-to-tool mapping
    mapping = {
        "volume_breakout": ["check_volume_breakout"],
        "ma_golden_cross": ["check_ma_cross"],
        "shrink_pullback": ["check_shrink_pullback"],
        "bottom_volume": ["check_bottom_volume"],
        "chan_theory": ["check_chan_structure"],
    }

    tool_defs = {
        "check_volume_breakout": {
            "type": "function",
            "function": {
                "name": "check_volume_breakout",
                "description": "检测放量突破形态：计算最新成交量相对于5日/20日均量的倍率，检查价格是否突破MA20/MA60均线。",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "symbol": {"type": "string", "description": "股票代码，如 600519.SH"},
                    },
                    "required": ["symbol"],
                },
            },
            "display_name": "放量突破检测",
        },
        "check_ma_cross": {
            "type": "function",
            "function": {
                "name": "check_ma_cross",
                "description": "检测均线交叉信号（金叉/死叉）：检查短期均线是否上穿/下穿长期均线，以及MACD状态。",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "symbol": {"type": "string", "description": "股票代码，如 600519.SH"},
                        "short_ma": {"type": "integer", "description": "短期均线周期，默认5"},
                        "long_ma": {"type": "integer", "description": "长期均线周期，默认20"},
                    },
                    "required": ["symbol"],
                },
            },
            "display_name": "均线交叉检测",
        },
        "check_shrink_pullback": {
            "type": "function",
            "function": {
                "name": "check_shrink_pullback",
                "description": "检测缩量回踩买点：检查上升趋势中价格回调时成交量是否萎缩，以及是否在MA10/MA20处获得支撑。",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "symbol": {"type": "string", "description": "股票代码，如 600519.SH"},
                    },
                    "required": ["symbol"],
                },
            },
            "display_name": "缩量回踩检测",
        },
        "check_bottom_volume": {
            "type": "function",
            "function": {
                "name": "check_bottom_volume",
                "description": "检测底部放量反转信号：长期下跌后，检查成交量是否异常放大、价格是否企稳收阳。",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "symbol": {"type": "string", "description": "股票代码，如 600519.SH"},
                    },
                    "required": ["symbol"],
                },
            },
            "display_name": "底部放量检测",
        },
        "check_chan_structure": {
            "type": "function",
            "function": {
                "name": "check_chan_structure",
                "description": "缠论结构分析（简化版）：识别分型、笔、线段，判断当前处于上涨/下跌/中枢震荡，检测顶底背驰。",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "symbol": {"type": "string", "description": "股票代码，如 600519.SH"},
                    },
                    "required": ["symbol"],
                },
            },
            "display_name": "缠论结构分析",
        },
    }

    seen = set()
    result = []
    for sid in strategy_ids:
        for tool_name in mapping.get(sid, []):
            if tool_name not in seen and tool_name in tool_defs:
                td = dict(tool_defs[tool_name])
                td["handler"] = handlers[tool_name]
                result.append(td)
                seen.add(tool_name)
    return result


# ---------------------------------------------------------------------------
# Handlers
# ---------------------------------------------------------------------------

def _get_klines_df(tf, symbol: str, period: str = "1d", count: int = 120):
    """Fetch kline data as a pandas DataFrame."""
    try:
        df = tf.klines.get(symbol, period=period, count=count, as_dataframe=True)
        return df
    except Exception as e:
        _log.warning("get_klines failed in strategy tool symbol=%s: %s", symbol, e)
        return None


def _check_volume_breakout(tf, symbol: str) -> dict:
    """Check for volume breakout pattern."""
    if not symbol:
        return {"error": "symbol is required"}
    symbol = symbol.strip().upper()

    df = _get_klines_df(tf, symbol, count=60)
    if df is None or df.empty:
        return {"error": f"未获取到 {symbol} 的K线数据"}

    try:
        latest = df.iloc[-1]
        close_vals = df["close"].values
        vol_vals = df["volume"].values.astype(float)

        latest_close = float(latest["close"])
        latest_vol = float(latest["volume"])

        avg_vol_5 = float(np.mean(vol_vals[-5:]))
        avg_vol_20 = float(np.mean(vol_vals[-20:]))
        vol_ratio_5 = latest_vol / avg_vol_5 if avg_vol_5 > 0 else 0

        ma20 = float(np.mean(close_vals[-20:]))
        ma60 = float(np.mean(close_vals[-60:])) if len(close_vals) >= 60 else None

        above_ma20 = latest_close > ma20
        above_ma60 = latest_close > ma60 if ma60 else None

        pct_change = ((close_vals[-1] - close_vals[-2]) / close_vals[-2]) * 100 if len(close_vals) >= 2 else 0

        # Find recent high (20 days)
        recent_high = float(np.max(close_vals[-20:]))
        high_idx = int(np.argmax(close_vals[-20:]))
        near_high = latest_close >= recent_high * 0.98  # within 2% of high

        is_breakout = vol_ratio_5 > 1.5 and above_ma20 and pct_change > 0 and near_high
        strength = "strong" if (vol_ratio_5 > 2.0 and above_ma60) else "moderate" if is_breakout else "weak"

        return {
            "symbol": symbol,
            "latest_close": round(latest_close, 2),
            "volume_ratio_vs_5d_avg": round(vol_ratio_5, 2),
            "avg_volume_5d": round(avg_vol_5, 0),
            "avg_volume_20d": round(avg_vol_20, 0),
            "ma20": round(ma20, 2),
            "ma60": round(ma60, 2) if ma60 else None,
            "above_ma20": bool(above_ma20),
            "above_ma60": bool(above_ma60) if above_ma60 is not None else None,
            "price_change_pct": round(pct_change, 2),
            "recent_high_20d": round(recent_high, 2),
            "near_recent_high": bool(near_high),
            "signal": "放量突破" if is_breakout else "未满足突破条件",
            "strength": strength,
        }
    except Exception as e:
        _log.error("check_volume_breakout error: %s", e)
        return {"error": f"放量突破检测失败: {e}"}


def _check_ma_cross(tf, symbol: str, short_ma: int = 5, long_ma: int = 20) -> dict:
    """Check for moving average cross signals."""
    if not symbol:
        return {"error": "symbol is required"}
    symbol = symbol.strip().upper()
    if short_ma >= long_ma:
        return {"error": "short_ma must be less than long_ma"}
    if short_ma < 2:
        short_ma = 5

    df = _get_klines_df(tf, symbol, count=max(long_ma + 30, 120))
    if df is None or df.empty:
        return {"error": f"未获取到 {symbol} 的K线数据"}

    try:
        close_vals = df["close"].values.astype(float)
        if len(close_vals) < long_ma + 5:
            return {"error": f"数据不足，需要至少 {long_ma + 5} 条K线"}

        # Calculate MAs
        def _ma(arr, n):
            return np.convolve(arr, np.ones(n) / n, mode="valid")

        short_arr = _ma(close_vals, short_ma)
        long_arr = _ma(close_vals, long_ma)

        # Align lengths (long MA has fewer points)
        offset = long_ma - short_ma
        short_aligned = short_arr[offset:]
        long_aligned = long_arr

        # Check last 3 days for cross
        prev_diff = short_aligned[-3] - long_aligned[-3] if len(short_aligned) >= 3 else None
        curr_diff = short_aligned[-2] - long_aligned[-2] if len(short_aligned) >= 2 else None
        latest_diff = short_aligned[-1] - long_aligned[-1]

        cross_type = None
        cross_day = None
        diffs = [prev_diff, curr_diff, latest_diff]
        for i in range(1, len(diffs)):
            if diffs[i - 1] is not None and diffs[i] is not None:
                if diffs[i - 1] <= 0 and diffs[i] > 0:
                    cross_type = "golden_cross"
                    cross_day = i - len(diffs)  # -2 or -1
                    break
                elif diffs[i - 1] >= 0 and diffs[i] < 0:
                    cross_type = "death_cross"
                    cross_day = i - len(diffs)
                    break

        # Current alignment
        ma_short_val = float(short_aligned[-1])
        ma_long_val = float(long_aligned[-1])

        # MACD check
        ema12 = _ema(close_vals, 12)
        ema26 = _ema(close_vals, 26)
        if ema12 is not None and ema26 is not None:
            dif_line = ema12 - ema26
            dea = _ema_single(dif_line, 9) if len(close_vals) >= 26 else None
            macd_hist = dif_line - dea if dea is not None else None
            macd_golden = dif_line > 0 and dif_line > dea if dea is not None else None
            macd_death = dif_line < 0 and dif_line < dea if dea is not None else None
        else:
            macd_golden = macd_death = None

        latest_close = float(close_vals[-1])
        above_ma = latest_close > ma_long_val

        return {
            "symbol": symbol,
            f"ma{short_ma}": round(ma_short_val, 2),
            f"ma{long_ma}": round(ma_long_val, 2),
            "latest_close": round(latest_close, 2),
            "above_long_ma": bool(above_ma),
            "cross_signal": cross_type or "no_cross",
            "ma_diff_pct": round((ma_short_val - ma_long_val) / ma_long_val * 100, 2),
            "macd_golden_cross": macd_golden,
            "macd_death_cross": macd_death,
            "judgment": _describe_cross(cross_type, macd_golden, macd_death),
        }
    except Exception as e:
        _log.error("check_ma_cross error: %s", e)
        return {"error": f"均线交叉检测失败: {e}"}


def _describe_cross(cross_type, macd_golden, macd_death):
    if cross_type == "golden_cross":
        return "均线金叉信号" + (" + MACD金叉共振（强烈）" if macd_golden else "（需量能确认）")
    elif cross_type == "death_cross":
        return "均线死叉信号" + (" + MACD死叉共振（强烈）" if macd_death else "（需进一步确认）")
    return "无明显均线交叉"


def _check_shrink_pullback(tf, symbol: str) -> dict:
    """Check for shrinking-volume pullback buy signal."""
    if not symbol:
        return {"error": "symbol is required"}
    symbol = symbol.strip().upper()

    df = _get_klines_df(tf, symbol, count=80)
    if df is None or df.empty:
        return {"error": f"未获取到 {symbol} 的K线数据"}

    try:
        close_vals = df["close"].values.astype(float)
        vol_vals = df["volume"].values.astype(float)
        high_vals = df["high"].values.astype(float)
        low_vals = df["low"].values.astype(float)

        if len(close_vals) < 30:
            return {"error": "数据不足，需要至少 30 条K线"}

        # MA slopes for trend direction
        ma20 = float(np.mean(close_vals[-20:]))
        ma10 = float(np.mean(close_vals[-10:]))
        ma20_prev = float(np.mean(close_vals[-40:-20]))
        ma20_slope = (ma20 - ma20_prev) / ma20_prev * 100  # percentage

        # Uptrend check
        is_uptrend = ma20_slope > 0.5 and close_vals[-1] > ma20

        # Recent high and pullback
        recent_high = float(np.max(close_vals[-20:]))
        high_idx = int(np.argmax(close_vals[-20:]))
        pullback_pct = (recent_high - close_vals[-1]) / recent_high * 100

        # Volume shrinkage: compare recent 3 days vs previous 10 days
        recent_vol_avg = float(np.mean(vol_vals[-5:]))
        prior_vol_avg = float(np.mean(vol_vals[-15:-5]))
        vol_shrink_ratio = recent_vol_avg / prior_vol_avg if prior_vol_avg > 0 else 1

        # Support at MA10/MA20
        at_ma10 = abs(close_vals[-1] - ma10) / ma10 * 100 < 2
        at_ma20 = abs(close_vals[-1] - ma20) / ma20 * 100 < 2
        below_ma60 = close_vals[-1] < float(np.mean(close_vals[-60:])) if len(close_vals) >= 60 else False

        # Candle pattern: hammer / doji
        body = abs(float(latest_close := close_vals[-1]) - float(open_val := df["open"].values[-1]))
        lower_shadow = min(float(open_val), latest_close) - float(low_vals[-1])
        upper_shadow = float(high_vals[-1]) - max(float(open_val), latest_close)
        is_hammer = lower_shadow > body * 2 and body > 0
        is_doji = body < (float(high_vals[-1]) - float(low_vals[-1])) * 0.1

        # Judgment
        conditions_met = sum([
            is_uptrend,
            vol_shrink_ratio < 0.8,
            3 <= pullback_pct <= 8,
            at_ma10 or at_ma20,
            not below_ma60,
        ])

        return {
            "symbol": symbol,
            "latest_close": round(latest_close, 2),
            "ma10": round(ma10, 2),
            "ma20": round(ma20, 2),
            "ma20_slope_pct": round(ma20_slope, 2),
            "is_uptrend": bool(is_uptrend),
            "pullback_from_high_pct": round(pullback_pct, 2),
            "recent_high_20d": round(recent_high, 2),
            "volume_shrink_ratio": round(vol_shrink_ratio, 2),
            "at_ma10_support": bool(at_ma10),
            "at_ma20_support": bool(at_ma20),
            "candle_pattern": "hammer" if is_hammer else "doji" if is_doji else "normal",
            "conditions_met": conditions_met,
            "max_conditions": 5,
            "signal": "缩量回踩买点" if conditions_met >= 4 else "条件不足",
        }
    except Exception as e:
        _log.error("check_shrink_pullback error: %s", e)
        return {"error": f"缩量回踩检测失败: {e}"}


def _check_bottom_volume(tf, symbol: str) -> dict:
    """Check for bottom-volume reversal signal."""
    if not symbol:
        return {"error": "symbol is required"}
    symbol = symbol.strip().upper()

    df = _get_klines_df(tf, symbol, count=60)
    if df is None or df.empty:
        return {"error": f"未获取到 {symbol} 的K线数据"}

    try:
        close_vals = df["close"].values.astype(float)
        vol_vals = df["volume"].values.astype(float)
        open_vals = df["open"].values.astype(float)
        low_vals = df["low"].values.astype(float)

        if len(close_vals) < 30:
            return {"error": "数据不足，需要至少 30 条K线"}

        # 1.持续下跌: check price drop from 20-day high
        high_20d = float(np.max(close_vals[-20:]))
        current_low = float(np.min(low_vals[-5:]))
        drop_pct = (high_20d - current_low) / high_20d * 100

        # 2.量能异动
        latest_vol = float(vol_vals[-1])
        avg_vol_5 = float(np.mean(vol_vals[-5:]))
        vol_ratio = latest_vol / avg_vol_5 if avg_vol_5 > 0 else 0

        # Volume quiet period before surge
        prior_vol_avg = float(np.mean(vol_vals[-20:-5]))
        was_quiet = prior_vol_avg < float(np.mean(vol_vals)) * 0.7

        # 3.价格企稳
        latest_close = float(close_vals[-1])
        latest_open = float(open_vals[-1])
        is_bullish = latest_close > latest_open

        # Lower shadow check
        low = float(low_vals[-1])
        body_top = max(latest_close, latest_open)
        body_bot = min(latest_close, latest_open)
        lower_shadow = body_bot - low
        body_size = body_top - body_bot
        has_long_lower_shadow = lower_shadow > body_size * 1.5 and body_size > 0

        conditions_met = sum([
            drop_pct > 15,
            vol_ratio > 3.0,
            is_bullish,
            was_quiet,
            has_long_lower_shadow,
        ])

        return {
            "symbol": symbol,
            "latest_close": round(latest_close, 2),
            "drop_from_20d_high_pct": round(drop_pct, 2),
            "volume_ratio_vs_5d": round(vol_ratio, 2),
            "is_bullish_candle": bool(is_bullish),
            "long_lower_shadow": bool(has_long_lower_shadow),
            "prior_volume_quiet": bool(was_quiet),
            "conditions_met": conditions_met,
            "max_conditions": 5,
            "signal": "底部放量反转信号" if conditions_met >= 4 else "条件不足",
        }
    except Exception as e:
        _log.error("check_bottom_volume error: %s", e)
        return {"error": f"底部放量检测失败: {e}"}


def _check_chan_structure(tf, symbol: str) -> dict:
    """Simplified 缠论 (Chan Theory) structure analysis.

    Identifies fractal tops/bottoms, strokes (笔), and basic中枢
    (center) structure. This is an intentionally simplified implementation.
    """
    if not symbol:
        return {"error": "symbol is required"}
    symbol = symbol.strip().upper()

    df = _get_klines_df(tf, symbol, count=120)
    if df is None or df.empty:
        return {"error": f"未获取到 {symbol} 的K线数据"}

    try:
        high_vals = df["high"].values.astype(float)
        low_vals = df["low"].values.astype(float)
        close_vals = df["close"].values.astype(float)

        if len(high_vals) < 30:
            return {"error": "数据不足，需要至少 30 条K线"}

        # 1.Identify fractal tops and bottoms (simplified: 5-bar fractal)
        tops = []  # (index, price)
        bottoms = []
        for i in range(2, len(high_vals) - 2):
            if high_vals[i] > high_vals[i - 1] and high_vals[i] > high_vals[i - 2] and \
               high_vals[i] > high_vals[i + 1] and high_vals[i] > high_vals[i + 2]:
                tops.append((i, high_vals[i]))
            if low_vals[i] < low_vals[i - 1] and low_vals[i] < low_vals[i - 2] and \
               low_vals[i] < low_vals[i + 1] and low_vals[i] < low_vals[i + 2]:
                bottoms.append((i, low_vals[i]))

        # 2.Simplified stroke detection: alternating tops and bottoms
        strokes = []
        combined = [(idx, "top", price) for idx, price in tops] + \
                   [(idx, "bottom", price) for idx, price in bottoms]
        combined.sort(key=lambda x: x[0])

        # Keep alternating tops and bottoms
        filtered = []
        last_type = None
        for idx, typ, price in combined:
            if typ != last_type:
                filtered.append((idx, typ, price))
                last_type = typ
            elif typ == "top" and price > (filtered[-1][2] if filtered else 0):
                filtered[-1] = (idx, typ, price)
            elif typ == "bottom" and price < (filtered[-1][2] if filtered else 0):
                filtered[-1] = (idx, typ, price)

        # 3.Detect 中枢 (center/consolidation) zones
        # A 中枢 is formed by 3 overlapping strokes
        zones = []
        for i in range(len(filtered) - 4):
            segment = filtered[i:i + 5]
            if segment[0][1] == "bottom" and segment[2][1] == "bottom" and segment[4][1] == "bottom":
                # Upward strokes, check overlap between seg[0]-seg[2]-seg[4]
                zone_high = min(segment[1][2], segment[3][2])  # lower of the two tops
                zone_low = max(segment[0][2], segment[2][2], segment[4][2])  # higher of bottoms
                if zone_high > zone_low:
                    zones.append({
                        "type": "upward_center",
                        "top": round(zone_high, 2),
                        "bottom": round(zone_low, 2),
                        "start_idx": segment[0][0],
                        "end_idx": segment[4][0],
                    })

        # 4.Determine current status
        latest_close = float(close_vals[-1])
        latest_high = float(high_vals[-1])
        latest_low = float(low_vals[-1])

        in_zone = False
        zone_top = zone_bottom = None
        for z in zones:
            if z["start_idx"] <= len(high_vals) - 1 <= z["end_idx"] + 5:
                in_zone = True
                zone_top = z["top"]
                zone_bottom = z["bottom"]
                break

        above_zone = zone_top is not None and latest_close > zone_top
        below_zone = zone_bottom is not None and latest_close < zone_bottom

        # 5.MACD divergence check
        ema12 = _ema(close_vals, 12)
        ema26 = _ema(close_vals, 26)
        divergence = None
        if ema12 is not None and ema26 is not None and len(tops) >= 2 and len(bottoms) >= 2:
            dif = ema12 - ema26
            # Top divergence: price higher, DIF lower
            if len(tops) >= 2:
                last_two_tops = tops[-2:]
                dif_at_tops = [float(dif[idx]) if idx < len(dif) else 0 for idx, _ in last_two_tops]
                if last_two_tops[1][1] > last_two_tops[0][1] and dif_at_tops[1] < dif_at_tops[0]:
                    divergence = "顶背驰"
            # Bottom divergence: price lower, DIF higher
            if len(bottoms) >= 2 and not divergence:
                last_two_bottoms = bottoms[-2:]
                dif_at_bottoms = [float(dif[idx]) if idx < len(dif) else 0 for idx, _ in last_two_bottoms]
                if last_two_bottoms[1][1] < last_two_bottoms[0][1] and dif_at_bottoms[1] > dif_at_bottoms[0]:
                    divergence = "底背驰"

        return {
            "symbol": symbol,
            "latest_close": round(latest_close, 2),
            "fractal_tops_found": len(tops),
            "fractal_bottoms_found": len(bottoms),
            "strokes_detected": len(filtered),
            "centers_found": len(zones),
            "in_consolidation_zone": bool(in_zone),
            "above_zone": bool(above_zone) if zone_top is not None else None,
            "below_zone": bool(below_zone) if zone_bottom is not None else None,
            "divergence": divergence or "无背驰",
            "current_status": "上涨趋势" if (above_zone and not in_zone) else
                             "下跌趋势" if (below_zone and not in_zone) else
                             "中枢震荡",
        }
    except Exception as e:
        _log.error("check_chan_structure error: %s", e)
        return {"error": f"缠论结构分析失败: {e}"}


# ---------------------------------------------------------------------------
# EMA helper
# ---------------------------------------------------------------------------

def _ema(arr: np.ndarray, period: int) -> np.ndarray | None:
    """Calculate exponential moving average."""
    if len(arr) < period:
        return None
    alpha = 2 / (period + 1)
    result = np.zeros(len(arr))
    result[0] = arr[0]
    for i in range(1, len(arr)):
        result[i] = alpha * arr[i] + (1 - alpha) * result[i - 1]
    return result


def _ema_single(arr: np.ndarray, period: int) -> float:
    """Calculate the last value of EMA."""
    if len(arr) < period:
        return float(arr[-1])
    alpha = 2 / (period + 1)
    out = float(arr[0])
    for i in range(1, len(arr)):
        out = alpha * arr[i] + (1 - alpha) * out
    return out
