"""
Step 5: Competition benchmarks — median, p25, p75, p90 of per-90 stats by (position, competition, season).
Output: data/processed/05_competition_benchmarks.parquet (long format).
"""

import sys
from pathlib import Path

import pandas as pd
import numpy as np

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

from scripts.build.utils import PROCESSED_DIR


def main():
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    df = pd.read_parquet(PROCESSED_DIR / "03_player_season_stats.parquet")
    df = df[df["sufficient_minutes"] == True].copy()

    per90_cols = [c for c in df.columns if c.endswith("_per90") and df[c].dtype in [np.float64, float]]
    rate_cols = [c for c in ["pass_accuracy", "duel_win_rate", "aerial_win_rate", "tackle_success_rate", "dribble_success_rate", "cross_accuracy", "long_ball_accuracy"] if c in df.columns]
    stat_cols = per90_cols + rate_cols

    rows = []
    for (position, competition_slug, season), g in df.groupby(["player_position", "competition_slug", "season"]):
        for stat in stat_cols:
            s = g[stat].dropna()
            if len(s) < 2:
                continue
            rows.append({
                "player_position": position,
                "competition_slug": competition_slug,
                "season": season,
                "stat_name": stat,
                "n_players": len(s),
                "mean": float(s.mean()),
                "median": float(s.median()),
                "p25": float(s.quantile(0.25)),
                "p75": float(s.quantile(0.75)),
                "p90": float(s.quantile(0.90)),
                "std": float(s.std()) if len(s) > 1 else np.nan,
            })
    # Global (all_competitions) per position per season
    for (position, season), g in df.groupby(["player_position", "season"]):
        for stat in stat_cols:
            s = g[stat].dropna()
            if len(s) < 2:
                continue
            rows.append({
                "player_position": position,
                "competition_slug": "all_competitions",
                "season": season,
                "stat_name": stat,
                "n_players": len(s),
                "mean": float(s.mean()),
                "median": float(s.median()),
                "p25": float(s.quantile(0.25)),
                "p75": float(s.quantile(0.75)),
                "p90": float(s.quantile(0.90)),
                "std": float(s.std()) if len(s) > 1 else np.nan,
            })

    out = pd.DataFrame(rows)
    out_path = PROCESSED_DIR / "05_competition_benchmarks.parquet"
    out.to_parquet(out_path, index=False)
    print(f"Wrote {out_path} ({len(out)} rows)")


if __name__ == "__main__":
    main()
