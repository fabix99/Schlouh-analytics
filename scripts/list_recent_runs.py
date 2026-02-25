#!/usr/bin/env python3
"""
Print the last N pipeline runs (from data/index/pipeline_runs.csv).
Usage:
  python scripts/list_recent_runs.py
  python scripts/list_recent_runs.py -n 50
"""

import argparse
import csv
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
from config import INDEX_DIR

PIPELINE_RUNS_PATH = INDEX_DIR / "pipeline_runs.csv"


def main():
    ap = argparse.ArgumentParser(description="List recent pipeline runs")
    ap.add_argument("-n", type=int, default=20, help="Number of runs to show (default 20)")
    args = ap.parse_args()

    if not PIPELINE_RUNS_PATH.exists():
        print("No pipeline runs recorded yet.", file=sys.stderr)
        print(f"Run: python scripts/run_pipeline.py", file=sys.stderr)
        sys.exit(0)

    with open(PIPELINE_RUNS_PATH) as f:
        rows = list(csv.DictReader(f))

    # Skip "running" and show most recent first
    rows = [r for r in rows if r.get("status") != "running"][-args.n :]
    rows.reverse()

    if not rows:
        print("No completed runs found.")
        return

    print(f"Last {len(rows)} pipeline run(s):\n")
    for r in rows:
        run_id = r.get("run_id", "")
        started = r.get("started_utc", "")
        ended = r.get("ended_utc", "")
        steps = r.get("steps_run", "")
        status = r.get("status", "")
        failed = r.get("failed_step", "")
        env = r.get("env", "")
        fail_info = f" (failed at: {failed})" if failed else ""
        print(f"  {started}  status={status}{fail_info}  env={env}")
        print(f"    steps: {steps}")
        if ended:
            print(f"    ended: {ended}")
        print()


if __name__ == "__main__":
    main()
