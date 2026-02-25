"""
Step 6: Player percentile ranks within (position, competition, season) and globally.
Output: data/processed/06_player_percentile_ranks.parquet (long format).
"""

import sys
from pathlib import Path

import pandas as pd
import numpy as np
from scipy.stats import percentileofscore

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

from scripts.build.utils import PROCESSED_DIR

LOWER_IS_BETTER = {"fouls_per90", "totalOffside_per90", "possessionLostCtrl_per90", "dispossessed_per90", "yellow_cards", "red_cards"}


def main():
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    df = pd.read_parquet(PROCESSED_DIR / "03_player_season_stats.parquet")
    df = df[df["sufficient_minutes"] == True].copy()

    per90_cols = [c for c in df.columns if c.endswith("_per90")]
    rate_cols = [c for c in ["pass_accuracy", "duel_win_rate", "aerial_win_rate", "tackle_success_rate"] if c in df.columns]
    stat_cols = per90_cols + rate_cols
    # Also add yellow_cards, red_cards (totals)
    for c in ["yellow_cards", "red_cards"]:
        if c in df.columns and c not in stat_cols:
            stat_cols.append(c)

    rows = []
    for (position, competition_slug, season), g in df.groupby(["player_position", "competition_slug", "season"]):
        n_comp = len(g)
        for _, row in g.iterrows():
            for stat in stat_cols:
                if stat not in row.index or pd.isna(row[stat]):
                    continue
                val = row[stat]
                arr = g[stat].dropna()
                if len(arr) < 2:
                    continue
                pct = percentileofscore(arr, val, kind="rank")
                if stat in LOWER_IS_BETTER or (stat in ["yellow_cards", "red_cards"]):
                    pct = 100 - pct
                rows.append({
                    "player_id": row["player_id"],
                    "player_name": row["player_name"],
                    "player_position": position,
                    "season": season,
                    "competition_slug": competition_slug,
                    "stat_name": stat,
                    "stat_value": val,
                    "pct_in_competition": round(pct, 1),
                    "n_players_in_competition": n_comp,
                    "pct_global": np.nan,
                    "n_players_global": np.nan,
                })

    out = pd.DataFrame(rows)
    # Global percentile: merge (position, season) group percentiles
    global_rows = []
    for (position, season), g in df.groupby(["player_position", "season"]):
        n_global = len(g)
        for stat in stat_cols:
            arr = g[stat].dropna()
            if len(arr) < 2:
                continue
            for pid in g["player_id"].unique():
                row = g[g["player_id"] == pid].iloc[0]
                if stat not in row.index or pd.isna(row[stat]):
                    continue
                val = row[stat]
                pct = percentileofscore(arr, val, kind="rank")
                if stat in LOWER_IS_BETTER or stat in ["yellow_cards", "red_cards"]:
                    pct = 100 - pct
                global_rows.append({"player_id": pid, "season": season, "player_position": position, "stat_name": stat, "pct_global": round(pct, 1), "n_players_global": n_global})
    if global_rows:
        gdf = pd.DataFrame(global_rows)
        out = out.drop(columns=["pct_global", "n_players_global"], errors="ignore")
        out = out.merge(gdf, on=["player_id", "season", "player_position", "stat_name"], how="left")
    out_path = PROCESSED_DIR / "06_player_percentile_ranks.parquet"
    out.to_parquet(out_path, index=False)
    print(f"Wrote {out_path} ({len(out)} rows)")


if __name__ == "__main__":
    main()
