"""
Track and report extraction progress across competitions and seasons.

Usage:
  python src/progress.py status          # Show what's done vs pending vs not started
  python src/progress.py log             # Show extraction run history
  python src/progress.py status --csv    # Output as CSV
"""

import argparse
import sys
from datetime import datetime
from pathlib import Path
from typing import List, Tuple

import sys
from pathlib import Path as _Path
sys.path.insert(0, str(_Path(__file__).resolve().parent))

import pandas as pd
import yaml

from config import INDEX_DIR, INDEX_PATH, RAW_BASE, ROOT

PROGRESS_PATH = INDEX_DIR / "extraction_progress.csv"
PROGRESS_RUNS_PATH = INDEX_DIR / "extraction_progress_runs.csv"
SCOPE_PATH = ROOT / "config" / "scope.yaml"
PROGRESS_COLS = ["competition_slug", "season", "total", "extracted", "skipped", "errors", "completed_at"]


def load_scope() -> List[Tuple[str, str, str]]:
    """Load full scope from config/scope.yaml. Returns [(competition_slug, season, realm), ...]."""
    if not SCOPE_PATH.exists():
        return []
    with open(SCOPE_PATH, encoding="utf-8") as f:
        data = yaml.safe_load(f)
    if not data:
        return []
    seasons = data.get("seasons", [])
    rows = []
    for realm_key, comps in [("club", data.get("club", {})), ("national", data.get("national", []))]:
        if realm_key == "club" and isinstance(comps, dict):
            for _group, slugs in comps.items():
                for slug in slugs:
                    for season in seasons:
                        rows.append((slug, season, "club"))
        elif realm_key == "national" and isinstance(comps, list):
            for slug in comps:
                for season in seasons:
                    rows.append((slug, season, "national"))
    return rows


def get_expected_from_index() -> pd.DataFrame:
    """Return DataFrame with competition_slug, season, realm, expected (count)."""
    if not INDEX_PATH.exists():
        return pd.DataFrame(columns=["competition_slug", "season", "realm", "expected"])
    df = pd.read_csv(INDEX_PATH)
    if "competition_slug" not in df.columns or "season" not in df.columns:
        return pd.DataFrame(columns=["competition_slug", "season", "realm", "expected"])
    g = df.groupby(["competition_slug", "season"])
    cnt = g.size().reset_index(name="expected")
    realm = df.groupby(["competition_slug", "season"])["realm"].first().reset_index()
    cnt = cnt.merge(realm, on=["competition_slug", "season"])
    return cnt


def count_extracted(competition_slug: str, season: str, realm: str) -> int:
    """Count match folders that have lineups.csv (i.e. successfully extracted)."""
    base = RAW_BASE / season / realm / competition_slug
    if not base.exists():
        return 0
    count = 0
    for d in base.iterdir():
        if d.is_dir() and not d.name.startswith(".") and (d / "lineups.csv").exists():
            count += 1
    return count


def get_extraction_status() -> pd.DataFrame:
    """Return status table: competition, season, expected, extracted, status (incl. not_started)."""
    scope = load_scope()
    index_df = get_expected_from_index()
    index_lookup = {}
    if not index_df.empty:
        for _, r in index_df.iterrows():
            key = (r["competition_slug"], r["season"])
            index_lookup[key] = {"expected": int(r["expected"]), "realm": r.get("realm", "club")}

    rows = []
    for comp, season, realm in scope:
        key = (comp, season)
        extracted = count_extracted(comp, season, realm)
        if key in index_lookup:
            exp = index_lookup[key]["expected"]
            if extracted >= exp:
                status = "complete"
            elif extracted > 0:
                status = "partial"
            else:
                status = "pending"
            rows.append({"competition_slug": comp, "season": season, "realm": realm, "expected": exp, "extracted": extracted, "status": status})
        else:
            rows.append({"competition_slug": comp, "season": season, "realm": realm, "expected": None, "extracted": extracted, "status": "not_started"})

    return pd.DataFrame(rows)


def get_extraction_log() -> pd.DataFrame:
    """Return extraction run history from runs log (if present), else from canonical table."""
    if PROGRESS_RUNS_PATH.exists():
        return pd.read_csv(PROGRESS_RUNS_PATH)
    if PROGRESS_PATH.exists():
        return pd.read_csv(PROGRESS_PATH)
    return pd.DataFrame()


def _load_canonical_progress() -> pd.DataFrame:
    """Load canonical progress table (one row per competition_slug, season)."""
    if not PROGRESS_PATH.exists():
        return pd.DataFrame(columns=PROGRESS_COLS)
    df = pd.read_csv(PROGRESS_PATH)
    for c in PROGRESS_COLS:
        if c not in df.columns:
            df[c] = None
    return df


def _save_canonical_progress(df: pd.DataFrame) -> None:
    """Write canonical table sorted by (competition_slug, season) for stable diffs."""
    df = df.sort_values(["competition_slug", "season"]).reset_index(drop=True)
    df.to_csv(PROGRESS_PATH, index=False)


def append_progress(competition: str, season: str, total: int, extracted: int, skipped: int, errors: int) -> None:
    """Upsert extraction progress by (competition_slug, season). Keeps canonical table unique.
    Appends this run to extraction_progress_runs.csv for history."""
    PROGRESS_PATH.parent.mkdir(parents=True, exist_ok=True)
    completed_at = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
    row = {
        "competition_slug": competition,
        "season": season,
        "total": total,
        "extracted": extracted,
        "skipped": skipped,
        "errors": errors,
        "completed_at": completed_at,
    }
    df = _load_canonical_progress()
    key = (str(competition).strip(), str(season).strip())
    mask = (df["competition_slug"].astype(str).str.strip() == key[0]) & (df["season"].astype(str).str.strip() == key[1])
    if mask.any():
        for col, val in row.items():
            df.loc[mask, col] = val
    else:
        df = pd.concat([df, pd.DataFrame([row])], ignore_index=True)
    _save_canonical_progress(df)
    # Append to run history
    run_row = {**row}
    if PROGRESS_RUNS_PATH.exists():
        runs = pd.read_csv(PROGRESS_RUNS_PATH)
        runs = pd.concat([runs, pd.DataFrame([run_row])], ignore_index=True)
    else:
        runs = pd.DataFrame([run_row])
    runs.to_csv(PROGRESS_RUNS_PATH, index=False)


def main():
    parser = argparse.ArgumentParser(description="Extraction progress tracking")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_status = sub.add_parser("status", help="Show extraction status (done vs pending)")
    p_status.add_argument("--csv", action="store_true", help="Output as CSV")

    p_log = sub.add_parser("log", help="Show extraction run history")
    p_log.add_argument("-n", type=int, default=20, help="Number of recent runs to show (default 20)")

    args = parser.parse_args()

    if args.cmd == "status":
        df = get_extraction_status()
        if args.csv:
            df.to_csv(sys.stdout, index=False)
        else:
            if df.empty:
                print("No scope found. Create config/scope.yaml first.")
                sys.exit(0)
            df = df.sort_values(["competition_slug", "season"])
            complete = (df["status"] == "complete").sum()
            partial = (df["status"] == "partial").sum()
            pending = (df["status"] == "pending").sum()
            not_started = (df["status"] == "not_started").sum()
            exp_total = df["expected"].fillna(0).astype(int).sum()
            ext_total = int(df["extracted"].sum())
            print("Extraction Status")
            print("-" * 80)
            df_display = df.copy()
            df_display["expected"] = df_display["expected"].apply(lambda x: "—" if pd.isna(x) else int(x))
            print(df_display.to_string(index=False))
            print("-" * 80)
            print(f"Complete: {complete} | Partial: {partial} | Pending: {pending} | Not started: {not_started}")
            print(f"Total matches in index: {exp_total:,}")
            print(f"Total extracted: {ext_total:,}")

    elif args.cmd == "log":
        df = get_extraction_log()
        if df.empty:
            print("No extraction runs logged yet.")
            sys.exit(0)
        df = df.tail(args.n).iloc[::-1]
        print("Extraction Log (most recent first)")
        print("-" * 80)
        print(df.to_string(index=False))


if __name__ == "__main__":
    main()
