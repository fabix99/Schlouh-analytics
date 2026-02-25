"""Bootstrap football.db from parquet/CSV for AI Scout RAG. Read-only usage in app."""

from __future__ import annotations

import pathlib
import sqlite3

import pandas as pd

_PROJECT_ROOT = pathlib.Path(__file__).parent.parent.parent
_DB_PATH = _PROJECT_ROOT / "data" / "football.db"


def get_db_path() -> pathlib.Path:
    """Return path to football.db (may not exist yet)."""
    return _DB_PATH


def ensure_football_db() -> pathlib.Path:
    """
    Create football.db from parquet/CSV if it does not exist.
    Uses read-only-friendly tables: player_season_stats, team_season_stats,
    match_summary, players_index.
    Returns path to football.db.
    """
    if _DB_PATH.exists():
        return _DB_PATH

    _DB_PATH.parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(str(_DB_PATH))

    try:
        # Player season stats (main scouting table)
        pstats = _PROJECT_ROOT / "data/processed/03_player_season_stats.parquet"
        if pstats.exists():
            df = pd.read_parquet(pstats)
            # Limit columns for smaller DB; keep names and key stats for RAG
            cols = [c for c in ["player_id", "player_name", "season", "competition_slug", "player_position",
                                "appearances", "total_minutes", "avg_rating", "goals", "assists",
                                "expectedGoals_per90", "expectedAssists_per90"] if c in df.columns]
            if cols:
                df[cols].to_sql("player_season_stats", conn, index=False, if_exists="replace")

        # Team lookup for player_season_stats (player -> team)
        lookup_path = _PROJECT_ROOT / "data/derived/player_appearances.parquet"
        if lookup_path.exists():
            import pyarrow.parquet as pq
            pf = pq.read_table(lookup_path, columns=["player_id", "season", "competition_slug", "team"])
            lookup = pf.to_pandas()
            lookup = lookup.groupby(["player_id", "season", "competition_slug"])["team"].agg(
                lambda x: x.mode().iloc[0] if len(x) > 0 else "Unknown"
            ).reset_index()
            lookup.to_sql("player_team_lookup", conn, index=False, if_exists="replace")

        # Team season stats
        tstats = _PROJECT_ROOT / "data/processed/01_team_season_stats.parquet"
        if tstats.exists():
            df = pd.read_parquet(tstats)
            cols = [c for c in ["team_name", "season", "competition_slug", "matches_total",
                                "xg_for_total", "xg_against_total"] if c in df.columns]
            if not cols:
                cols = list(df.columns)[:15]
            df[cols].to_sql("team_season_stats", conn, index=False, if_exists="replace")

        # Match summary (teams, scores)
        msum = _PROJECT_ROOT / "data/processed/02_match_summary.parquet"
        if msum.exists():
            df = pd.read_parquet(msum)
            cols = [c for c in ["match_id", "season", "competition_slug", "match_date_utc", "home_team_name",
                                "away_team_name", "home_score", "away_score", "home_xg", "away_xg"] if c in df.columns]
            if cols:
                df[cols].to_sql("match_summary", conn, index=False, if_exists="replace")

        # Players index (names for search)
        players_csv = _PROJECT_ROOT / "data/index/players.csv"
        if players_csv.exists():
            df = pd.read_csv(players_csv, usecols=["player_id", "player_name", "player_shortName"])
            if not df.empty:
                df.to_sql("players_index", conn, index=False, if_exists="replace")
    except Exception:
        conn.close()
        if _DB_PATH.exists():
            _DB_PATH.unlink()
        raise
    finally:
        conn.close()

    return _DB_PATH
