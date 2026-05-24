# Stock Web Chat — CLAUDE.md

## Project Overview

AI Agent 多轮对话股票分析系统。用户通过自然语言问股，Agent 自动调用工具获取数据（K线、行情、知乎、全网搜索），在对话中渲染走势图。

## Tech Stack

- **Backend**: Python 3.10+ / FastAPI / uv / DeepSeek API / tickflow (免费行情)
- **Frontend**: Vue 3 Composition API / TypeScript 5.9 strict / Vite 8 / Pinia / Tailwind 3.4 / shadcn-vue / lightweight-charts 5
- **Infra**: Docker multi-stage build / GitHub Actions
- **Package managers**: uv (Python) / pnpm (frontend)

## Commands

```bash
# Backend
uv sync                          # install dependencies
uv run python main.py            # start dev server on :8000 (API + SPA)

# Frontend (hot-reload dev mode)
cd client && pnpm dev            # :5173, proxies /api → :8000

# Build
cd client && pnpm build          # outputs to client/dist/

# Docker
docker compose up -d
```

## Project Structure

```
stockWebChat/
├── main.py                      # uvicorn entry: server.app
├── README.md
├── pyproject.toml               # Python deps
├── Dockerfile / docker-compose.yml
├── config.example.json

├── server/
│   ├── app.py                   # FastAPI factory + CORS + singletons
│   ├── config_manager.py        # config.json CRUD + validation
│   ├── routers/
│   │   ├── chat.py              # POST /api/chat/stream (SSE), /summarize, /deep-analysis
│   │   ├── config.py            # GET/POST /api/config
│   │   └── market.py            # GET /api/stock/klines, /api/stock/instrument
│   └── agent/
│       ├── runner.py            # ReAct loop (max 10 steps, 120s)
│       ├── tools.py             # 5 tools: search_zhihu, search_global, get_klines, get_realtime_quote, get_instrument_info
│       ├── client_ext.py        # LLMClient: DeepSeek chat + streaming
│       └── conversation.py      # In-memory session store

├── client/src/
│   ├── main.ts / App.vue
│   ├── router/index.ts          # /chat, /settings
│   ├── stores/
│   │   ├── chatStore.ts         # SSE streaming + messages + sessions
│   │   └── configStore.ts       # Config state
│   ├── views/
│   │   ├── ChatView.vue         # Main chat UI
│   │   └── SettingsView.vue
│   └── components/
│       ├── StockChart.vue       # lightweight-charts K线
│       ├── ChatMessage.vue      # Message bubble + charts + thinking
│       ├── SessionSidebar.vue
│       ├── ConfigForm.vue
│       └── ui/                  # shadcn-vue primitives
└── strategies/presets.json      # 4 built-in trading strategy instructions
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

## Agent / Tool System

### ReAct Loop (`runner.py`)

```
LLM(call tools?) → [tool_calls] → execute → append results → loop
            ↘ [final answer] → parse chart_specs → return
```

- Max 10 steps, wall clock 120s budget
- Tool results cached by `tool_name:json_args` key within one turn
- Chart specs extracted from LLM's markdown by regex: ` ```chart_specs\n[...]\n``` `

### Tool Definitions (`tools.py`)

Each tool = `{name, display_name, description, parameters(JSON Schema), handler}`.

| Tool | Data Source | Description |
|------|-------------|-------------|
| `search_zhihu` | Zhihu Open API | 知乎站内搜索 |
| `search_global` | Zhihu Open API | 全网搜索 |
| `get_klines` | tickflow | OHLCV 历史K线 |
| `get_realtime_quote` | tickflow | 实时行情 |
| `get_instrument_info` | tickflow | 标的信息 |

### System Prompt (`chat.py`)

System prompt instructs the LLM to:
1. Call tools before making claims (get_klines before technical analysis)
2. Output chart specs in its final markdown: ` ```chart_specs [{ symbol, period?, start_date?, end_date?, title? }]``` `
3. Respect user-specified time ranges → fill `start_date`/`end_date` (YYYY-MM-DD)

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

### `GET /api/stock/klines`

Query params: `symbol` (required), `period` (1d/1w/1M/1Y), `count` (max 1000), `start_date` (YYYY-MM-DD), `end_date` (YYYY-MM-DD), `start_time` (ms), `end_time` (ms).

Returns `{ data: [{ trade_date, open, close, high, low, volume, timestamp }], count }`.

Supports date-range query (for LLM-requested time windows) and time-range incremental scroll.

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

| 后端搜 a1b2                | 含义 |
|---|---|---|
| 没有日志 | 请求没到后端，前端 fetch 挂了 |
| 只有 `→ POST` 无后续 | runner 初始化阶段崩溃 |
| `LLM call` 无 `LLM done` | LLM API 超时 |
| `tool=...` 失败 | 数据源挂了 |
| 全部正常但前端报错 | SSE 管道断裂 |
