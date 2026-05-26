# Stock Web Chat — CLAUDE.md

## Project Overview

AI Agent 多轮对话股票分析系统。用户通过自然语言问股，Agent 自动调用工具获取数据（K线、行情、知乎、全网搜索、大盘指数、板块排名），在对话中渲染走势图。

支持分析维度快捷指令（告诉 AI 侧重分析什么）和策略分析方法论（预设分析框架 + 策略专用分析工具）。

## Tech Stack

- **Backend**: Python 3.10+ / FastAPI / uv / DeepSeek API / tickflow (免费行情) / akshare (板块数据)
- **Frontend**: Vue 3 Composition API / TypeScript 5.9 strict / Vite 8 / Pinia / Tailwind 3.4 / shadcn-vue / lightweight-charts 5
- **Infra**: Docker multi-stage build / GitHub Actions
- **Package managers**: uv (Python) / pnpm (frontend)

## Commands

```bash
# Backend
uv sync                          # install dependencies
uv run python main.py            # start dev server on :8978 (API + SPA)

# Frontend (hot-reload dev mode)
cd client && pnpm dev            # :5173, proxies /api → :8978

# Build
cd client && pnpm build          # outputs to client/dist/

# Docker
docker compose up -d
```

## Project Structure

```
stockWebChat/
├── main.py                      # uvicorn entry: server.app
├── pyproject.toml               # Python deps (incl. pyyaml, akshare)
├── Dockerfile / docker-compose.yml
├── config.example.json
├── CLAUDE.md                    # ← 本文档

├── server/
│   ├── app.py                   # FastAPI factory + CORS + singletons
│   ├── config_manager.py        # config.json CRUD + validation
│   ├── routers/
│   │   ├── chat.py              # POST /api/chat/stream (SSE), /summarize, /deep-analysis
│   │   ├── config.py            # GET/POST /api/config
│   │   └── market.py            # GET /api/stock/klines, /api/stock/instrument
│   └── agent/
│       ├── runner.py            # ReAct loop (max 10 steps, 120s) + strategy tool injection
│       ├── tools.py             # 7 base tools (search, klines, quote, info, indices, sectors)
│       ├── strategy_tools.py    # 5 strategy-specific analysis tools
│       ├── client_ext.py        # LLMClient: DeepSeek chat + streaming
│       └── conversation.py      # In-memory session store

├── client/src/
│   ├── main.ts / App.vue
│   ├── router/index.ts          # /chat, /settings
│   ├── stores/
│   │   ├── chatStore.ts         # SSE streaming + messages + sessions (supports analysisDimensions)
│   │   └── configStore.ts       # Config state
│   ├── views/
│   │   ├── ChatView.vue         # Main chat UI (AnalysisChips + StrategyEditor embedded)
│   │   └── SettingsView.vue
│   └── components/
│       ├── StockChart.vue       # lightweight-charts K线
│       ├── ChatMessage.vue      # Message bubble + charts + thinking
│       ├── SessionSidebar.vue
│       ├── ConfigForm.vue
│       ├── AnalysisChips.vue    # 分析维度快捷指令芯片 (4/6 chips)
│       ├── StrategyEditor.vue   # 策略选择器
│       └── ui/                  # shadcn-vue primitives

└── strategies/                  # 16 个策略定义 YAML 文件
    ├── bull_trend.yaml          # 多头趋势跟踪
    ├── volume_breakout.yaml     # 放量突破
    ├── shrink_pullback.yaml     # 缩量回踩
    ├── risk_stop.yaml           # 风险止损
    ├── ma_golden_cross.yaml     # 均线金叉
    ├── chan_theory.yaml         # 缠论
    ├── wave_theory.yaml         # 波浪理论
    ├── event_driven.yaml        # 事件驱动
    ├── hot_theme.yaml           # 热点题材
    ├── growth_quality.yaml      # 成长质量
    ├── expectation_repricing.yaml # 预期重估
    ├── box_oscillation.yaml     # 箱体震荡
    ├── dragon_head.yaml         # 龙头策略
    ├── emotion_cycle.yaml       # 情绪周期
    ├── one_yang_three_yin.yaml  # 一阳夹三阴
    └── bottom_volume.yaml       # 底部放量
```

## Conventions

### Frontend

- All components use `<script setup lang="ts">` — no Options API
- PascalCase multi-word component names
- State: Pinia composition stores only
- Styling: Tailwind utility classes
- `@/` path alias → `client/src/`
- No unused-var enforcement (TS strict but noUnusedLocals=false)

### Backend

- All Python files: `# -*- coding: utf-8 -*-`
- Router prefixes: `/api/config`, `/api/chat`, `/api/stock`
- Tool handlers are synchronous, dispatched via `asyncio.to_thread`
- No ORM — sessions in-memory, Feishu optional
- `get_tickflow()` singleton via `server/app.py`

### SSE Event Protocol

SSE events emitted by `runner.py` via progress_callback:

```
type: thinking          → { step, message }
type: tool_start        → { tool, display_name, args }
type: tool_done         → { tool, display_name, summary }
type: done              → { content, chart_specs, steps, session_id }
```

Frontend consumes via `ReadableStream` in `chatStore.sendMessage()`.

## Analysis System (重构模块)

### 分析维度快捷指令 (AnalysisChips)

输入框上方显示一组 toggle 芯片，告诉 AI 侧重分析什么维度。

**当前芯片 (4/6):**

| 芯片 | context 值 | 注入效果 |
|------|-----------|---------|
| `📊 行情` | `quote` | 优先查实时行情 + K线 + 标的信息 |
| `📰 公告` | `news` | 优先搜索新闻/公告/舆情 |
| `📈 技术` | `technical` | 综合技术指标分析 + K线形态 |
| `🏭 板块` | `sector` | 分析所属板块表现 + 排名 |

**待补全 (2):**

| 芯片 | context 值 | 注入效果 |
|------|-----------|---------|
| `💰 资金` | `capital` | 分析主力资金流向（预留，工具就绪后生效）|
| `📋 完整` | `full` | 全维度无侧重分析 |

实现文件: [AnalysisChips.vue](client/src/components/AnalysisChips.vue)

### 轻量路由逻辑

在 `ChatRequest` 增加 `analysis_dimensions: Optional[list[str]]` 字段，后端按以下逻辑路由:

```
IF analysis_dimensions 非空 OR strategy_ids 非空:
    注入维度 prompt + 策略 prompt
    注册策略特有工具（如果有）
    走完整 ReAct 循环（所有工具可用）
ELSE:
    第一轮 LLM 调用：只给 2 个工具（get_realtime_quote + get_klines）
        IF LLM 返回 tool_calls:
            走完整 ReAct 循环（全工具可用）
        ELSE:
            直接返回 LLM 文本回复（纯聊天，零 Agent 开销）
```

实现文件: [chat.py](server/routers/chat.py) — `_build_system_message()` + `is_lightweight` 分支

### 策略系统

#### 策略定义 YAML

每个策略独立 YAML 文件在 `strategies/` 目录，由 `server/services/strategies.py` 加载:

```yaml
name: volume_breakout
display_name: 放量突破
category: trend
description: 检测放量突破阻力位信号
instructions: |
  **放量突破策略**
  ...
```

`strategies.load_strategies()` 返回 `[{id, name, category, instructions, description, required_tools}]`。

#### 策略分析工具 (strategy_tools.py)

策略不只是 prompt 注入，还可以注册专用分析函数。注册在 `server/agent/strategy_tools.py`:

| 工具 | 绑定策略 | 功能 |
|------|---------|------|
| `check_volume_breakout` | 放量突破 | 量比计算、均线突破检测、强度评估 |
| `check_ma_cross` | 均线金叉 | 金叉/死叉检测、MACD 共振、多周期 MA 计算 |
| `check_shrink_pullback` | 缩量回踩 | 趋势斜率、回调幅度、缩量比、支撑位检测 |
| `check_bottom_volume` | 底部放量 | 跌幅计算、量比检测、阳线确认、下影线识别 |
| `check_chan_structure` | 缠论 | 分型识别、笔/段检测、中枢判定、背驰判断 |

策略工具自动注入: `runner.py` 在 `run_agent_loop()` 接受 `strategy_ids` 参数，调用 `get_strategy_tools()` 追加工具到 ReAct 循环。

## Agent / Tool System

### ReAct Loop (`runner.py`)

```
LLM(call tools?) → [tool_calls] → execute → append results → loop
            ↘ [final answer] → parse chart_specs → return
```

- Max 10 steps, wall clock 120s budget
- Tool results cached by `tool_name:json_args` key within one turn
- Chart specs extracted from LLM's markdown by regex: ` ```chart_specs\n[...]\n``` `
- `strategy_ids` 参数 → 自动追加策略专用工具到工具集

### Tool Definitions (`tools.py` + `strategy_tools.py`)

Each tool = `{name, display_name, description, parameters(JSON Schema), handler}`.

**7 个基础工具:**

| Tool | Data Source | Description |
|------|-------------|-------------|
| `search_zhihu` | Zhihu Open API | 知乎站内搜索 |
| `search_global` | Zhihu Open API | 全网搜索 |
| `get_klines` | tickflow | OHLCV 历史K线 |
| `get_realtime_quote` | tickflow | 实时行情 |
| `get_instrument_info` | tickflow | 标的信息 |
| `get_market_indices` | tickflow | 大盘指数 (A/港/美股 11 个指数) |
| `get_sector_rankings` | akshare | A 股行业板块涨跌幅排名 |

**5 个策略工具** (通过策略选择触发注入):

| Tool | Strategy | Data Source |
|------|----------|-------------|
| `check_volume_breakout` | volume_breakout | tickflow |
| `check_ma_cross` | ma_golden_cross | tickflow |
| `check_shrink_pullback` | shrink_pullback | tickflow |
| `check_bottom_volume` | bottom_volume | tickflow |
| `check_chan_structure` | chan_theory | tickflow |

### 大盘指数映射 (`tools.py` INDEX_MAP)

| 代码 | 名称 | 市场 |
|------|------|------|
| 000001.SH | 上证指数 | A |
| 399001.SZ | 深证成指 | A |
| 399006.SZ | 创业板指 | A |
| 000300.SH | 沪深300 | A |
| 000688.SH | 科创50 | A |
| HSI | 恒生指数 | HK |
| HSCEI | 恒生国企指数 | HK |
| HSTECH | 恒生科技指数 | HK |
| SPX | 标普500 | US |
| IXIC | 纳斯达克 | US |
| DJI | 道琼斯 | US |

### System Prompt (`chat.py`)

`_build_system_message(config, strategy_ids, analysis_dimensions)` 组装 system prompt:

1. 基础 prompt（工具列表、分析规则、chart_specs 格式）
2. 维度 context（analysis_dimensions → 特定维度提示文本）
3. 策略指令（strategy_ids → 对应 YAML 的 instructions）

## StockChart Component

- **Library**: lightweight-charts 5.x (CandlestickSeries + HistogramSeries)
- **Props**: `{ symbol, period?, title?, height?, startDate?, endDate? }`
- **Features**: 
  - Period toggle: 日K(1d) / 周K(1w) / 月K(1M) / 年K(1Y)
  - Infinite scroll: auto-fetch older data when scrolling left edge
  - Date range: zooms to `startDate`~`endDate` on load (via `timeScale().setVisibleRange`)
  - ResizeObserver for responsive width
- **API**: `GET /api/stock/klines?symbol=&period=&count=&start_date=&end_date=`

### StockChart Data Flow

```
LLM chart_specs → SSE "done" → ChatMessage parses → v-for StockChart
                                                       ↓
                                              StockChart fetches /api/stock/klines
                                                       ↓
                                              lightweight-charts render
```

## API Reference

### `POST /api/chat/stream`

Request body:
```json
{
  "message": "分析一下茅台",
  "session_id": "sess_xxx",
  "strategy_ids": ["volume_breakout"],
  "analysis_dimensions": ["quote", "technical"],
  "action_id": "chat.send.xxx"
}
```

SSE streaming response, events: `thinking` / `tool_start` / `tool_done` / `content_delta` / `done`.

### `GET /api/stock/klines`

Query params: `symbol` (required), `period` (1d/1w/1M/1Y), `count` (max 1000), `start_date` (YYYY-MM-DD), `end_date` (YYYY-MM-DD), `start_time` (ms), `end_time` (ms).

Returns `{ data: [{ trade_date, open, close, high, low, volume, timestamp }], count }`.

## 重构完成度

### Phase 1 — AnalysisChips + 策略 YAML 迁移 + 轻量路由

| 条目 | 状态 | 文件 |
|------|------|------|
| AnalysisChips 组件 | ✅ 4/6 芯片 | [AnalysisChips.vue](client/src/components/AnalysisChips.vue) |
| ChatView 集成 | ✅ | [ChatView.vue](client/src/views/ChatView.vue) |
| chatStore 改造 | ✅ | [chatStore.ts](client/src/stores/chatStore.ts) |
| 维度 context prompt | ✅ | [chat.py](server/routers/chat.py) `_build_system_message()` |
| 轻量路由 | ✅ | [chat.py](server/routers/chat.py) `is_lightweight` 分支 |
| 策略 YAML 迁移 | ✅ 16 个 | [strategies/](strategies/) |
| strategies.py 改造 | ✅ | [strategies.py](server/services/strategies.py) |

### Phase 2 — 策略分析工具

| 条目 | 状态 | 文件 |
|------|------|------|
| 放量突破检测 | ✅ | [strategy_tools.py](server/agent/strategy_tools.py) |
| 均线交叉检测 | ✅ | 同上 |
| 缩量回踩检测 | ✅ | 同上 |
| 底部放量检测 | ✅ | 同上 |
| 缠论结构分析 | ✅ | 同上 |
| runner.py 工具注入 | ✅ | [runner.py](server/agent/runner.py) |

### Phase 3 — 市场数据工具

| 条目 | 状态 | 文件 |
|------|------|------|
| get_market_indices | ✅ 11 个指数 | [tools.py](server/agent/tools.py) |
| get_sector_rankings | ✅ akshare | 同上 |
| 依赖添加 | ✅ | [pyproject.toml](pyproject.toml) |

### 待办

| 条目 | 优先级 | 说明 |
|------|--------|------|
| 补全 `capital` 芯片 | 低 | 分析资金流向（预留，需要确定数据源后生效）|
| 补全 `full` 芯片 | 低 | 全维度无侧重分析，等价于不选芯片 |
| 删除 `presets.json` | 低 | 数据已全部迁移到 YAML，文件可安全删除 |
| 更多策略分析工具 | 中 | 目前 5/16 策略有专用分析工具，可逐步扩展 |
| 板块数据源优化 | 中 | 当前依赖 akshare，后续可接入 tickflow 板块 API |

## Logging

### Architecture: User Action ID + Request ID 双层关联

```
用户操作 (聊天/深度分析)
  ↓ genActionId('chat.send.1745400000.a1b2')
前端 console.log('[chat.send.a1b2] → ...')     ← 前端日志
  ↓ header: X-Action-Id + body: action_id
后端中间件: 生成 req_id + 提取 action_id        ← contextvars 传播
  ↓
runner / tools / LLM 调用                       ← 日志自动带 [req_xxx][chat.send.a1b2]
```

### 日志格式

后端控制台:
```
2026-05-24 10:00:01 INFO  app   [req_abc123][chat.send.a1b2] → POST /api/chat/stream
2026-05-24 10:00:01 INFO  chat  [req_abc123][chat.send.a1b2] chat.stream session=sess_001
2026-05-24 10:00:02 INFO  runner [req_abc123][chat.send.a1b2] step 1/10 LLM call
2026-05-24 10:00:04 INFO  runner [req_abc123][chat.send.a1b2] step 1/10 LLM done (2.1s) tools=1
2026-05-24 10:00:04 INFO  runner [req_abc123][chat.send.a1b2] step 1/10 tool=get_klines done 0.3s
2026-05-24 10:00:05 INFO  market [req_def456][stock.klines.e5f6] stock.klines symbol=600519.SH
```

前端终端:
```
[chat.send.a1b2] → sendMessage 分析茅台
[chat.send.a1b2] ← SSE events 5 last type: tool_start
[chat.send.a1b2] ← SSE done 15 events, charts: 1
```

### 相关文件

- `client/src/utils/actions.ts` — 动作注册表 + `genActionId()`
- `server/services/logger.py` — ContextLogger + contextvars 传播
- `server/services/action_registry.py` — Python 端注册表
- `server/app.py` — `request_logging` 中间件: 生成 req_id、提取 X-Action-Id、记入/出日志

### Debug 场景

| 后端搜 a1b2 | 含义 |
|---|---|
| 没有日志 | 请求没到后端，前端 fetch 挂了 |
| 只有 `→ POST` 无后续 | runner 初始化阶段崩溃 |
| `LLM call` 无 `LLM done` | LLM API 超时 |
| `tool=...` 失败 | 数据源挂了 |
| 全部正常但前端报错 | SSE 管道断裂 |
