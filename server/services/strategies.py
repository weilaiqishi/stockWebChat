# -*- coding: utf-8 -*-
"""Strategy loading — YAML files + optional Feishu custom strategies."""
import json
import os
import yaml
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PRESETS_PATH = ROOT / "strategies" / "presets.json"
STRATEGIES_DIR = ROOT / "strategies"


def load_strategies() -> list[dict]:
    """Load all strategies from YAML files, with JSON fallback.

    Returns a list of {id, name, category, instructions, description} dicts.
    """
    strategies = []

    # Load from YAML files first
    if STRATEGIES_DIR.exists():
        for f in sorted(STRATEGIES_DIR.glob("*.yaml")):
            try:
                with open(f, "r", encoding="utf-8") as fh:
                    data = yaml.safe_load(fh)
                if data and "name" in data:
                    strategies.append({
                        "id": data["name"],
                        "name": data.get("display_name", data["name"]),
                        "category": data.get("category", "framework"),
                        "instructions": data.get("instructions", ""),
                        "description": data.get("description", ""),
                        "required_tools": data.get("required_tools", []),
                    })
            except Exception as e:
                pass  # skip invalid files

    # Fallback: load legacy JSON (for backward compatibility)
    if not strategies and PRESETS_PATH.exists():
        try:
            presets = json.loads(PRESETS_PATH.read_text("utf-8"))
            strategies.extend(presets)
        except Exception:
            pass

    # TODO: Load custom strategies from Feishu if configured

    return strategies


def get_strategy(strategy_id: str) -> dict | None:
    """Get a single strategy by id."""
    for s in load_strategies():
        if s["id"] == strategy_id:
            return s
    return None
