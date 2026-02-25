"""
Deduplicate data/index/extraction_progress.csv by (competition_slug, season).

Keeps the most recent row per key (by completed_at). Use after validation reports
duplicate (competition_slug, season) rows.

Usage:
  python scripts/fix_extraction_progress.py
  python scripts/fix_extraction_progress.py --dry-run
"""

import argparse
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
PROGRESS_PATH = ROOT / "data" / "index" / "extraction_progress.csv"


def main() -> None:
    parser = argparse.ArgumentParser(description="Deduplicate extraction_progress.csv")
    parser.add_argument("--dry-run", action="store_true", help="Print what would be done, do not write")
    args = parser.parse_args()

    if not PROGRESS_PATH.exists():
        print(f"File not found: {PROGRESS_PATH}")
        return

    df = pd.read_csv(PROGRESS_PATH)
    before = len(df)

    if "completed_at" not in df.columns:
        # Keep last occurrence per key
        df = df.drop_duplicates(subset=["competition_slug", "season"], keep="last")
    else:
        df["_completed_at"] = pd.to_datetime(df["completed_at"], errors="coerce", utc=True)
        df = df.sort_values("_completed_at").drop_duplicates(
            subset=["competition_slug", "season"], keep="last"
        )
        df = df.drop(columns=["_completed_at"])

    after = len(df)
    removed = before - after

    # Deterministic sort for stable diffs
    df = df.sort_values(["competition_slug", "season"]).reset_index(drop=True)
    after = len(df)

    if removed == 0:
        print("No duplicates found. File unchanged (sorted for stable diffs).")
        if args.dry_run:
            return
        df.to_csv(PROGRESS_PATH, index=False)
        print(f"Wrote {PROGRESS_PATH}")
        return

    print(f"Removed {removed} duplicate row(s). Rows: {before} -> {after}")
    if args.dry_run:
        print("Dry run: not writing file.")
        return

    df.to_csv(PROGRESS_PATH, index=False)
    print(f"Wrote {PROGRESS_PATH}")


if __name__ == "__main__":
    main()
