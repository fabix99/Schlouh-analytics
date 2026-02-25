"""
Step 8: One row per player — latest season, career, rolling form (window=10), top percentile highlights.
Output: data/processed/08_player_scouting_profiles.parquet
"""

import sys
from pathlib import Path

import pandas as pd
import numpy as np

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

from scripts.build.utils import PROCESSED_DIR, INDEX_DIR, DERIVED_DIR


def main():
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    players = pd.read_csv(INDEX_DIR / "players.csv")

    # age_today from player_appearances DOB
    app = pd.read_parquet(DERIVED_DIR / "player_appearances.parquet", columns=["player_id", "player_dateOfBirthTimestamp"])
    dob = app.dropna(subset=["player_dateOfBirthTimestamp"]).drop_duplicates("player_id")[["player_id", "player_dateOfBirthTimestamp"]]
    now_sec = pd.Timestamp.now(tz="UTC").timestamp()
    dob["age_today"] = (now_sec - pd.to_numeric(dob["player_dateOfBirthTimestamp"], errors="coerce")) / (365.25 * 24 * 3600)
    dob = dob[["player_id", "age_today"]]
    players["player_id"] = players["player_id"].astype(type(players["player_id"].iloc[0]))
    season_stats = pd.read_parquet(PROCESSED_DIR / "03_player_season_stats.parquet")
    career = pd.read_parquet(PROCESSED_DIR / "04_player_career_stats.parquet")
    rolling = pd.read_parquet(PROCESSED_DIR / "07_player_rolling_form.parquet")
    rolling10 = rolling[rolling["window"] == 10].drop(columns=["window"]).rename(columns=lambda c: "form_" + c if c not in ["player_id", "player_name", "player_position"] else c)
    percentiles = pd.read_parquet(PROCESSED_DIR / "06_player_percentile_ranks.parquet")

    # Latest season per player (most recent season with sufficient_minutes)
    season_stats_valid = season_stats[season_stats["sufficient_minutes"] == True]
    latest_season = season_stats_valid.sort_values("season", ascending=False).groupby("player_id").first().reset_index()
    latest_season = latest_season.rename(columns={
        "season": "latest_season", "competition_slug": "latest_competition",
        "avg_rating": "latest_rating", "total_minutes": "latest_minutes", "appearances": "latest_appearances",
    })

    # Top 3 percentile stats per player (from latest season or any)
    pct_top = percentiles[percentiles["pct_in_competition"].notna()].sort_values("pct_in_competition", ascending=False)
    top3 = pct_top.groupby("player_id").head(3)
    top3_list = top3.groupby("player_id", group_keys=False).apply(
        lambda g: list(zip(g["stat_name"], g["stat_value"], g["pct_in_competition"])), include_groups=False
    ).to_dict()
    def top3_row(pid):
        t = top3_list.get(pid, [])
        row = {}
        for i, (name, val, pct) in enumerate(t[:3]):
            row[f"top_pct_stat_{i+1}_name"] = name
            row[f"top_pct_stat_{i+1}_value"] = val
            row[f"top_pct_stat_{i+1}_pct"] = pct
        return row
    players["_top3"] = players["player_id"].map(top3_row)

    out = players[["player_id", "player_name", "player_slug", "player_shortName", "n_matches", "_top3"]].copy()
    out = out.merge(dob, on="player_id", how="left")
    out = out.merge(career[["player_id", "player_position", "total_minutes", "goals", "assists", "first_season", "last_season", "n_seasons", "n_competitions"]], on="player_id", how="left")
    out = out.merge(latest_season[["player_id", "latest_season", "latest_competition", "latest_rating", "latest_minutes", "latest_appearances"]], on="player_id", how="left")
    roll_cols = ["player_id", "form_avg_rating", "form_goals", "form_xg_total", "form_xa_total"]
    roll_cols = [c for c in roll_cols if c in rolling10.columns]
    r10 = rolling10[roll_cols].rename(columns={"form_avg_rating": "form_rating", "form_xg_total": "form_xg", "form_xa_total": "form_xa"})
    out = out.merge(r10, on="player_id", how="left")

    # Expand top3
    for i in range(1, 4):
        out[f"top_pct_stat_{i}_name"] = out["_top3"].apply(lambda r: r.get(f"top_pct_stat_{i}_name") if isinstance(r, dict) else None)
        out[f"top_pct_stat_{i}_value"] = out["_top3"].apply(lambda r: r.get(f"top_pct_stat_{i}_value") if isinstance(r, dict) else None)
        out[f"top_pct_stat_{i}_pct"] = out["_top3"].apply(lambda r: r.get(f"top_pct_stat_{i}_pct") if isinstance(r, dict) else None)
    out = out.drop(columns=["_top3"], errors="ignore")

    out["active"] = out["last_season"].notna()
    out["sufficient_minutes_latest_season"] = out["latest_minutes"].fillna(0) >= 450

    out_path = PROCESSED_DIR / "08_player_scouting_profiles.parquet"
    out.to_parquet(out_path, index=False)
    print(f"Wrote {out_path} ({len(out)} rows)")


if __name__ == "__main__":
    main()
