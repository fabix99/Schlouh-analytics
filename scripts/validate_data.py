"""
Data validation script for the Sofascore scraping project.

Validates all artifacts under data/ except data/raw/ (the trusted source).

Usage:
    python scripts/validate_data.py
    python scripts/validate_data.py --verbose
    python scripts/validate_data.py --fail-fast
"""

from __future__ import annotations

import argparse
import os
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pandas as pd

# ---------------------------------------------------------------------------
# Paths (prefer config so SOFASCORE_* env overrides apply in CI/prod)
# ---------------------------------------------------------------------------

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
try:
    from config import RAW_BASE, DERIVED_DIR, PROCESSED_DIR, INDEX_DIR
    DATA = ROOT / "data"  # fallback for any path not in config
    INDEX = INDEX_DIR
    DERIVED = DERIVED_DIR
    PROCESSED = PROCESSED_DIR
    RAW = RAW_BASE
except ImportError:
    DATA = ROOT / "data"
    INDEX = DATA / "index"
    DERIVED = DATA / "derived"
    PROCESSED = DATA / "processed"
    RAW = DATA / "raw"


# ---------------------------------------------------------------------------
# Result tracking
# ---------------------------------------------------------------------------


@dataclass
class CheckResult:
    artifact: str
    check: str
    passed: bool
    detail: str = ""


@dataclass
class Report:
    results: list[CheckResult] = field(default_factory=list)
    verbose: bool = False
    fail_fast: bool = False

    def record(self, artifact: str, check: str, passed: bool, detail: str = "") -> None:
        r = CheckResult(artifact, check, passed, detail)
        self.results.append(r)
        icon = "✓" if passed else "✗"
        if self.verbose or not passed:
            msg = f"  [{icon}] {check}"
            if detail:
                msg += f" — {detail}"
            print(msg)
        if self.fail_fast and not passed:
            self.print_summary()
            sys.exit(1)

    def check(
        self,
        artifact: str,
        check_name: str,
        condition: bool,
        detail: str = "",
        fail_detail: str = "",
    ) -> bool:
        d = detail if condition else (fail_detail or detail)
        self.record(artifact, check_name, condition, d)
        return condition

    def print_summary(self) -> None:
        total = len(self.results)
        passed = sum(r.passed for r in self.results)
        failed = total - passed

        print()
        print("=" * 60)
        print(f"VALIDATION SUMMARY  —  {passed}/{total} checks passed")
        print("=" * 60)

        if failed == 0:
            print("All checks passed.")
            return

        print(f"\nFailed checks ({failed}):")
        by_artifact: dict[str, list[CheckResult]] = {}
        for r in self.results:
            if not r.passed:
                by_artifact.setdefault(r.artifact, []).append(r)
        for artifact, checks in by_artifact.items():
            print(f"\n  {artifact}")
            for c in checks:
                detail = f" — {c.detail}" if c.detail else ""
                print(f"    ✗ {c.check}{detail}")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def load_csv(path: Path, report: Report, artifact: str) -> pd.DataFrame | None:
    if not path.exists():
        report.record(artifact, "file_exists", False, f"{path} not found")
        return None
    report.record(artifact, "file_exists", True)
    try:
        df = pd.read_csv(path, low_memory=False)
        report.record(artifact, "file_readable", True, f"{len(df):,} rows")
        return df
    except Exception as exc:
        report.record(artifact, "file_readable", False, str(exc))
        return None


def load_parquet(path: Path, report: Report, artifact: str) -> pd.DataFrame | None:
    if not path.exists():
        report.record(artifact, "file_exists", False, f"{path} not found")
        return None
    report.record(artifact, "file_exists", True)
    try:
        df = pd.read_parquet(path)
        report.record(artifact, "file_readable", True, f"{len(df):,} rows")
        return df
    except Exception as exc:
        report.record(artifact, "file_readable", False, str(exc))
        return None


def check_columns(
    df: pd.DataFrame,
    required: list[str],
    report: Report,
    artifact: str,
) -> bool:
    missing = [c for c in required if c not in df.columns]
    ok = len(missing) == 0
    report.check(
        artifact,
        "required_columns_present",
        ok,
        fail_detail=f"missing: {missing}",
    )
    return ok


def check_no_duplicates(
    df: pd.DataFrame,
    keys: list[str],
    report: Report,
    artifact: str,
    check_name: str = "no_duplicate_keys",
) -> None:
    available = [k for k in keys if k in df.columns]
    if len(available) < len(keys):
        return
    dupes = df.duplicated(subset=available, keep=False).sum()
    report.check(
        artifact,
        check_name,
        dupes == 0,
        fail_detail=f"{dupes} duplicate rows on {available}",
    )


def check_not_null(
    df: pd.DataFrame,
    cols: list[str],
    report: Report,
    artifact: str,
    check_name: str | None = None,
) -> None:
    for col in cols:
        if col not in df.columns:
            continue
        nulls = df[col].isna().sum()
        name = check_name or f"no_nulls_{col}"
        report.check(
            artifact,
            name,
            nulls == 0,
            fail_detail=f"{nulls} null values in '{col}'",
        )


def check_numeric_range(
    df: pd.DataFrame,
    col: str,
    lo: float | None,
    hi: float | None,
    report: Report,
    artifact: str,
    allow_null: bool = True,
) -> None:
    if col not in df.columns:
        return
    series = df[col].dropna() if allow_null else df[col]
    violations = 0
    if lo is not None:
        violations += (series < lo).sum()
    if hi is not None:
        violations += (series > hi).sum()
    report.check(
        artifact,
        f"range_{col}",
        violations == 0,
        fail_detail=f"{violations} out-of-range values in '{col}' (expected [{lo}, {hi}])",
    )


def check_values_in_set(
    df: pd.DataFrame,
    col: str,
    allowed: set[Any],
    report: Report,
    artifact: str,
    allow_null: bool = True,
) -> None:
    if col not in df.columns:
        return
    series = df[col].dropna() if allow_null else df[col]
    bad = ~series.isin(allowed)
    report.check(
        artifact,
        f"values_{col}",
        not bad.any(),
        fail_detail=f"unexpected values in '{col}': {series[bad].unique().tolist()[:10]}",
    )


def get_raw_match_ids() -> set[str]:
    """Collect match_ids that exist in data/raw/ by walking the directory tree."""
    ids: set[str] = set()
    if not RAW.exists():
        return ids
    for season_dir in RAW.iterdir():
        if not season_dir.is_dir():
            continue
        for realm_dir in season_dir.iterdir():
            if not realm_dir.is_dir():
                continue
            for comp_dir in realm_dir.iterdir():
                if not comp_dir.is_dir():
                    continue
                for match_dir in comp_dir.iterdir():
                    if match_dir.is_dir():
                        ids.add(match_dir.name)
    return ids


# ---------------------------------------------------------------------------
# Artifact validators
# ---------------------------------------------------------------------------


def validate_players_index(report: Report) -> pd.DataFrame | None:
    artifact = "data/index/players.csv"
    path = INDEX / "players.csv"
    print(f"\n--- {artifact} ---")

    df = load_csv(path, report, artifact)
    if df is None:
        return None

    required = [
        "player_id", "player_name", "player_slug", "player_shortName",
        "n_matches", "first_match_id", "last_match_id", "competitions", "seasons",
    ]
    if not check_columns(df, required, report, artifact):
        return df

    check_no_duplicates(df, ["player_id"], report, artifact, "no_duplicate_player_id")
    check_not_null(df, ["player_id", "player_name", "player_slug"], report, artifact)

    # Numeric types
    for col in ["player_id", "n_matches", "first_match_id", "last_match_id"]:
        numeric_ok = pd.to_numeric(df[col], errors="coerce").notna().all()
        report.check(artifact, f"numeric_{col}", numeric_ok, fail_detail=f"'{col}' contains non-numeric values")

    # n_matches >= 0 (0 allowed for incident-only players who have no lineup appearance)
    if pd.api.types.is_numeric_dtype(df["n_matches"]):
        report.check(
            artifact, "n_matches_ge_0",
            (df["n_matches"] >= 0).all(),
            fail_detail=f"{(df['n_matches'] < 0).sum()} rows with n_matches < 0",
        )

    # first_match_id <= last_match_id (as integers)
    try:
        fid = pd.to_numeric(df["first_match_id"], errors="coerce")
        lid = pd.to_numeric(df["last_match_id"], errors="coerce")
        valid_mask = fid.notna() & lid.notna()
        violations = (fid[valid_mask] > lid[valid_mask]).sum()
        report.check(
            artifact, "first_match_id_le_last_match_id",
            violations == 0,
            fail_detail=f"{violations} rows where first_match_id > last_match_id",
        )
    except Exception as exc:
        report.record(artifact, "first_match_id_le_last_match_id", False, str(exc))

    # competitions and seasons non-empty
    for col in ["competitions", "seasons"]:
        if col in df.columns:
            empty = df[col].isna() | (df[col].astype(str).str.strip() == "")
            report.check(
                artifact, f"{col}_non_empty",
                not empty.any(),
                fail_detail=f"{empty.sum()} rows with empty '{col}'",
            )

    return df


def validate_extraction_progress(report: Report) -> pd.DataFrame | None:
    artifact = "data/index/extraction_progress.csv"
    path = INDEX / "extraction_progress.csv"
    print(f"\n--- {artifact} ---")

    df = load_csv(path, report, artifact)
    if df is None:
        return None

    required = ["competition_slug", "season", "total", "extracted", "skipped", "errors", "completed_at"]
    if not check_columns(df, required, report, artifact):
        return df

    check_no_duplicates(df, ["competition_slug", "season"], report, artifact, "no_duplicate_competition_season")
    check_not_null(df, ["competition_slug", "season", "total", "extracted", "skipped", "errors"], report, artifact)

    # Integer counts >= 0
    for col in ["total", "extracted", "skipped", "errors"]:
        if col in df.columns:
            as_int = pd.to_numeric(df[col], errors="coerce")
            report.check(artifact, f"numeric_{col}", as_int.notna().all(), fail_detail=f"non-numeric values in '{col}'")
            report.check(artifact, f"{col}_ge_0", (as_int.dropna() >= 0).all(), fail_detail=f"negative values in '{col}'")

    # extracted + skipped + errors <= total
    try:
        total = pd.to_numeric(df["total"], errors="coerce")
        summed = (
            pd.to_numeric(df["extracted"], errors="coerce").fillna(0)
            + pd.to_numeric(df["skipped"], errors="coerce").fillna(0)
            + pd.to_numeric(df["errors"], errors="coerce").fillna(0)
        )
        violations = (summed > total).sum()
        report.check(
            artifact, "extracted_plus_skipped_plus_errors_le_total",
            violations == 0,
            fail_detail=f"{violations} rows where extracted+skipped+errors > total",
        )
    except Exception as exc:
        report.record(artifact, "extracted_plus_skipped_plus_errors_le_total", False, str(exc))

    # completed_at is parseable as ISO datetime
    if "completed_at" in df.columns:
        try:
            parsed = pd.to_datetime(df["completed_at"], errors="coerce", utc=True)
            bad = parsed.isna().sum()
            report.check(artifact, "completed_at_is_datetime", bad == 0, fail_detail=f"{bad} unparseable values in 'completed_at'")
        except Exception as exc:
            report.record(artifact, "completed_at_is_datetime", False, str(exc))

    return df


def validate_matches_index(report: Report) -> pd.DataFrame | None:
    artifact = "data/index/matches.csv"
    path = INDEX / "matches.csv"
    print(f"\n--- {artifact} ---")

    df = load_csv(path, report, artifact)
    if df is None:
        return None

    required = [
        "match_id", "season", "realm", "competition_slug",
        "home_team_id", "home_team_name", "away_team_id", "away_team_name",
        "match_date", "status_code", "status_type",
    ]
    check_columns(df, required, report, artifact)
    check_no_duplicates(df, ["match_id"], report, artifact, "no_duplicate_match_id")
    check_not_null(df, ["match_id", "season", "competition_slug", "home_team_id", "away_team_id"], report, artifact)

    # Home and away teams must differ
    if "home_team_id" in df.columns and "away_team_id" in df.columns:
        same = (df["home_team_id"] == df["away_team_id"]).sum()
        report.check(artifact, "home_away_teams_differ", same == 0, fail_detail=f"{same} rows with identical home/away team")

    # match_date is a unix timestamp (large int)
    if "match_date" in df.columns:
        as_num = pd.to_numeric(df["match_date"], errors="coerce")
        report.check(artifact, "match_date_numeric", as_num.notna().all(), fail_detail="non-numeric match_date values")
        # Sanity: between 2010-01-01 and 2030-01-01
        report.check(
            artifact, "match_date_plausible",
            (as_num.dropna() > 1_262_304_000).all() and (as_num.dropna() < 1_893_456_000).all(),
            fail_detail="match_date out of plausible range",
        )

    return df


def validate_quality_report(report: Report) -> None:
    artifact = "data/index/quality_report.csv"
    path = INDEX / "quality_report.csv"
    print(f"\n--- {artifact} ---")

    df = load_csv(path, report, artifact)
    if df is None:
        return

    required = ["match_id", "passed", "error_count"]
    check_columns(df, required, report, artifact)
    check_no_duplicates(df, ["match_id"], report, artifact, "no_duplicate_match_id")

    if "passed" in df.columns:
        check_values_in_set(df, "passed", {True, False, "True", "False", 1, 0}, report, artifact)

    if "error_count" in df.columns:
        as_num = pd.to_numeric(df["error_count"], errors="coerce")
        report.check(artifact, "error_count_ge_0", (as_num.dropna() >= 0).all(), fail_detail="negative error_count values")


def validate_player_appearances(
    report: Report,
    players_df: pd.DataFrame | None,
    raw_match_ids: set[str],
) -> pd.DataFrame | None:
    artifact = "data/derived/player_appearances.parquet"
    path = DERIVED / "player_appearances.parquet"
    print(f"\n--- {artifact} ---")

    df = load_parquet(path, report, artifact)
    if df is None:
        return None

    required_cols = [
        "player_id", "player_name", "player_slug", "match_id",
        "season", "realm", "competition_slug", "match_date", "match_date_utc",
        "home_team_name", "away_team_name", "team", "side",
        "stat_minutesPlayed", "stat_rating",
    ]
    check_columns(df, required_cols, report, artifact)
    check_no_duplicates(df, ["player_id", "match_id"], report, artifact, "no_duplicate_player_match")
    check_not_null(df, ["player_id", "match_id", "side", "team", "season", "competition_slug"], report, artifact)

    check_values_in_set(df, "side", {"home", "away"}, report, artifact)
    check_numeric_range(df, "stat_rating", 1.0, 10.0, report, artifact)
    check_numeric_range(df, "stat_minutesPlayed", 0.0, 130.0, report, artifact)

    # Stat columns must be >= 0 (spot-check key ones)
    for col in ["stat_totalPass", "stat_totalShots", "stat_goals", "stat_goalAssist"]:
        check_numeric_range(df, col, 0.0, None, report, artifact)

    # accurate <= total pass checks
    if "stat_accuratePass" in df.columns and "stat_totalPass" in df.columns:
        mask = df["stat_accuratePass"].notna() & df["stat_totalPass"].notna()
        violations = (df.loc[mask, "stat_accuratePass"] > df.loc[mask, "stat_totalPass"]).sum()
        report.check(
            artifact, "accurate_pass_le_total_pass",
            violations == 0,
            fail_detail=f"{violations} rows where accuratePass > totalPass",
        )

    # FK: player_id in players index
    if players_df is not None and "player_id" in df.columns and "player_id" in players_df.columns:
        known_ids = set(players_df["player_id"].dropna().astype(int))
        app_ids = set(df["player_id"].dropna().astype(int))
        orphans = app_ids - known_ids
        report.check(
            artifact, "player_id_in_players_index",
            len(orphans) == 0,
            fail_detail=f"{len(orphans)} player_ids not found in players.csv: {list(orphans)[:5]}",
        )

    # FK: match_id exists in raw
    if raw_match_ids:
        app_match_ids = set(df["match_id"].dropna().astype(str))
        orphan_matches = app_match_ids - raw_match_ids
        report.check(
            artifact, "match_id_exists_in_raw",
            len(orphan_matches) == 0,
            fail_detail=f"{len(orphan_matches)} match_ids not found in data/raw/: {list(orphan_matches)[:5]}",
        )

    return df


def validate_player_appearances_csv(
    report: Report,
    parquet_df: pd.DataFrame | None,
) -> None:
    artifact = "data/derived/player_appearances.csv"
    path = DERIVED / "player_appearances.csv"
    print(f"\n--- {artifact} ---")

    df = load_csv(path, report, artifact)
    if df is None:
        return

    required_cols = [
        "player_id", "player_name", "player_slug", "match_id",
        "season", "realm", "competition_slug", "match_date",
        "home_team_name", "away_team_name", "team", "side",
    ]
    check_columns(df, required_cols, report, artifact)
    check_no_duplicates(df, ["player_id", "match_id"], report, artifact, "no_duplicate_player_match")
    check_values_in_set(df, "side", {"home", "away"}, report, artifact)

    # Row count should match parquet
    if parquet_df is not None:
        report.check(
            artifact, "row_count_matches_parquet",
            len(df) == len(parquet_df),
            fail_detail=f"CSV has {len(df):,} rows, parquet has {len(parquet_df):,} rows",
        )


def validate_player_incidents(
    report: Report,
    players_df: pd.DataFrame | None,
    raw_match_ids: set[str],
) -> None:
    artifact = "data/derived/player_incidents.parquet"
    path = DERIVED / "player_incidents.parquet"
    print(f"\n--- {artifact} ---")

    df = load_parquet(path, report, artifact)
    if df is None:
        return

    required_cols = [
        "match_id", "player_id", "player_name", "incidentType", "incidentClass",
        "time", "season", "competition_slug", "match_date_utc",
    ]
    check_columns(df, required_cols, report, artifact)
    check_not_null(df, ["match_id", "incidentType", "time"], report, artifact)

    known_incident_types = {"card", "goal", "varDecision", "inGamePenalty"}
    check_values_in_set(df, "incidentType", known_incident_types, report, artifact)

    if "time" in df.columns:
        # Sofascore uses negative time (e.g. -5) for pre-match incidents such
        # as accumulated-booking cards; allow down to -10.
        check_numeric_range(df, "time", -10, 200, report, artifact)

    # FK: player_id in players index (nullable — some incidents may have no linked player)
    if players_df is not None and "player_id" in df.columns and "player_id" in players_df.columns:
        known_ids = set(players_df["player_id"].dropna().astype(int))
        # Only check non-null player_ids
        incident_ids = set(df["player_id"].dropna().astype(int))
        orphans = incident_ids - known_ids
        report.check(
            artifact, "player_id_in_players_index",
            len(orphans) == 0,
            fail_detail=f"{len(orphans)} player_ids not found in players.csv: {list(orphans)[:5]}",
        )

    # FK: match_id in raw
    if raw_match_ids:
        inc_match_ids = set(df["match_id"].dropna().astype(str))
        orphan_matches = inc_match_ids - raw_match_ids
        report.check(
            artifact, "match_id_exists_in_raw",
            len(orphan_matches) == 0,
            fail_detail=f"{len(orphan_matches)} match_ids not found in data/raw/: {list(orphan_matches)[:5]}",
        )

    if "period" in df.columns:
        check_values_in_set(df, "period", {"period1", "period2", None, float("nan")}, report, artifact)


def validate_per_player_csvs(
    report: Report,
    players_df: pd.DataFrame | None,
    appearances_df: pd.DataFrame | None,
) -> None:
    players_dir = DERIVED / "players"
    print(f"\n--- data/derived/players/*.csv ---")

    if not players_dir.exists():
        report.record("data/derived/players/", "directory_exists", False, "directory not found")
        return

    csv_files = sorted(players_dir.glob("*.csv"))
    report.record("data/derived/players/", "directory_exists", True, f"{len(csv_files)} CSV files found")
    if not csv_files:
        return

    # Build lookup of slug -> player_id from players index
    slug_to_id: dict[str, int] = {}
    if players_df is not None and "player_slug" in players_df.columns and "player_id" in players_df.columns:
        for _, row in players_df.dropna(subset=["player_slug", "player_id"]).iterrows():
            slug_to_id[str(row["player_slug"])] = int(row["player_id"])

    # Only apply strict schema/slug/player_id checks to main per-player files: {slug}.csv
    # Files named {slug}_appearances.csv or {slug}_incidents.csv are legacy/alternate format (different schema).
    required_cols = [
        "player_id", "player_slug", "match_id", "side", "team",
        "season", "competition_slug", "match_date",
    ]

    errors: list[str] = []
    files_ok = 0

    for csv_path in csv_files:
        stem = csv_path.stem
        is_appearances_suffix = stem.endswith("_appearances")
        is_incidents_suffix = stem.endswith("_incidents")
        is_main_file = not is_appearances_suffix and not is_incidents_suffix
        slug = stem.replace("_appearances", "").replace("_incidents", "") if (is_appearances_suffix or is_incidents_suffix) else stem

        try:
            df = pd.read_csv(csv_path, low_memory=False)
        except Exception as exc:
            errors.append(f"{csv_path.name}: unreadable — {exc}")
            continue

        file_ok = True

        if is_incidents_suffix:
            # One row per incident; duplicate match_id is expected. Only check prefix is known slug.
            if slug not in slug_to_id and slug_to_id:
                errors.append(f"{csv_path.name}: prefix '{slug}' not in players index")
                file_ok = False
            if "match_id" not in df.columns:
                errors.append(f"{csv_path.name}: missing match_id")
                file_ok = False
        elif is_appearances_suffix:
            # Same schema as main file; require prefix match and no duplicate match_id
            if slug not in slug_to_id and slug_to_id:
                errors.append(f"{csv_path.name}: prefix '{slug}' not in players index")
                file_ok = False
            if "match_id" in df.columns and df["match_id"].duplicated().any():
                n = df["match_id"].duplicated().sum()
                errors.append(f"{csv_path.name}: {n} duplicate match_id rows")
                file_ok = False
            if "player_id" in df.columns and slug in slug_to_id:
                expected_id = slug_to_id[slug]
                ids_in_file = df["player_id"].dropna().unique().tolist()
                if len(ids_in_file) == 1 and int(ids_in_file[0]) != expected_id:
                    errors.append(f"{csv_path.name}: player_id {ids_in_file[0]} doesn't match index ({expected_id})")
                    file_ok = False
        else:
            # Main file: {slug}.csv — full checks
            missing = [c for c in required_cols if c not in df.columns]
            if missing:
                errors.append(f"{csv_path.name}: missing columns {missing}")
                file_ok = False

            if "match_id" in df.columns and df["match_id"].duplicated().any():
                n = df["match_id"].duplicated().sum()
                errors.append(f"{csv_path.name}: {n} duplicate match_id rows")
                file_ok = False

            if "player_slug" in df.columns:
                slugs = df["player_slug"].dropna().unique().tolist()
                if len(slugs) != 1 or slugs[0] != stem:
                    errors.append(f"{csv_path.name}: player_slug values {slugs} don't match filename '{stem}'")
                    file_ok = False

            if "player_id" in df.columns and stem in slug_to_id:
                expected_id = slug_to_id[stem]
                ids_in_file = df["player_id"].dropna().unique().tolist()
                if len(ids_in_file) == 1 and int(ids_in_file[0]) != expected_id:
                    errors.append(f"{csv_path.name}: player_id {ids_in_file[0]} doesn't match index ({expected_id})")
                    file_ok = False

            if "side" in df.columns:
                bad_sides = set(df["side"].dropna().unique()) - {"home", "away"}
                if bad_sides:
                    errors.append(f"{csv_path.name}: unexpected side values {bad_sides}")
                    file_ok = False

        if file_ok:
            files_ok += 1

    n = len(csv_files)
    report.check(
        "data/derived/players/*.csv",
        "all_files_valid",
        len(errors) == 0,
        fail_detail=f"{n - files_ok}/{n} files have issues",
    )
    if errors:
        print(f"    Per-player file issues ({len(errors)} total, first 20 shown):")
        for e in errors[:20]:
            print(f"      - {e}")
        if len(errors) > 20:
            print(f"      ... and {len(errors) - 20} more")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate Sofascore project data artifacts.")
    parser.add_argument("--verbose", "-v", action="store_true", help="Print all checks, not just failures.")
    parser.add_argument("--fail-fast", action="store_true", help="Stop at first failure.")
    args = parser.parse_args()

    report = Report(verbose=args.verbose, fail_fast=args.fail_fast)

    print("Collecting raw match IDs (this may take a moment)...")
    raw_match_ids = get_raw_match_ids()
    print(f"Found {len(raw_match_ids):,} match directories in data/raw/")

    # --- Index ---
    players_df = validate_players_index(report)
    validate_extraction_progress(report)
    validate_matches_index(report)
    validate_quality_report(report)

    # --- Derived ---
    appearances_df = validate_player_appearances(report, players_df, raw_match_ids)
    validate_player_appearances_csv(report, appearances_df)
    validate_player_incidents(report, players_df, raw_match_ids)
    validate_per_player_csvs(report, players_df, appearances_df)

    report.print_summary()

    failed = sum(1 for r in report.results if not r.passed)
    sys.exit(0 if failed == 0 else 1)


if __name__ == "__main__":
    main()
