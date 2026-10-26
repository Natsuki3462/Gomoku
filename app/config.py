from __future__ import annotations

import json
from pathlib import Path
from typing import Any

APP_DIR = Path(__file__).resolve().parent
ROOT_DIR = APP_DIR.parent
ENGINE_DIR = ROOT_DIR / "engine"
CONFIG_PATH = ROOT_DIR / "config.json"

APP_NAME = "GomokuFloat"
BOARD_SIZE = 15

WINDOW_MIN_WIDTH = 380
WINDOW_MIN_HEIGHT = 430
DEFAULT_GEOMETRY = [1120, 120, 470, 560]

MIN_OPACITY = 0.15
MAX_OPACITY = 1.0
DEFAULT_OPACITY = 0.95

STRENGTH_PRESETS: dict[str, tuple[str, int, int, int]] = {
    "fast": ("轻快", 300, 2, 128),
    "balanced": ("均衡", 800, 4, 256),
    "deep": ("深度", 1500, 6, 512),
    "max": ("极限", 3000, 8, 1024),
}
CUSTOM_STRENGTH = "custom"

RULE_RENJU = "renju"
RULE_FREESTYLE = "freestyle"

DEFAULT_CONFIG: dict[str, Any] = {
    "engine_path": "",
    "rule_mode": RULE_RENJU,
    "block_forbidden": True,
    "strength": "balanced",
    "movetime_ms": 800,
    "debounce_ms": 180,
    "threads": 4,
    "hash_mb": 256,
    "opacity": 0.95,
    "geometry": list(DEFAULT_GEOMETRY),
    "show_coords": False,
    "auto_accept": False,
    "low_priority": True,
}

ENGINE_PATTERNS = (
    "pbrain-rapfi-windows-avxvnni.exe",
    "pbrain-rapfi-windows-avx2.exe",
    "pbrain-rapfi-windows-sse.exe",
    "rapfi.exe",
    "pbrain-rapfi.exe",
)

def find_engine(explicit: str | None = None) -> Path | None:
    if explicit:
        path = Path(explicit)
        if path.is_file():
            return path
    for name in ENGINE_PATTERNS:
        candidate = ENGINE_DIR / name
        if candidate.is_file():
            return candidate
    if ENGINE_DIR.is_dir():
        for candidate in sorted(ENGINE_DIR.glob("pbrain-rapfi*.exe")):
            if candidate.is_file():
                return candidate
        for candidate in sorted(ENGINE_DIR.glob("*rapfi*.exe")):
            if candidate.is_file():
                return candidate
    return None

def apply_preset(cfg: dict[str, Any], name: str) -> None:
    if name in STRENGTH_PRESETS:
        _, ms, threads, hash_mb = STRENGTH_PRESETS[name]
        cfg["movetime_ms"] = ms
        cfg["threads"] = threads
        cfg["hash_mb"] = hash_mb
    cfg["strength"] = name

def _sanitize(cfg: dict[str, Any]) -> dict[str, Any]:
    out = dict(cfg)
    out["movetime_ms"] = int(max(50, min(30000, int(out.get("movetime_ms") or 800))))
    out["debounce_ms"] = int(max(0, min(1500, int(out.get("debounce_ms") or 180))))
    out["threads"] = int(max(1, min(32, int(out.get("threads") or 4))))
    out["hash_mb"] = int(max(16, min(4096, int(out.get("hash_mb") or 256))))
    try:
        opacity = float(out.get("opacity", DEFAULT_OPACITY))
    except (TypeError, ValueError):
        opacity = DEFAULT_OPACITY
    out["opacity"] = round(max(MIN_OPACITY, min(MAX_OPACITY, opacity)), 3)
    for key, default in (
        ("show_coords", False),
        ("auto_accept", False),
        ("low_priority", True),
        ("block_forbidden", True),
    ):
        out[key] = bool(out.get(key, default))
    if out.get("rule_mode") not in (RULE_RENJU, RULE_FREESTYLE):
        out["rule_mode"] = RULE_RENJU
    strength = out.get("strength")
    if strength not in STRENGTH_PRESETS and strength != CUSTOM_STRENGTH:
        strength = "balanced"
    out["strength"] = strength
    geo = out.get("geometry")
    if not (isinstance(geo, list) and len(geo) == 4):
        out["geometry"] = list(DEFAULT_GEOMETRY)
    else:
        out["geometry"] = [int(v) for v in geo]
    return out

def load_config() -> dict[str, Any]:
    cfg = dict(DEFAULT_CONFIG)
    raw: dict[str, Any] = {}
    try:
        loaded = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
        if isinstance(loaded, dict):
            raw = loaded
            cfg.update({k: v for k, v in raw.items() if k in DEFAULT_CONFIG})
    except (OSError, ValueError):
        pass
    if "strength" not in raw:
        apply_preset(cfg, "balanced")
    return _sanitize(cfg)

def save_config(cfg: dict[str, Any]) -> None:
    try:
        CONFIG_PATH.write_text(
            json.dumps(_sanitize(cfg), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    except OSError:
        pass
