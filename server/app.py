# -*- coding: utf-8 -*-
"""FastAPI app factory + shared singletons for stockWebChat."""
import sys as _sys
import io as _io
import json
import os
import time
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

# Project root
ROOT = Path(__file__).resolve().parents[1]

# ---------------------------------------------------------------------------
# Shared singletons (lazy-init)
# ---------------------------------------------------------------------------

_storage = None
_tickflow = None
_feishu = None


def get_storage():
    return _storage


def get_tickflow():
    global _tickflow
    if _tickflow is None:
        _old_stdout = _sys.stdout
        _sys.stdout = _io.StringIO()
        try:
            from tickflow import TickFlow
            _tickflow = TickFlow.free()
        finally:
            _sys.stdout = _old_stdout
    return _tickflow


def get_feishu():
    return _feishu


def has_config() -> bool:
    """Check if any persistent config source has an API key."""
    if os.environ.get("DEEPSEEK_API_KEY", "").strip():
        return True
    config_path = ROOT / "config.json"
    if config_path.exists():
        try:
            cfg = json.loads(config_path.read_text("utf-8"))
            return bool(cfg.get("deepseek_api_key"))
        except Exception:
            pass
    return False


def normalize_code(code: str) -> str:
    """Convert sh600036 -> 600036.SH"""
    code = code.upper().strip()
    if "." in code:
        return code
    if code.startswith("SH"):
        return code[2:] + ".SH"
    if code.startswith("SZ"):
        return code[2:] + ".SZ"
    if code.startswith(("6", "5")):
        return code + ".SH"
    return code + ".SZ"


# ---------------------------------------------------------------------------
# FastAPI app
# ---------------------------------------------------------------------------

app = FastAPI(title="Stock Web Chat - Agent 策略问股")

# ---------------------------------------------------------------------------
# Logging setup
# ---------------------------------------------------------------------------
from .services.logger import setup_logging, gen_req_id, req_id_ctx, action_id_ctx, get_logger
setup_logging()
log = get_logger(__name__)


@app.middleware("http")
async def request_logging(request: Request, call_next):
    """Inject request_id/action_id into contextvars, log entry/exit."""
    req_id = gen_req_id()
    action_id = request.headers.get("X-Action-Id", "") or ""
    req_id_ctx.set(req_id)
    action_id_ctx.set(action_id)

    qs = str(request.query_params) if request.query_params else ""
    path = request.url.path
    log.info("→ %s %s%s", request.method, path, f"?{qs}" if qs else "")

    start = time.monotonic()
    try:
        response = await call_next(request)
        elapsed = time.monotonic() - start
        log.info("← %s %s (%d) %.3fs", request.method, path, response.status_code, elapsed)
        return response
    except Exception as e:
        elapsed = time.monotonic() - start
        log.error("✗ %s %s %.3fs %s: %s", request.method, path, elapsed, type(e).__name__, e)
        raise


app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
async def startup():
    from .config_manager import ConfigManager
    cfg = ConfigManager()
    config = cfg.load()

    # Init feishu if configured
    global _feishu
    if config.get("feishu_app_id") and config.get("feishu_app_secret"):
        try:
            from .services.feishu_client import FeishuClient
            _feishu = FeishuClient(
                app_id=config["feishu_app_id"],
                app_secret=config["feishu_app_secret"],
                bitable_id=config.get("feishu_bitable_id", ""),
            )
            # warm up: verify connection, create tables if needed
            # (done lazily; don't block startup)
        except Exception:
            pass

    get_tickflow()  # warm up


# ---------------------------------------------------------------------------
# Register routers
# ---------------------------------------------------------------------------

from .routers.config import router as config_router
from .routers.chat import router as chat_router
from .routers.market import router as market_router

app.include_router(config_router)
app.include_router(chat_router)
app.include_router(market_router)


# ---------------------------------------------------------------------------
# Serve static SPA in production
# ---------------------------------------------------------------------------

_client_dist = ROOT / "client" / "dist"
if _client_dist.exists():
    app.mount("/", StaticFiles(directory=str(_client_dist), html=True), name="static")
