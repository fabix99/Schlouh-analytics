"""DuckDB warehouse access — canonical read path for the scouting app."""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from typing import Optional

import pandas as pd

from dashboard.utils.paths import PROJECT_ROOT

DEFAULT_WAREHOUSE = PROJECT_ROOT / "data" / "warehouse" / "schlouh.duckdb"


def warehouse_path() -> Path:
    env = os.environ.get("SOFASCORE_WAREHOUSE_PATH")
    if env:
        p = Path(env)
        return p if p.is_absolute() else PROJECT_ROOT / p
    return DEFAULT_WAREHOUSE


def warehouse_available() -> bool:
    return warehouse_path().exists()


@lru_cache(maxsize=1)
def _connect_readonly():
    import duckdb

    path = warehouse_path()
    if not path.exists():
        raise FileNotFoundError(
            f"Warehouse not found: {path}. Run: bash platform/scripts/run_platform_full.sh"
        )
    return duckdb.connect(str(path), read_only=True)


def read_mart(table: str, schema: str = "analytics_marts") -> pd.DataFrame:
    """Read a dbt mart table from DuckDB."""
    con = _connect_readonly()
    return con.execute(f"select * from {schema}.{table}").fetchdf()


def read_raw(table: str, schema: str = "raw_sofascore") -> pd.DataFrame:
    """Read a raw/DLT table from DuckDB."""
    con = _connect_readonly()
    return con.execute(f"select * from {schema}.{table}").fetchdf()


def clear_warehouse_cache() -> None:
    _connect_readonly.cache_clear()
