#!/usr/bin/env python3
"""
One-shot minimal data setup for forkers / first run.
Discovers one competition, extracts a small number of matches, runs the pipeline.
After this, the dashboard and exports have enough data to run.

Usage (from project root):
  python scripts/quickstart_data.py

Uses: spain-laliga, 2025-26 season, max 20 matches (override with env QUICKSTART_LIMIT).
"""

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
COMPETITION = "spain-laliga"
SEASON = "2025-26"
LIMIT = int(os.environ.get("QUICKSTART_LIMIT", "20"))


def run(cmd: list[str], cwd: Path) -> bool:
    print(f"  $ {' '.join(cmd)}")
    r = subprocess.run(cmd, cwd=str(cwd))
    if r.returncode != 0:
        print(f"  Failed (exit {r.returncode})", file=sys.stderr)
        return False
    return True


def main():
    print("Quickstart: creating minimal data so the dashboard can run.\n")

    # 1. Discover (creates/updates data/index/matches.csv)
    print("1. Discover matches (one competition, one season)...")
    if not run(
        [sys.executable, str(ROOT / "src/discover_matches.py"), COMPETITION, "--seasons", SEASON],
        ROOT,
    ):
        sys.exit(1)

    # 2. Extract a small number of matches
    print("\n2. Extract raw data (limit {} matches)...".format(LIMIT))
    if not run(
        [sys.executable, str(ROOT / "src/extract_batch.py"), COMPETITION, SEASON, "--limit", str(LIMIT)],
        ROOT,
    ):
        sys.exit(1)

    # 3. Run pipeline (derived + processed + dq + validate)
    print("\n3. Run pipeline (derived → processed → validate)...")
    if not run(
        [sys.executable, str(ROOT / "scripts/run_pipeline.py")],
        ROOT,
    ):
        print("  Pipeline had failures; you may still have enough data for the dashboard.", file=sys.stderr)

    print("\nDone. You can run the dashboard (e.g. streamlit run dashboard/Home.py) or add more data via the Operational checklist in README.")


if __name__ == "__main__":
    main()
