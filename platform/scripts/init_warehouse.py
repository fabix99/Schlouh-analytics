#!/usr/bin/env python3
"""Create warehouse directory and empty DuckDB file; print connection smoke check."""

from __future__ import annotations

import os
import sys
from pathlib import Path

import duckdb

ROOT = Path(__file__).resolve().parents[2]
DEFAULT = ROOT / "data" / "warehouse" / "schlouh.duckdb"


def warehouse_path() -> Path:
    env = os.environ.get("SOFASCORE_WAREHOUSE_PATH")
    if env:
        p = Path(env)
        return p if p.is_absolute() else ROOT / p
    return DEFAULT


def main() -> int:
    path = warehouse_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect(str(path))
    con.execute("CREATE SCHEMA IF NOT EXISTS analytics")
    ver = con.execute("SELECT version()").fetchone()[0]
    con.close()
    print(f"OK warehouse={path}")
    print(f"OK duckdb_version={ver}")
    print("OK schema=analytics")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
