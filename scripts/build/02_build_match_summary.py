"""
Step 2: Build match summary (one row per match): scores, xG, possession, shots, managers.
Output: data/processed/02_match_summary.parquet
"""

import json
import sys
from pathlib import Path
from typing import Optional

import pandas as pd
import numpy as np

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

from scripts.build.utils import RAW_DIR, PROCESSED_DIR, INDEX_DIR, parse_pct, parse_ratio


def parse_value(s):
    """Parse stat value: ratio, percentage (only if '%' in string), or plain number."""
    if pd.isna(s):
        return np.nan
    s = str(s).strip()
    r = parse_ratio(s)
    if r[0] is not None:
        return r[2] if r[1] and r[1] > 0 else np.nan
    if "%" in s:
        p = parse_pct(s)
        if p is not None:
            return p
    try:
        return float(s)
    except ValueError:
        return np.nan


def get_raw_match_dir(match_id: str, season: str, competition_slug: str) -> Optional[Path]:
    """Return path to match folder if it exists."""
    p = RAW_DIR / season / "club" / competition_slug / match_id
    return p if p.exists() else None


def main():
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    matches = pd.read_csv(INDEX_DIR / "matches.csv")
    matches["match_id"] = matches["match_id"].astype(str)
    scores = pd.read_parquet(PROCESSED_DIR / "00_match_scores_full.parquet")
    scores["match_id"] = scores["match_id"].astype(str)
    matches = matches.merge(scores, on="match_id", how="left")

    rows = []
    unreadable_stats = 0
    unreadable_manager = 0
    parse_errors = 0
    for _, row in matches.iterrows():
        match_id = row["match_id"]
        season = row["season"]
        comp = row["competition_slug"]
        match_dir = get_raw_match_dir(match_id, season, comp)
        rec = {
            "match_id": match_id,
            "season": season,
            "competition_slug": comp,
            "match_date_utc": pd.to_datetime(row["match_date"], unit="s", utc=True) if pd.notna(row.get("match_date")) else pd.NaT,
            "round": row.get("round"),
            "home_team_name": row["home_team_name"],
            "away_team_name": row["away_team_name"],
            "home_score": row.get("home_score"),
            "away_score": row.get("away_score"),
            "result": row.get("result", "D"),
            "total_goals": row.get("total_goals"),
            "home_xg": np.nan,
            "away_xg": np.nan,
            "home_possession": np.nan,
            "away_possession": np.nan,
            "home_shots": np.nan,
            "away_shots": np.nan,
            "home_shots_on_target": np.nan,
            "away_shots_on_target": np.nan,
            "home_big_chances": np.nan,
            "away_big_chances": np.nan,
            "home_manager_name": None,
            "home_manager_id": None,
            "away_manager_name": None,
            "away_manager_id": None,
            "home_xg_first_half": np.nan,
            "away_xg_first_half": np.nan,
            "home_xg_second_half": np.nan,
            "away_xg_second_half": np.nan,
        }
        if match_dir:
            # Team stats
            ts_path = match_dir / "team_statistics.csv"
            if ts_path.exists():
                try:
                    ts = pd.read_csv(ts_path)
                    ts_all = ts[ts["period"] == "ALL"].drop_duplicates(subset=["name"], keep="first")
                    for _, r in ts_all.iterrows():
                        name = r["name"]
                        h, a = parse_value(r["home"]), parse_value(r["away"])
                        if name == "Expected goals":
                            rec["home_xg"], rec["away_xg"] = h, a
                        elif name == "Ball possession":
                            rec["home_possession"], rec["away_possession"] = h, a
                        elif name == "Total shots":
                            rec["home_shots"], rec["away_shots"] = h, a
                        elif name == "Shots on target":
                            rec["home_shots_on_target"], rec["away_shots_on_target"] = h, a
                        elif name == "Big chances":
                            rec["home_big_chances"], rec["away_big_chances"] = h, a
                    # First/second half xG
                    for period, key_h, key_a in [("1ST", "home_xg_first_half", "away_xg_first_half"), ("2ND", "home_xg_second_half", "away_xg_second_half")]:
                        ts_per = ts[ts["period"] == period].drop_duplicates(subset=["name"], keep="first")
                        for _, r in ts_per.iterrows():
                            if r["name"] == "Expected goals":
                                rec[key_h], rec[key_a] = parse_value(r["home"]), parse_value(r["away"])
                                break
                except (pd.errors.ParserError, ValueError, KeyError, OSError) as e:
                    parse_errors += 1
                except Exception as e:
                    unreadable_stats += 1
            # Managers
            mgr_path = match_dir / "managers.json"
            if mgr_path.exists():
                try:
                    with open(mgr_path, encoding="utf-8") as f:
                        mgr = json.load(f)
                    for side, key in [("home", "homeManager"), ("away", "awayManager")]:
                        m = mgr.get(key) or {}
                        rec[f"{side}_manager_name"] = m.get("name")
                        rec[f"{side}_manager_id"] = m.get("id")
                except (json.JSONDecodeError, OSError, KeyError) as e:
                    parse_errors += 1
                except Exception as e:
                    unreadable_manager += 1
        rec["xg_swing"] = (rec["home_xg"] - rec["away_xg"]) if pd.notna(rec["home_xg"]) and pd.notna(rec["away_xg"]) else np.nan
        rec["home_xg_overperformance"] = (float(rec["home_score"]) - rec["home_xg"]) if pd.notna(rec["home_score"]) and pd.notna(rec["home_xg"]) else np.nan
        rec["away_xg_overperformance"] = (float(rec["away_score"]) - rec["away_xg"]) if pd.notna(rec["away_score"]) and pd.notna(rec["away_xg"]) else np.nan
        rows.append(rec)

    out = pd.DataFrame(rows)
    out_path = PROCESSED_DIR / "02_match_summary.parquet"
    out.to_parquet(out_path, index=False)
    print(f"Wrote {out_path} ({len(out)} rows)")
    if unreadable_stats or unreadable_manager or parse_errors:
        print(f"  Warnings: unreadable_stats={unreadable_stats}, unreadable_manager={unreadable_manager}, parse_errors={parse_errors}")


if __name__ == "__main__":
    main()
