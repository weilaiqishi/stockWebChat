# -*- coding: utf-8 -*-
"""Configuration endpoints — get/save/validate config."""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Any

from ..app import has_config
from ..config_manager import ConfigManager

router = APIRouter(prefix="/api", tags=["config"])


class ConfigSaveRequest(BaseModel):
    deepseek_api_key: str = ""
    deepseek_model: str = "deepseek-v4-flash"
    deepseek_base_url: str = "https://api.deepseek.com"
    zhihu_access_secret: str = ""
    feishu_app_id: str = ""
    feishu_app_secret: str = ""
    feishu_bitable_id: str = ""


@router.get("/config")
async def get_config():
    """Get current config (masked sensitive values)."""
    cm = ConfigManager()
    return cm.to_safe_dict()


@router.get("/config/status")
async def config_status():
    """Check if config is complete."""
    return {"configured": has_config()}


@router.post("/config/validate")
async def validate_config(body: dict[str, Any]):
    """Validate config and optionally test Feishu connection."""
    cm = ConfigManager()
    result = await cm.validate(body)
    return result


@router.post("/config/save")
async def save_config(body: dict[str, Any]):
    """Validate and save config."""
    cm = ConfigManager()
    result = await cm.validate(body)

    if not result["valid"]:
        raise HTTPException(status_code=400, detail=result["errors"])

    # Update bitable_id if auto-created
    if result.get("bitable_id"):
        body["feishu_bitable_id"] = result["bitable_id"]

    cm.save(body)
    return {
        "message": "配置已保存",
        "bitable_id": result.get("bitable_id", body.get("feishu_bitable_id", "")),
    }


@router.get("/strategies")
async def list_strategies():
    """Get all available strategies."""
    from ..services.strategies import load_strategies
    strategies = load_strategies()
    return {
        "strategies": [
            {"id": s["id"], "name": s["name"], "category": s["category"]}
            for s in strategies
        ]
    }
