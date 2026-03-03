"""
Add player maps (heatmap, shotmap, rating breakdown) for every match in the index
for a given season — all leagues and European competitions.
Only runs for match dirs that already have lineups.csv.

Usage (from project root):
  python scripts/run_player_maps_season_all.py --season 2025-26
  python scripts/run_player_maps_season_all.py --season 2025-26 --log-file data/logs/player_maps_2025-26.log  # log so you can check progress/errors
  python scripts/run_player_maps_season_all.py --season 2025-26 --competition uefa-champions-league  # one competition only

Then run step 18 to build the heatmap parquet:
  python scripts/build/18_player_match_maps.py
"""

import argparse
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import pandas as pd

from src.config import INDEX_PATH, RAW_BASE
from src.extract_match_lineups import extract_player_maps

DELAY_BETWEEN_MATCHES = 0.8


class Tee:
    """Write to stdout and a log file so background runs can be inspected."""
    def __init__(self, path: Path):
        self._path = path
        self._file = open(path, "w", encoding="utf-8")
    def write(self, data: str):
        sys.__stdout__.write(data)
        self._file.write(data)
        self._file.flush()
    def flush(self):
        sys.__stdout__.flush()
        self._file.flush()
    def close(self):
        self._file.close()


def main():
    parser = argparse.ArgumentParser(
        description="Add player maps for all matches in a season (all leagues & European comps)"
    )
    parser.add_argument("--season", type=str, required=True, help="Season label (e.g. 2025-26)")
    parser.add_argument(
        "--competition",
        type=str,
        default=None,
        help="Optional: only process this competition_slug (e.g. uefa-champions-league)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Only print match list and counts, do not extract",
    )
    parser.add_argument(
        "--skip-existing",
        action="store_true",
        default=True,
        help="Skip match dirs that already have heatmap files (default: True, for resume)",
    )
    parser.add_argument(
        "--no-skip-existing",
        action="store_false",
        dest="skip_existing",
        help="Process all matches even if heatmaps already exist",
    )
    parser.add_argument(
        "--log-file",
        type=str,
        default=None,
        help="Also write all output to this file (e.g. data/logs/player_maps_2025-26.log) so you can check progress/errors",
    )
    args = parser.parse_args()

    log_path = None
    if args.log_file:
        log_path = Path(args.log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        sys.stdout = Tee(log_path)
        print(f"Logging to {log_path}")

    if not INDEX_PATH.exists():
        print(f"Index not found: {INDEX_PATH}")
        print("Run discovery for your competitions first (e.g. src/discover_matches.py).")
        sys.exit(1)

    df = pd.read_csv(INDEX_PATH)
    df["match_id"] = df["match_id"].astype(str)
    if "match_date" not in df.columns:
        print("Index has no match_date column.")
        sys.exit(1)

    # Filter by season
    mask = df["season"].astype(str) == args.season
    subset = df[mask].copy()
    subset["match_date"] = pd.to_numeric(subset["match_date"], errors="coerce")
    subset = subset.dropna(subset=["match_date"])

    if args.competition:
        subset = subset[subset["competition_slug"] == args.competition]
        if subset.empty:
            print(f"No matches for season {args.season} and competition {args.competition}.")
            sys.exit(0)
        print(f"Season {args.season}, competition {args.competition}: {len(subset)} matches")
    else:
        print(f"Season {args.season}, all competitions: {len(subset)} matches")
        print(subset["competition_slug"].value_counts().to_string())
    print()

    subset = subset.sort_values("match_date", ascending=False)

    if args.dry_run:
        for _, row in subset.iterrows():
            print(f"  {row['match_id']}  {row['competition_slug']}  {row.get('home_team_name', '')} vs {row.get('away_team_name', '')}")
        print(f"\nDry run: would process {len(subset)} matches. Run without --dry-run to extract.")
        return

    done = 0
    skipped_no_lineups = 0
    skipped_existing = 0
    failed = 0

    for i, row in subset.iterrows():
        match_id = str(row["match_id"])
        season = str(row["season"])
        realm = str(row.get("realm", "club"))
        comp = str(row["competition_slug"])
        match_dir = RAW_BASE / season / realm / comp / match_id

        if not (match_dir / "lineups.csv").exists():
            skipped_no_lineups += 1
            if skipped_no_lineups <= 5 or (skipped_no_lineups % 100 == 0):
                print(f"  Skip {match_id} ({comp}): no lineups.csv")
            continue

        if args.skip_existing:
            players_dir = match_dir / "players"
            if players_dir.is_dir() and any(players_dir.glob("heatmap_*.json")):
                skipped_existing += 1
                if skipped_existing <= 5 or skipped_existing % 100 == 0:
                    print(f"  Skip {match_id} ({comp}): already has heatmaps [{skipped_existing} skipped]")
                continue

        try:
            n, api_error = extract_player_maps(match_id, str(match_dir))
            done += 1
            if done <= 10 or done % 50 == 0 or done == len(subset):
                print(f"  OK {match_id} ({comp}): wrote {n} player map files [{done} done]")
            if n == 0 and api_error:
                print(f"    -> no data: {api_error}", flush=True)
        except Exception as e:
            failed += 1
            print(f"  ERROR {match_id} ({comp}): {e}")

        time.sleep(DELAY_BETWEEN_MATCHES)

    print()
    print(f"Done. Wrote player maps: {done}, Skipped (no lineups): {skipped_no_lineups}, Skipped (existing): {skipped_existing}, Failed: {failed}")
    if done > 0:
        print("Next: python scripts/build/18_player_match_maps.py")
    if log_path:
        sys.stdout.close()
        sys.stdout = sys.__stdout__


if __name__ == "__main__":
    main()
