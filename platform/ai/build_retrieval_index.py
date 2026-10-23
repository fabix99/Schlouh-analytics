#!/usr/bin/env python3
"""
Build an AI/RAG-ready retrieval index from dbt marts in DuckDB.

This is the "bridge to AI Lab" layer: structured warehouse marts → searchable
documents. Uses DuckDB FTS (no external LLM required). Downstream you can swap
the retriever for embeddings / an agent while keeping the same document table.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import duckdb

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_WAREHOUSE = ROOT / "data" / "warehouse" / "schlouh.duckdb"


def warehouse_path() -> Path:
    env = os.environ.get("SOFASCORE_WAREHOUSE_PATH")
    if env:
        p = Path(env)
        return p if p.is_absolute() else ROOT / p
    return DEFAULT_WAREHOUSE


def main() -> int:
    path = warehouse_path()
    if not path.exists():
        print(f"Warehouse missing: {path}", file=sys.stderr)
        print("Run the platform pipeline first.", file=sys.stderr)
        return 1

    con = duckdb.connect(str(path))
    con.execute("INSTALL fts")
    con.execute("LOAD fts")
    con.execute("CREATE SCHEMA IF NOT EXISTS ai")

    con.execute("DROP TABLE IF EXISTS ai.retrieval_documents")
    con.execute(
        """
        CREATE TABLE ai.retrieval_documents AS
        SELECT
            'player:' || cast(player_id as varchar) AS doc_id,
            'player_profile' AS doc_type,
            cast(player_id as varchar) AS entity_id,
            player_name AS title,
            trim(
                coalesce(player_name, '') || ' | pos ' || coalesce(player_position, '?') ||
                ' | minutes ' || coalesce(cast(total_minutes as varchar), '0') ||
                ' | goals ' || coalesce(cast(goals as varchar), '0') ||
                ' | assists ' || coalesce(cast(assists as varchar), '0') ||
                ' | latest ' || coalesce(latest_season, '') || ' ' || coalesce(latest_competition, '') ||
                ' | rating ' || coalesce(cast(round(latest_rating, 2) as varchar), 'n/a')
            ) AS content
        FROM analytics_marts.mart_player_scouting_profiles

        UNION ALL

        SELECT
            'match:' || match_id AS doc_id,
            'match_summary' AS doc_type,
            match_id AS entity_id,
            home_team_name || ' vs ' || away_team_name AS title,
            trim(
                coalesce(home_team_name, '') || ' vs ' || coalesce(away_team_name, '') ||
                ' | ' || coalesce(season, '') || ' ' || coalesce(competition_slug, '') ||
                ' | score ' || coalesce(cast(home_score as varchar), '?') || '-' ||
                coalesce(cast(away_score as varchar), '?') ||
                ' | result ' || coalesce(result, '') ||
                ' | venue ' || coalesce(venue_name, '') || ' ' || coalesce(venue_city, '') ||
                ' | referee ' || coalesce(referee_name, '')
            ) AS content
        FROM analytics_marts.mart_match_summary
        """
    )

    n = con.execute("SELECT count(*) FROM ai.retrieval_documents").fetchone()[0]
    con.execute(
        "PRAGMA create_fts_index('ai.retrieval_documents', 'doc_id', 'title', 'content', overwrite=1)"
    )

    sample = con.execute(
        "SELECT doc_type, count(*) FROM ai.retrieval_documents GROUP BY 1 ORDER BY 1"
    ).fetchall()
    print(f"OK documents={n} breakdown={sample}")
    print(f"OK warehouse={path}")
    print("OK schema=ai.retrieval_documents + FTS index")
    con.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
