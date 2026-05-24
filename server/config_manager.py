# -*- coding: utf-8 -*-
"""Configuration management: load, save, validate config.json."""
import json
import copy
import os
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = ROOT / "config.json"

# Environment variable overrides (e.g. Render deployment)
_ENV_OVERRIDES = {
    "DEEPSEEK_API_KEY": "deepseek_api_key",
    "DEEPSEEK_MODEL": "deepseek_model",
    "DEEPSEEK_BASE_URL": "deepseek_base_url",
    "ZHIHU_ACCESS_SECRET": "zhihu_access_secret",
    "FEISHU_APP_ID": "feishu_app_id",
    "FEISHU_APP_SECRET": "feishu_app_secret",
    "FEISHU_BITABLE_ID": "feishu_bitable_id",
}


def _apply_env_overrides(config: dict) -> dict:
    for env_key, cfg_key in _ENV_OVERRIDES.items():
        val = os.environ.get(env_key)
        if val is not None and val.strip():
            config[cfg_key] = val.strip()
    return config


class ConfigManager:
    def __init__(self):
        self._path = CONFIG_PATH

    def load(self) -> dict:
        """Load config from file (or example), then apply env var overrides."""
        if self._path.exists():
            try:
                return _apply_env_overrides(json.loads(self._path.read_text("utf-8")))
            except Exception:
                pass
        return _apply_env_overrides(self._load_example())

    @staticmethod
    def defaults() -> dict:
        return {
            "deepseek_api_key": "",
            "deepseek_model": "deepseek-v4-flash",
            "deepseek_base_url": "https://api.deepseek.com",
            "zhihu_access_secret": "",
            "feishu_app_id": "",
            "feishu_app_secret": "",
            "feishu_bitable_id": "",
        }

    def _load_example(self) -> dict:
        return self.defaults()

    def save(self, config: dict) -> None:
        """Write config to disk."""
        self._path.write_text(
            json.dumps(config, ensure_ascii=False, indent=2),
            "utf-8",
        )

    async def validate(self, config: dict) -> dict:
        """Validate config and optionally test Feishu connection.

        Returns: {valid: bool, errors: dict, bitable_id: str}
        """
        errors = {}

        # Required fields
        if not config.get("deepseek_api_key", "").strip():
            errors["deepseek_api_key"] = "请输入 DeepSeek API Key"

        # Optional: test Feishu
        bitable_id = config.get("feishu_bitable_id", "")
        if config.get("feishu_app_id") and config.get("feishu_app_secret"):
            try:
                from .services.feishu_client import FeishuClient
                fc = FeishuClient(
                    app_id=config["feishu_app_id"],
                    app_secret=config["feishu_app_secret"],
                    bitable_id=bitable_id,
                )
                result = await fc.validate_and_init()
                if result.get("error"):
                    errors["feishu"] = result["error"]
                else:
                    bitable_id = result.get("bitable_id", bitable_id)
            except ImportError:
                errors["feishu"] = "飞书 SDK 未安装 (lark-oapi)"
            except Exception as e:
                errors["feishu"] = f"飞书连接失败: {e}"

        return {
            "valid": len(errors) == 0,
            "errors": errors,
            "bitable_id": bitable_id,
        }

    def to_safe_dict(self, config: dict = None) -> dict:
        """Return config with sensitive values masked for display."""
        if config is None:
            config = self.load()
        safe = copy.deepcopy(config)
        for key in ("deepseek_api_key", "zhihu_access_secret", "feishu_app_secret"):
            if safe.get(key):
                v = safe[key]
                if len(v) > 8:
                    safe[key] = v[:4] + "****" + v[-4:]
                else:
                    safe[key] = "****"
        return safe
