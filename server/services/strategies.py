# -*- coding: utf-8 -*-
"""Strategy loading — presets from JSON file + optional Feishu custom strategies."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PRESETS_PATH = ROOT / "strategies" / "presets.json"


def load_strategies() -> list[dict]:
    """Load all strategies (presets + custom from Feishu if available).

    Returns a list of {id, name, category, instructions} dicts.
    """
    strategies = []

    # Load built-in presets
    if PRESETS_PATH.exists():
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
