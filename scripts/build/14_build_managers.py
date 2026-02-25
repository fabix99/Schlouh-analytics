"""
Step 14: Parse managers.json -> match-level manager rows; aggregate manager_career_stats.
Output: data/processed/14_managers.parquet, manager_career_stats.parquet
"""

import json
import sys
from pathlib import Path

import pandas as pd
import numpy as np

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

from scripts.build.utils import RAW_DIR, PROCESSED_DIR, INDEX_DIR


def iter_managers_files():
    for season_dir in sorted(RAW_DIR.iterdir()):
        if not season_dir.is_dir() or season_dir.name.startswith("."):
            continue
        club = season_dir / "club"
        if not club.exists():
            continue
        for comp_dir in sorted(club.iterdir()):
            if not comp_dir.is_dir() or comp_dir.name.startswith("."):
                continue
            for match_dir in sorted(comp_dir.iterdir()):
                if not match_dir.is_dir() or match_dir.name.startswith("."):
                    continue
                path = match_dir / "managers.json"
                if path.exists():
                    yield match_dir.name, season_dir.name, comp_dir.name, path


def main():
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    scores = pd.read_parquet(PROCESSED_DIR / "00_match_scores_full.parquet")
    scores["match_id"] = scores["match_id"].astype(str)
    matches = pd.read_csv(INDEX_DIR / "matches.csv")
    matches["match_id"] = matches["match_id"].astype(str)
    matches = matches.merge(scores[["match_id", "home_score", "away_score", "result"]], on="match_id", how="left")

    rows = []
    for match_id, season, comp, path in iter_managers_files():
        try:
            with open(path) as f:
                data = json.load(f)
        except Exception:
            continue
        m = matches[matches["match_id"] == match_id]
        if m.empty:
            continue
        m = m.iloc[0]
        res = m.get("result", "D")
        for side, key in [("home", "homeManager"), ("away", "awayManager")]:
            mgr = data.get(key) or {}
            team = m["home_team_name"] if side == "home" else m["away_team_name"]
            score_own = m["home_score"] if side == "home" else m["away_score"]
            score_opp = m["away_score"] if side == "home" else m["home_score"]
            if res == "H":
                res_side = "W" if side == "home" else "L"
            elif res == "A":
                res_side = "L" if side == "home" else "W"
            else:
                res_side = "D"
            rows.append({
                "match_id": match_id,
                "manager_id": mgr.get("id"),
                "manager_name": mgr.get("name"),
                "manager_slug": mgr.get("slug"),
                "side": side,
                "team_name": team,
                "season": season,
                "competition_slug": comp,
                "result": res_side,
            })
    out = pd.DataFrame(rows)
    out_path = PROCESSED_DIR / "14_managers.parquet"
    out.to_parquet(out_path, index=False)
    print(f"Wrote {out_path} ({len(out)} rows)")

    if out.empty:
        career = pd.DataFrame()
    else:
        career = out.groupby("manager_id").agg(
            manager_name=("manager_name", "first"),
            total_matches=("match_id", "nunique"),
            wins=("result", lambda x: (x == "W").sum()),
            draws=("result", lambda x: (x == "D").sum()),
            losses=("result", lambda x: (x == "L").sum()),
            seasons=("season", lambda s: ",".join(sorted(s.dropna().unique()))),
            competitions=("competition_slug", lambda s: ",".join(sorted(s.dropna().unique()))),
            teams=("team_name", lambda s: ",".join(sorted(s.dropna().unique()))),
        ).reset_index()
        career["win_rate"] = career["wins"] / career["total_matches"].replace(0, np.nan)
    career_path = PROCESSED_DIR / "manager_career_stats.parquet"
    career.to_parquet(career_path, index=False)
    print(f"Wrote {career_path} ({len(career)} rows)")


if __name__ == "__main__":
    main()
