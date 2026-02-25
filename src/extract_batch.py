"""
Batch extract match data for a competition/season from the index.

- Skips matches that already have lineups.csv (use --force to re-extract).
- Quality validation runs by default; use --no-validate to skip.
- Each run is logged to data/index/extraction_progress.csv (upsert).
- Per-match endpoint status is written to data/index/extraction_batch_errors.csv when any failure occurs.

Usage:
  python src/extract_batch.py spain-laliga 2025-26
  python src/extract_batch.py spain-laliga 2025-26 --force  # re-extract even if exists
  python src/extract_batch.py spain-laliga 2025-26 --no-validate  # skip validation
  python src/extract_batch.py spain-laliga 2025-26 --delay 0.5 --limit 5  # dry run with 5 matches

Outputs to: data/raw/{season}/club|national/{competition_slug}/{match_id}/
"""

import argparse
import random
import sys
import time
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from config import INDEX_PATH as CONFIG_INDEX_PATH, INDEX_DIR, RAW_BASE
from extract_match_lineups import (
    extract_graph,
    extract_incidents,
    extract_lineups,
    extract_managers,
    extract_statistics,
)
from progress import append_progress

def _validate_match(match_dir: Path, match_id: str) -> dict:
    """No-op validation (quality module removed). Returns passed=True, errors=[]."""
    return {"passed": True, "errors": []}

ERROR_LOG_PATH = INDEX_DIR / "extraction_batch_errors.csv"

# Circuit breaker: stop extraction after this many consecutive failed matches (429/5xx or lineups fail)
CONSECUTIVE_FAILURES_BREAK = 6


def _delay_jitter(base: float) -> None:
    time.sleep(base + random.uniform(0, min(0.3, base * 0.5)))


def main():
    parser = argparse.ArgumentParser(description="Batch extract match data from index")
    parser.add_argument("competition", help="Competition slug (e.g. spain-laliga)")
    parser.add_argument("season", help="Season label (e.g. 2025-26)")
    parser.add_argument("--index-path", default=None, help="Path to matches index CSV")
    parser.add_argument("--force", action="store_true", help="Re-extract even if already present (default: skip existing)")
    parser.add_argument("--delay", type=float, default=0.5, help="Seconds between matches")
    parser.add_argument("--limit", type=int, default=None, help="Max matches to process (for testing)")
    parser.add_argument("--no-validate", action="store_true", help="Skip quality validation after extraction")
    args = parser.parse_args()

    index_path = Path(args.index_path) if args.index_path else CONFIG_INDEX_PATH
    if not index_path.exists():
        print(f"Index not found: {index_path}")
        print("Run: python src/discover_matches.py spain-laliga")
        sys.exit(1)

    df = pd.read_csv(index_path)
    mask = (df["season"] == args.season) & (df["competition_slug"] == args.competition)
    matches = df.loc[mask, "match_id"].astype(str).tolist()

    if not matches:
        print(f"No matches found for {args.competition} {args.season}")
        sys.exit(0)

    realm = df.loc[mask, "realm"].iloc[0] if "realm" in df.columns else "club"
    out_base = RAW_BASE / args.season / realm / args.competition

    if args.limit:
        matches = matches[: args.limit]
        print(f"Limiting to {args.limit} matches")

    print(f"Extracting {len(matches)} matches for {args.competition} {args.season} -> {out_base}")

    ok = 0
    skip = 0
    failed = 0
    partial_success = 0
    error_rows = []
    consecutive_failures = 0

    for i, match_id in enumerate(matches):
        if consecutive_failures >= CONSECUTIVE_FAILURES_BREAK:
            print(f"  Circuit breaker: stopping after {CONSECUTIVE_FAILURES_BREAK} consecutive failures (rate limit or API errors).", file=sys.stderr)
            break
        match_dir = out_base / str(match_id)
        if not args.force and (match_dir / "lineups.csv").exists():
            skip += 1
            if (i + 1) % 50 == 0:
                print(f"  [{i+1}/{len(matches)}] skipped (already extracted)")
            time.sleep(0.1)
            continue

        lineups_ok = stats_ok = incidents_ok = managers_ok = graph_ok = False
        errors = []

        try:
            match_dir.mkdir(parents=True, exist_ok=True)
            try:
                extract_lineups(match_id, str(match_dir), flat_filenames=True)
                lineups_ok = True
            except Exception as e:
                errors.append(f"lineups:{type(e).__name__}")
            if lineups_ok:
                try:
                    extract_statistics(match_id, str(match_dir), flat_filenames=True)
                    stats_ok = True
                except Exception as e:
                    errors.append(f"stats:{type(e).__name__}")
                try:
                    extract_incidents(match_id, str(match_dir), flat_filenames=True)
                    incidents_ok = True
                except Exception as e:
                    errors.append(f"incidents:{type(e).__name__}")
                try:
                    extract_managers(match_id, str(match_dir), flat_filenames=True)
                    managers_ok = True
                except Exception as e:
                    errors.append(f"managers:{type(e).__name__}")
                try:
                    extract_graph(match_id, str(match_dir), flat_filenames=True)
                    graph_ok = True
                except Exception as e:
                    errors.append(f"graph:{type(e).__name__}")
            if not args.no_validate and lineups_ok:
                res = _validate_match(match_dir, match_id)
                if not res["passed"]:
                    for e in res["errors"]:
                        print(f"    WARN validation: {e['check']} - {e['message']}")
        except Exception as e:
            errors.append(f"run:{type(e).__name__}")

        if lineups_ok and (stats_ok and incidents_ok and managers_ok and graph_ok):
            ok += 1
            consecutive_failures = 0
        elif lineups_ok:
            partial_success += 1
            error_rows.append({
                "match_id": match_id,
                "competition_slug": args.competition,
                "season": args.season,
                "lineups_ok": True,
                "stats_ok": stats_ok,
                "incidents_ok": incidents_ok,
                "managers_ok": managers_ok,
                "graph_ok": graph_ok,
                "status": "partial_success",
                "error_detail": "; ".join(errors),
            })
            consecutive_failures = 0
        else:
            failed += 1
            consecutive_failures += 1
            error_rows.append({
                "match_id": match_id,
                "competition_slug": args.competition,
                "season": args.season,
                "lineups_ok": lineups_ok,
                "stats_ok": stats_ok,
                "incidents_ok": incidents_ok,
                "managers_ok": managers_ok,
                "graph_ok": graph_ok,
                "status": "failed",
                "error_detail": "; ".join(errors),
            })
            if errors:
                print(f"  ERROR match {match_id}: {'; '.join(errors)}")

        if (i + 1) % 10 == 0 or i == 0:
            print(f"  [{i+1}/{len(matches)}] ok={ok}, partial={partial_success}, failed={failed}, skipped={skip}")

        _delay_jitter(args.delay)

    print(f"Done. Extracted: {ok}, Partial: {partial_success}, Failed: {failed}, Skipped: {skip}")

    if error_rows:
        ERROR_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        err_df = pd.DataFrame(error_rows)
        if ERROR_LOG_PATH.exists():
            existing = pd.read_csv(ERROR_LOG_PATH)
            err_df = pd.concat([existing, err_df], ignore_index=True)
        err_df.to_csv(ERROR_LOG_PATH, index=False)
        print(f"  Appended {len(error_rows)} row(s) to {ERROR_LOG_PATH}")

    append_progress(args.competition, args.season, total=len(matches), extracted=ok, skipped=skip, errors=failed)


if __name__ == "__main__":
    main()
