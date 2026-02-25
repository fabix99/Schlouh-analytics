"""
Build player-level derived data from raw match data.

Reads all data/raw/{season}/{realm}/{competition_slug}/{match_id}/lineups.csv
and incidents.csv, joins with data/index/matches.csv for match metadata,
and writes:

  - data/derived/player_appearances.parquet   one row per player per match (all stats + match context)
  - data/derived/player_incidents.parquet      one row per incident involving a player (goals, cards, etc.)
  - data/derived/match_scores.parquet          one row per match with home_score, away_score (from incidents FT row)
  - data/index/players.csv                     unique players with id, name, slug, appearance count

Usage:
  python src/build_player_appearances.py
  python src/build_player_appearances.py --csv   also write player_appearances.csv for compatibility
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import pandas as pd

from config import DERIVED_DIR, INDEX_DIR, INDEX_PATH, RAW_BASE, ROOT

PLAYERS_INDEX_PATH = INDEX_DIR / "players.csv"

# Plausible Unix seconds range (2001-01-01 to 2033-12-31) to avoid overflow in to_datetime
MATCH_DATE_MIN = 978_307_200
MATCH_DATE_MAX = 2_019_513_599


def _safe_match_date_to_utc(series: pd.Series) -> pd.Series:
    """Convert match_date (Unix s or ms) to timezone-aware datetime; invalid/overflow -> NaT."""
    s = pd.to_numeric(series, errors="coerce")
    # If values look like milliseconds (>= 1e12), convert to seconds
    s = s.where(s < 1e12, s / 1000.0)
    # Clamp to plausible range to avoid FloatingPointError in pandas/numpy
    s = s.clip(lower=MATCH_DATE_MIN, upper=MATCH_DATE_MAX)
    # Use int64 for seconds so pd.to_datetime(unit="s") doesn't overflow internally
    s = s.astype("Int64")  # nullable int; NaN preserved
    # Convert via timestamps one-by-one to avoid numpy/pandas overflow in vectorized path
    def _one(sec):
        if pd.isna(sec) or sec < MATCH_DATE_MIN or sec > MATCH_DATE_MAX:
            return pd.NaT
        try:
            return pd.Timestamp(int(sec), unit="s", tz="UTC")
        except (OverflowError, ValueError):
            return pd.NaT

    return s.map(_one)


# Match columns to attach to each appearance (for viz: date, round, opponents)
MATCH_COLUMNS = [
    "match_date",
    "round",
    "home_team_id",
    "home_team_name",
    "away_team_id",
    "away_team_name",
    "status_code",
    "status_type",
]


def load_matches_index() -> pd.DataFrame:
    """Load matches index and normalize match_id to string for joins."""
    if not INDEX_PATH.exists():
        return pd.DataFrame()
    df = pd.read_csv(INDEX_PATH)
    df["match_id"] = df["match_id"].astype(str)
    return df


def iter_match_dirs():
    """Yield (season, realm, competition_slug, match_dir) for every match folder that has lineups.csv."""
    if not RAW_BASE.exists():
        return
    for season_dir in sorted(RAW_BASE.iterdir()):
        if not season_dir.is_dir() or season_dir.name.startswith("."):
            continue
        season = season_dir.name
        for realm_dir in sorted(season_dir.iterdir()):
            if not realm_dir.is_dir() or realm_dir.name.startswith("."):
                continue
            realm = realm_dir.name
            for comp_dir in sorted(realm_dir.iterdir()):
                if not comp_dir.is_dir() or comp_dir.name.startswith("."):
                    continue
                competition_slug = comp_dir.name
                for match_dir in sorted(comp_dir.iterdir()):
                    if not match_dir.is_dir() or match_dir.name.startswith("."):
                        continue
                    lineups_path = match_dir / "lineups.csv"
                    if lineups_path.exists():
                        yield season, realm, competition_slug, match_dir


def build_player_appearances(matches: pd.DataFrame, also_csv: bool = False) -> pd.DataFrame:
    """Read all lineups, enrich with match metadata, return one DataFrame."""
    rows = []
    match_id_str = matches.set_index("match_id") if not matches.empty else pd.DataFrame()

    for season, realm, competition_slug, match_dir in iter_match_dirs():
        match_id = match_dir.name
        lineups_path = match_dir / "lineups.csv"
        try:
            df = pd.read_csv(lineups_path)
        except Exception as e:
            print(f"  WARN skip {lineups_path}: {e}", file=sys.stderr)
            continue

        if df.empty:
            continue

        # Normalize match_id in lineups for join
        df["match_id"] = df["match_id"].astype(str)

        # Add path-derived columns
        df["season"] = season
        df["realm"] = realm
        df["competition_slug"] = competition_slug

        # Join match metadata (date, round, opponents) in one assign
        if not match_id_str.empty and match_id in match_id_str.index:
            meta = match_id_str.loc[match_id]
            extra = {col: meta[col] for col in MATCH_COLUMNS if col in meta.index}
            if extra:
                df = df.assign(**extra)
        rows.append(df)

    if not rows:
        return pd.DataFrame()

    out = pd.concat(rows, ignore_index=True)

    # Ensure player_id is consistent type (numeric where possible)
    if "player_id" in out.columns:
        out["player_id"] = pd.to_numeric(out["player_id"], errors="coerce")

    # Add human-readable match date for viz (match_date is Unix timestamp, possibly ms)
    if "match_date" in out.columns:
        out = out.assign(match_date_utc=_safe_match_date_to_utc(out["match_date"]))

    return out


def build_player_incidents(matches: pd.DataFrame) -> pd.DataFrame:
    """Read all incidents, keep rows with player_id, add match metadata."""
    rows = []
    match_id_str = matches.set_index("match_id") if not matches.empty else pd.DataFrame()

    for season, realm, competition_slug, match_dir in iter_match_dirs():
        match_id = match_dir.name
        incidents_path = match_dir / "incidents.csv"
        if not incidents_path.exists():
            continue
        try:
            df = pd.read_csv(incidents_path)
        except Exception as e:
            print(f"  WARN skip {incidents_path}: {e}", file=sys.stderr)
            continue

        if df.empty:
            continue

        # Keep only rows that have a player (goals, cards, etc.)
        if "player_id" not in df.columns:
            continue
        df = df.dropna(subset=["player_id"]).copy()
        if df.empty:
            continue

        df["match_id"] = df["match_id"].astype(str)
        df["season"] = season
        df["realm"] = realm
        df["competition_slug"] = competition_slug

        if not match_id_str.empty and match_id in match_id_str.index:
            meta = match_id_str.loc[match_id]
            extra = {col: meta[col] for col in MATCH_COLUMNS if col in meta.index}
            if extra:
                df = df.assign(**extra)
        rows.append(df)

    if not rows:
        return pd.DataFrame()

    out = pd.concat(rows, ignore_index=True)
    out["player_id"] = pd.to_numeric(out["player_id"], errors="coerce")
    if "match_date" in out.columns:
        out = out.assign(match_date_utc=_safe_match_date_to_utc(out["match_date"]))
    return out


def build_match_scores() -> pd.DataFrame:
    """Build one row per match with final score from incidents.csv FT row.
    Returns DataFrame with columns: match_id, home_score, away_score (match_id as string).
    """
    rows = []
    for season, realm, competition_slug, match_dir in iter_match_dirs():
        match_id = match_dir.name
        incidents_path = match_dir / "incidents.csv"
        if not incidents_path.exists():
            continue
        try:
            df = pd.read_csv(incidents_path)
        except Exception as e:
            print(f"  WARN skip {incidents_path}: {e}", file=sys.stderr)
            continue
        if df.empty:
            continue
        # Find full-time row: incidentType == "period" and time == 90 (or last row with homeScore/awayScore)
        if "incidentType" in df.columns and "time" in df.columns:
            ft = df[(df["incidentType"] == "period") & (df["time"] == 90)]
        else:
            ft = pd.DataFrame()
        if ft.empty and "homeScore" in df.columns:
            # Fallback: last row with non-null homeScore
            with_score = df[df["homeScore"].notna()]
            ft = with_score.tail(1) if not with_score.empty else pd.DataFrame()
        if ft.empty:
            continue
        row = ft.iloc[0]
        home = row.get("homeScore")
        away = row.get("awayScore")
        if pd.isna(home) or pd.isna(away):
            continue
        try:
            home_int = int(float(home))
            away_int = int(float(away))
        except (ValueError, TypeError):
            continue
        rows.append({"match_id": str(match_id), "home_score": home_int, "away_score": away_int})
    if not rows:
        return pd.DataFrame()
    return pd.DataFrame(rows)


def build_players_index(appearances: pd.DataFrame, incidents: pd.DataFrame = None) -> pd.DataFrame:
    """One row per player: id, name, slug, appearance count, first/last match, competitions.
    Includes players that appear only in incidents (no lineup row) so the index stays referentially complete.
    """
    players_from_appearances = pd.DataFrame()
    if not appearances.empty and "player_id" in appearances.columns:
        agg = appearances.groupby("player_id", dropna=False).agg(
            player_name=("player_name", "first"),
            player_slug=("player_slug", "first"),
            player_shortName=("player_shortName", "first"),
            n_matches=("match_id", "nunique"),
            first_match_id=("match_id", "min"),
            last_match_id=("match_id", "max"),
            competitions=("competition_slug", lambda s: ",".join(sorted(s.dropna().unique()))),
            seasons=("season", lambda s: ",".join(sorted(s.dropna().unique()))),
        ).reset_index()
        players_from_appearances = agg

    if incidents is None or incidents.empty or "player_id" not in incidents.columns:
        return players_from_appearances

    # Add players that appear in incidents but never in lineups (e.g. sent off before appearing)
    incident_ids = set(incidents["player_id"].dropna().astype(int))
    appearance_ids = set(players_from_appearances["player_id"].dropna().astype(int)) if not players_from_appearances.empty else set()
    only_in_incidents = incident_ids - appearance_ids
    if not only_in_incidents:
        return players_from_appearances

    inc = incidents[incidents["player_id"].isin(only_in_incidents)].copy()
    inc_agg = inc.groupby("player_id").agg(
        player_name=("player_name", "first"),
        n_matches=("match_id", "nunique"),
        first_match_id=("match_id", "min"),
        last_match_id=("match_id", "max"),
        competitions=("competition_slug", lambda s: ",".join(sorted(s.dropna().unique()))),
        seasons=("season", lambda s: ",".join(sorted(s.dropna().unique()))),
    ).reset_index()
    inc_agg["player_slug"] = inc_agg["player_id"].apply(lambda x: f"player-{int(x)}")
    inc_agg["player_shortName"] = inc_agg["player_name"]
    # n_matches = number of matches in which they had an incident (no lineup row)

    players = pd.concat([players_from_appearances, inc_agg], ignore_index=True)
    return players


def main():
    parser = argparse.ArgumentParser(description="Build player-level derived data from raw matches.")
    parser.add_argument("--csv", action="store_true", help="Also write player_appearances.csv")
    args = parser.parse_args()

    print("Loading matches index...")
    matches = load_matches_index()
    print(f"  {len(matches)} matches in index")

    print("Building player appearances from raw lineups...")
    appearances = build_player_appearances(matches, also_csv=args.csv)
    if appearances.empty:
        print("  No lineup data found. Ensure data/raw/{season}/{realm}/{competition}/{match_id}/lineups.csv exist.")
        sys.exit(1)
    print(f"  {len(appearances)} rows ({appearances['match_id'].nunique()} matches)")

    print("Building player incidents...")
    incidents = build_player_incidents(matches)
    if not incidents.empty:
        print(f"  {len(incidents)} incident rows with player_id")
    else:
        print("  No player incidents found")

    print("Building match scores from incidents...")
    match_scores = build_match_scores()
    if not match_scores.empty:
        print(f"  {len(match_scores)} matches with score")
    else:
        print("  No match scores found (incidents may lack FT row)")

    print("Building players index...")
    players = build_players_index(appearances, incidents)
    if not players.empty:
        print(f"  {len(players)} unique players")

    DERIVED_DIR.mkdir(parents=True, exist_ok=True)

    # Ensure string columns have no NaN for parquet (PyArrow expects bytes or null-capable type)
    for col in appearances.select_dtypes(include=["object"]).columns:
        appearances[col] = appearances[col].fillna("").astype(str)

    # Write derived outputs
    app_path = DERIVED_DIR / "player_appearances.parquet"
    appearances.to_parquet(app_path, index=False)
    print(f"Wrote {app_path}")

    if args.csv:
        app_csv = DERIVED_DIR / "player_appearances.csv"
        appearances.to_csv(app_csv, index=False)
        print(f"Wrote {app_csv}")

    if not incidents.empty:
        inc_path = DERIVED_DIR / "player_incidents.parquet"
        incidents.to_parquet(inc_path, index=False)
        print(f"Wrote {inc_path}")

    if not match_scores.empty:
        ms_path = DERIVED_DIR / "match_scores.parquet"
        match_scores.to_parquet(ms_path, index=False)
        print(f"Wrote {ms_path}")

    if not players.empty:
        PLAYERS_INDEX_PATH.parent.mkdir(parents=True, exist_ok=True)
        players.to_csv(PLAYERS_INDEX_PATH, index=False)
        print(f"Wrote {PLAYERS_INDEX_PATH}")

    print("Done.")


if __name__ == "__main__":
    main()
