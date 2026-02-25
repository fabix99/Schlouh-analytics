"""
Step 4: Aggregate 03_player_season_stats by player_id into career totals and per-90.
Output: data/processed/04_player_career_stats.parquet
"""

import sys
from pathlib import Path

import pandas as pd
import numpy as np

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

from scripts.build.utils import PROCESSED_DIR, DERIVED_DIR, INDEX_DIR, MIN_MINUTES_CAREER, per90


def main():
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    df = pd.read_parquet(PROCESSED_DIR / "03_player_season_stats.parquet")
    players = pd.read_csv(INDEX_DIR / "players.csv") if (INDEX_DIR / "players.csv").exists() else pd.DataFrame()

    id_col = "player_id"
    # Identity
    identity = df.groupby(id_col).agg(
        player_name=("player_name", "first"),
        player_position=("player_position", "first"),
    ).reset_index()
    if "player_height" in df.columns:
        identity = identity.merge(df.groupby(id_col)["player_height"].first().reset_index(), on=id_col, how="left")

    # Career totals: sum of totals from 03 (we have total_minutes, goals, assists, etc.)
    sum_cols = ["appearances", "starts", "total_minutes", "goals", "assists", "goal_contributions", "yellow_cards", "red_cards"]
    sum_cols = [c for c in sum_cols if c in df.columns]
    career_totals = df.groupby(id_col)[sum_cols].sum().reset_index()

    # Total stat columns (total_* from 03 - but we dropped them; we have per90 and rate columns)
    # So we need to recompute from appearances or keep only what we have in 03.
    # 03 has: total_minutes, goals, assists, *_per90, pass_accuracy, etc.
    # For career we sum: appearances, starts, total_minutes, goals, assists, yellow_cards, red_cards
    # Per-90 from career: (career_goals / career_minutes) * 90, etc.
    out = identity.merge(career_totals, on=id_col, how="left")
    out["sub_appearances"] = out["appearances"] - out["starts"]
    out["avg_minutes_per_game"] = out["total_minutes"] / out["appearances"].replace(0, np.nan)
    out["sufficient_minutes"] = out["total_minutes"] >= MIN_MINUTES_CAREER

    # Career per-90 from totals
    mins = out["total_minutes"].astype(float)
    out["goals_per90"] = per90(out["goals"], mins)
    out["assists_per90"] = per90(out["assists"], mins)
    out["goal_contributions_per90"] = per90(out["goal_contributions"], mins)

    # First/last season, n_seasons, n_competitions
    meta = df.groupby(id_col).agg(
        first_season=("season", "min"),
        last_season=("season", "max"),
        n_seasons=("season", "nunique"),
        n_competitions=("competition_slug", "nunique"),
        competitions_list=("competition_slug", lambda s: ",".join(sorted(s.dropna().unique()))),
        seasons_list=("season", lambda s: ",".join(sorted(s.dropna().unique()))),
    ).reset_index()
    out = out.merge(meta, on=id_col, how="left")

    # Peak rating season (drop groups with all-nan rating)
    idx = df.groupby(id_col)["avg_rating"].idxmax()
    idx = idx.dropna()
    if len(idx) > 0:
        peak_rating = df.loc[idx][[id_col, "season", "avg_rating"]].rename(columns={"season": "peak_rating_season", "avg_rating": "peak_rating"})
        out = out.merge(peak_rating[[id_col, "peak_rating_season", "peak_rating"]], on=id_col, how="left")
    # Peak xg_per90 season (if column exists)
    if "expectedGoals_per90" in df.columns:
        idx_xg = df.groupby(id_col)["expectedGoals_per90"].idxmax().dropna()
        if len(idx_xg) > 0:
            peak_xg = df.loc[idx_xg][[id_col, "season"]].drop_duplicates(id_col).rename(columns={"season": "peak_xg_per90_season"})
            out = out.merge(peak_xg, on=id_col, how="left")

    out_path = PROCESSED_DIR / "04_player_career_stats.parquet"
    out.to_parquet(out_path, index=False)
    print(f"Wrote {out_path} ({len(out)} rows)")


if __name__ == "__main__":
    main()
