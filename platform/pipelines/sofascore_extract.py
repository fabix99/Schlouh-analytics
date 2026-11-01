#!/usr/bin/env python3
"""
DLT extract source: Sofascore API → DuckDB (and optionally data/raw/ for legacy builds).

Reuses resilient HTTP helpers from src/extract_match_lineups.py. This is the
platform-native extract path (Python + DLT resources), complementary to
extract_batch.py which writes the file lake.

Usage (from project root):
  python platform/pipelines/sofascore_extract.py \\
    --competition england-premier-league --season 2025-26 --limit 2
  python platform/pipelines/sofascore_extract.py \\
    --match-id 14083327 --also-write-raw
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path
from typing import Any, Iterator, Optional

import dlt
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from config import API_BASE, INDEX_PATH, RAW_BASE  # noqa: E402
from extract_match_lineups import (  # noqa: E402
    fetch_json_resilient,
    flatten_player,
    get_team_name,
)

os.environ.setdefault("SCHEMA__NAMING", "direct")

DEFAULT_WAREHOUSE = ROOT / "data" / "warehouse" / "schlouh.duckdb"
DATASET_NAME = "raw_sofascore_api"


def _warehouse_path() -> Path:
    env = os.environ.get("SOFASCORE_WAREHOUSE_PATH")
    if env:
        p = Path(env)
        return p if p.is_absolute() else ROOT / p
    return DEFAULT_WAREHOUSE


def _select_matches(
    competition: Optional[str],
    season: Optional[str],
    match_ids: list[str],
    limit: Optional[int],
) -> pd.DataFrame:
    if match_ids:
        rows = [{"match_id": m, "season": season or "", "competition_slug": competition or "", "realm": "club"} for m in match_ids]
        return pd.DataFrame(rows)

    if not INDEX_PATH.exists():
        raise FileNotFoundError(f"Index not found: {INDEX_PATH}. Run discover_matches first.")
    df = pd.read_csv(INDEX_PATH)
    df["match_id"] = df["match_id"].astype(str)
    if competition:
        df = df[df["competition_slug"] == competition]
    if season:
        df = df[df["season"] == season]
    if "status_type" in df.columns:
        finished = df[df["status_type"].astype(str).str.lower() == "finished"]
        if not finished.empty:
            df = finished
    if df.empty:
        raise SystemExit(f"No matches for competition={competition!r} season={season!r}")
    if limit:
        df = df.sort_values("match_date", ascending=False).head(limit)
    return df.reset_index(drop=True)


def _lineup_rows(event_id: str, event: dict, lineups: dict) -> list[dict]:
    rows: list[dict] = []
    for side, key in (("home", "home"), ("away", "away")):
        team_block = lineups.get(key) or {}
        team_name = ""
        if isinstance(team_block.get("team"), dict):
            team_name = (team_block["team"].get("name") or team_block["team"].get("shortName")) or ""
        if not team_name:
            team_name = get_team_name(event, side)
        for p in team_block.get("players") or []:
            rows.append(flatten_player(p, side, team_name, event_id))
    if rows:
        return rows
    for side, key in (("home", "homeTeam"), ("away", "awayTeam")):
        team_block = lineups.get(key) or {}
        team_name = (team_block.get("name") or team_block.get("shortName")) or get_team_name(event, side)
        for p in team_block.get("players") or team_block.get("lineup") or []:
            rows.append(flatten_player(p, side, team_name, event_id))
    return rows


def _incident_rows(event_id: str, payload: dict) -> list[dict]:
    rows = []
    for inc in payload.get("incidents") or []:
        row: dict[str, Any] = {"match_id": event_id}
        for k, v in inc.items():
            if isinstance(v, (dict, list)):
                continue
            row[k] = v
        if isinstance(inc.get("player"), dict):
            row["player_id"] = inc["player"].get("id")
            row["player_name"] = inc["player"].get("name")
        rows.append(row)
    return rows


def _stat_rows(event_id: str, payload: dict) -> list[dict]:
    rows = []
    for period_block in payload.get("statistics") or []:
        period = period_block.get("period") or "ALL"
        for group in period_block.get("groups") or []:
            group_name = group.get("groupName") or group.get("name") or ""
            for stat in group.get("statisticsItems") or group.get("items") or []:
                if not isinstance(stat, dict):
                    continue
                rows.append(
                    {
                        "match_id": event_id,
                        "period": period,
                        "group": group_name,
                        "name": stat.get("name"),
                        "home": stat.get("home") or stat.get("homeValue"),
                        "away": stat.get("away") or stat.get("awayValue"),
                    }
                )
    return rows


def _event_flat(event_id: str, event: dict, meta: dict) -> dict:
    inner = event.get("event") if isinstance(event.get("event"), dict) else event
    home = (inner.get("homeTeam") or {}) if isinstance(inner, dict) else {}
    away = (inner.get("awayTeam") or {}) if isinstance(inner, dict) else {}
    score = (inner.get("homeScore") or {}) if isinstance(inner, dict) else {}
    ascore = (inner.get("awayScore") or {}) if isinstance(inner, dict) else {}
    return {
        "match_id": event_id,
        "season": meta.get("season"),
        "competition_slug": meta.get("competition_slug"),
        "realm": meta.get("realm", "club"),
        "home_team_id": home.get("id"),
        "home_team_name": home.get("name") or home.get("shortName"),
        "away_team_id": away.get("id"),
        "away_team_name": away.get("name") or away.get("shortName"),
        "home_score": score.get("current") if isinstance(score, dict) else None,
        "away_score": ascore.get("current") if isinstance(ascore, dict) else None,
        "status_type": ((inner.get("status") or {}) if isinstance(inner, dict) else {}).get("type"),
        "match_date": (inner.get("startTimestamp") if isinstance(inner, dict) else None),
        "round": ((inner.get("roundInfo") or {}) if isinstance(inner, dict) else {}).get("round"),
    }


def _write_raw_files(
    match_id: str,
    meta: dict,
    event: dict,
    lineup_rows: list[dict],
    incident_rows: list[dict],
    stat_rows: list[dict],
) -> Path:
    season = meta.get("season") or "unknown"
    realm = meta.get("realm") or "club"
    comp = meta.get("competition_slug") or "unknown"
    match_dir = RAW_BASE / str(season) / str(realm) / str(comp) / str(match_id)
    match_dir.mkdir(parents=True, exist_ok=True)
    (match_dir / "event.json").write_text(json.dumps(event, indent=2, ensure_ascii=False), encoding="utf-8")
    if lineup_rows:
        pd.DataFrame(lineup_rows).to_csv(match_dir / "lineups.csv", index=False)
    if incident_rows:
        pd.DataFrame(incident_rows).to_csv(match_dir / "incidents.csv", index=False)
    if stat_rows:
        pd.DataFrame(stat_rows).to_csv(match_dir / "team_statistics.csv", index=False)
    return match_dir


def fetch_match_bundle(match_id: str, meta: dict, delay: float) -> dict[str, Any]:
    """Fetch one match from Sofascore; returns tables + optional error."""
    event, err = fetch_json_resilient(f"{API_BASE}/event/{match_id}")
    if err or not event:
        return {"match_id": match_id, "error": err or "empty_event", "events": [], "lineups": [], "incidents": [], "team_statistics": []}

    time.sleep(delay)
    lineups, lerr = fetch_json_resilient(f"{API_BASE}/event/{match_id}/lineups")
    lineup_rows = _lineup_rows(match_id, event, lineups or {}) if lineups else []
    if lerr and not lineup_rows:
        return {
            "match_id": match_id,
            "error": f"lineups:{lerr}",
            "events": [_event_flat(match_id, event, meta)],
            "lineups": [],
            "incidents": [],
            "team_statistics": [],
        }

    time.sleep(delay)
    incidents_payload, _ = fetch_json_resilient(f"{API_BASE}/event/{match_id}/incidents")
    incident_rows = _incident_rows(match_id, incidents_payload or {})

    time.sleep(delay)
    stats_payload, _ = fetch_json_resilient(f"{API_BASE}/event/{match_id}/statistics")
    stat_rows = _stat_rows(match_id, stats_payload or {})

    # Attach season/comp onto lineups for warehouse joins
    for row in lineup_rows:
        row["season"] = meta.get("season")
        row["competition_slug"] = meta.get("competition_slug")
        row["realm"] = meta.get("realm", "club")

    for row in incident_rows:
        row["season"] = meta.get("season")
        row["competition_slug"] = meta.get("competition_slug")

    return {
        "match_id": match_id,
        "error": None,
        "events": [_event_flat(match_id, event, meta)],
        "lineups": lineup_rows,
        "incidents": incident_rows,
        "team_statistics": stat_rows,
        "_raw_event": event,
    }


@dlt.source(name="sofascore_api")
def sofascore_api(
    matches: pd.DataFrame,
    delay: float = 0.5,
    also_write_raw: bool = False,
):
    """DLT resources for live Sofascore extract."""

    bundles: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []

    for _, row in matches.iterrows():
        match_id = str(row["match_id"])
        meta = {
            "season": row.get("season"),
            "competition_slug": row.get("competition_slug"),
            "realm": row.get("realm", "club") or "club",
        }
        print(f"extract {match_id} ({meta.get('competition_slug')} {meta.get('season')})")
        bundle = fetch_match_bundle(match_id, meta, delay=delay)
        if bundle.get("error"):
            errors.append({"match_id": match_id, "error": bundle["error"], **meta})
            print(f"  FAIL {bundle['error']}")
        else:
            print(
                f"  OK lineups={len(bundle['lineups'])} incidents={len(bundle['incidents'])} stats={len(bundle['team_statistics'])}"
            )
        if also_write_raw and bundle.get("_raw_event"):
            path = _write_raw_files(
                match_id,
                meta,
                bundle["_raw_event"],
                bundle["lineups"],
                bundle["incidents"],
                bundle["team_statistics"],
            )
            print(f"  raw → {path.relative_to(ROOT)}")
        bundles.append(bundle)

    @dlt.resource(name="api_events", write_disposition="merge", primary_key="match_id")
    def api_events() -> Iterator[dict]:
        for b in bundles:
            for row in b["events"]:
                yield row

    @dlt.resource(name="api_lineups", write_disposition="append")
    def api_lineups() -> Iterator[dict]:
        for b in bundles:
            for row in b["lineups"]:
                yield row

    @dlt.resource(name="api_incidents", write_disposition="append")
    def api_incidents() -> Iterator[dict]:
        for b in bundles:
            for row in b["incidents"]:
                yield row

    @dlt.resource(name="api_team_statistics", write_disposition="append")
    def api_team_statistics() -> Iterator[dict]:
        for b in bundles:
            for row in b["team_statistics"]:
                yield row

    @dlt.resource(name="api_extract_errors", write_disposition="append")
    def api_extract_errors() -> Iterator[dict]:
        for row in errors:
            yield row

    return api_events, api_lineups, api_incidents, api_team_statistics, api_extract_errors


def run(
    matches: pd.DataFrame,
    warehouse: Path,
    delay: float,
    also_write_raw: bool,
) -> dlt.Pipeline:
    warehouse.parent.mkdir(parents=True, exist_ok=True)
    pipeline = dlt.pipeline(
        pipeline_name="sofascore_extract",
        destination=dlt.destinations.duckdb(str(warehouse)),
        dataset_name=DATASET_NAME,
        progress="log",
    )
    info = pipeline.run(sofascore_api(matches, delay=delay, also_write_raw=also_write_raw))
    print(info)
    print(f"Warehouse: {warehouse}")
    print(f"Dataset:   {DATASET_NAME}")
    return pipeline


def main() -> int:
    parser = argparse.ArgumentParser(description="DLT extract Sofascore API → DuckDB")
    parser.add_argument("--competition", default=None)
    parser.add_argument("--season", default=None)
    parser.add_argument("--match-id", action="append", default=[], dest="match_ids")
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--delay", type=float, default=0.5)
    parser.add_argument("--also-write-raw", action="store_true", help="Also write data/raw/{season}/... files")
    parser.add_argument("--warehouse", type=Path, default=None)
    args = parser.parse_args()

    matches = _select_matches(args.competition, args.season, args.match_ids, args.limit)
    warehouse = args.warehouse if args.warehouse else _warehouse_path()
    if args.warehouse and not Path(args.warehouse).is_absolute():
        warehouse = ROOT / args.warehouse

    print(f"Extracting {len(matches)} match(es) → {warehouse}")
    run(matches, warehouse, delay=args.delay, also_write_raw=args.also_write_raw)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
