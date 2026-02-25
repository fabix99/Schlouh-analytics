"""
Single source of truth for environment and paths.
Loads config/env.yaml and overrides with env vars so the pipeline can run with different roots (e.g. CI, staging).
"""

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# Defaults (relative to ROOT)
_DEFAULTS = {
    "raw_base": "data/raw",
    "index_path": "data/index/matches.csv",
    "api_base": "https://api.sofascore.com/api/v1",
    "log_dir": "data/logs",
    "derived_dir": "data/derived",
    "processed_dir": "data/processed",
    "index_dir": "data/index",
    "env": "dev",
}

_ENV_VARS = {
    "raw_base": "SOFASCORE_RAW_BASE",
    "index_path": "SOFASCORE_INDEX_PATH",
    "api_base": "SOFASCORE_API_BASE",
    "log_dir": "SOFASCORE_LOG_DIR",
    "derived_dir": "SOFASCORE_DERIVED_DIR",
    "processed_dir": "SOFASCORE_PROCESSED_DIR",
    "index_dir": "SOFASCORE_INDEX_DIR",
    "env": "ENV",
}


def _load_yaml() -> dict:
    out = _DEFAULTS.copy()
    yaml_path = ROOT / "config" / "env.yaml"
    if yaml_path.exists():
        try:
            import yaml
            with open(yaml_path) as f:
                data = yaml.safe_load(f) or {}
            for k, v in data.items():
                if k in out and v is not None:
                    out[k] = v
        except Exception:
            pass
    return out


def _resolve_path(value: str) -> Path:
    p = Path(value)
    if not p.is_absolute():
        p = ROOT / value
    return p


def _get_config() -> dict:
    cfg = _load_yaml()
    for key, env_key in _ENV_VARS.items():
        val = os.environ.get(env_key)
        if val is not None and val != "":
            cfg[key] = val
    return cfg


_cfg = _get_config()

RAW_BASE = _resolve_path(_cfg["raw_base"])
INDEX_PATH = _resolve_path(_cfg["index_path"])
API_BASE = _cfg["api_base"].rstrip("/")
LOG_DIR = _resolve_path(_cfg["log_dir"])
DERIVED_DIR = _resolve_path(_cfg["derived_dir"])
PROCESSED_DIR = _resolve_path(_cfg["processed_dir"])
INDEX_DIR = _resolve_path(_cfg["index_dir"])
ENV = _cfg.get("env", "dev")
