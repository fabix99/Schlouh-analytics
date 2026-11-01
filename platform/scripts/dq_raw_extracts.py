#!/usr/bin/env python3
"""
Data-quality check on raw match extracts (detect empty/403 payloads vs real data).

Usage:
  python platform/scripts/dq_raw_extracts.py england-premier-league 2025-26
  python platform/scripts/dq_raw_extracts.py england-premier-league 2025-26 --probe-api
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
from config import API_BASE, INDEX_PATH, RAW_BASE  # noqa: E402
from extract_match_lineups import fetch_json_resilient  # noqa: E402


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("competition")
    p.add_argument("season")
    p.add_argument("--probe-api", action="store_true", help="Live-hit Sofascore for 3 sample matches")
    p.add_argument("--sample", type=int, default=5)
    args = p.parse_args()

    index = pd.read_csv(INDEX_PATH)
    index["match_id"] = index["match_id"].astype(str)
    ids = index[
        (index["competition_slug"] == args.competition) & (index["season"] == args.season)
    ]["match_id"].tolist()
    if not ids:
        print("No matches in index for that competition/season", file=sys.stderr)
        return 1

    base = RAW_BASE / args.season / "club" / args.competition
    ok = missing = bad = error_json = 0
    newest_ok = []

    for mid in ids:
        d = base / mid
        lp, ep = d / "lineups.csv", d / "event.json"
        if not lp.exists() or lp.stat().st_size < 50:
            missing += 1
            continue
        try:
            raw = json.loads(ep.read_text()) if ep.exists() else {}
            if isinstance(raw, dict) and "error" in raw:
                error_json += 1
                continue
            df = pd.read_csv(lp)
            ev = raw.get("event") or {}
            hs = (ev.get("homeScore") or {}).get("current")
            as_ = (ev.get("awayScore") or {}).get("current")
            n_players = df["player_name"].notna().sum() if "player_name" in df.columns else 0
            good = len(df) >= 22 and n_players >= 22 and hs is not None and as_ is not None
            if good:
                ok += 1
                newest_ok.append(
                    (
                        (lp.stat().st_mtime),
                        mid,
                        (ev.get("homeTeam") or {}).get("name"),
                        hs,
                        as_,
                        (ev.get("awayTeam") or {}).get("name"),
                        len(df),
                        df["player_name"].dropna().head(2).tolist(),
                    )
                )
            else:
                bad += 1
        except Exception:
            bad += 1

    print(f"=== DQ {args.competition} {args.season} ===")
    print(f"indexed: {len(ids)}")
    print(f"real_ok: {ok}")
    print(f"missing: {missing}")
    print(f"bad_weak: {bad}")
    print(f"error_json_403ish: {error_json}")

    newest_ok.sort(reverse=True)
    print(f"\nNewest {min(args.sample, len(newest_ok))} OK extracts:")
    for _, mid, home, hs, as_, away, n, names in newest_ok[: args.sample]:
        print(f"  {mid}: {home} {hs}-{as_} {away} | lineups={n} e.g. {names}")

    if args.probe_api:
        print("\nLive API probe:")
        for _, mid, *_ in newest_ok[:3] or [(0, ids[0])]:
            data, err = fetch_json_resilient(f"{API_BASE}/event/{mid}")
            if err:
                print(f"  {mid}: FAIL {err}")
            else:
                ev = (data or {}).get("event") or {}
                print(
                    f"  {mid}: OK {(ev.get('homeTeam') or {}).get('name')} "
                    f"{(ev.get('homeScore') or {}).get('current')}-{(ev.get('awayScore') or {}).get('current')} "
                    f"{(ev.get('awayTeam') or {}).get('name')}"
                )

    # Fail CI-style if any saved error payloads or bad files among present extracts
    if error_json or bad:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
