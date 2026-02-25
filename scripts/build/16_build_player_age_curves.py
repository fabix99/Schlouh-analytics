"""
Step 16: Median per-90 stats by (player_position, age_bin); reliable flag (n >= 20).
Output: data/processed/16_player_age_curves.parquet
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
    df["age_bin"] = df["age_at_season_start"].fillna(0).astype(int)

    per90_cols = [c for c in df.columns if c.endswith("_per90")]
    rate_cols = [c for c in ["pass_accuracy", "duel_win_rate"] if c in df.columns]
    stat_cols = per90_cols + rate_cols

    rows = []
    for (position, age_bin), g in df.groupby(["player_position", "age_bin"]):
        if age_bin < 16 or age_bin > 45:
            continue
        n = len(g)
        rec = {"player_position": position, "age_bin": age_bin, "n_player_seasons": n, "reliable": n >= 20}
        for stat in stat_cols:
            if stat in g.columns:
                rec["median_" + stat] = g[stat].median()
        rows.append(rec)
    out = pd.DataFrame(rows)
    out_path = PROCESSED_DIR / "16_player_age_curves.parquet"
    out.to_parquet(out_path, index=False)
    print(f"Wrote {out_path} ({len(out)} rows)")

    # Peak age by position (age_bin where median stat is highest, among reliable rows)
    reliable = out[out["reliable"] == True]
    if reliable.empty:
        peak_df = pd.DataFrame(columns=["player_position", "peak_rating_age", "peak_xg_age"])
    else:
        peak_rows = []
        for position in reliable["player_position"].unique():
            g = reliable[reliable["player_position"] == position]
            row = {"player_position": position}
            if "median_rating_per90" in g.columns:
                idx = g["median_rating_per90"].idxmax()
                row["peak_rating_age"] = int(g.loc[idx, "age_bin"])
            else:
                row["peak_rating_age"] = np.nan
            if "median_expectedGoals_per90" in g.columns:
                idx = g["median_expectedGoals_per90"].idxmax()
                row["peak_xg_age"] = int(g.loc[idx, "age_bin"])
            else:
                row["peak_xg_age"] = np.nan
            peak_rows.append(row)
        peak_df = pd.DataFrame(peak_rows)
    peak_path = PROCESSED_DIR / "16_peak_age_by_position.parquet"
    peak_df.to_parquet(peak_path, index=False)
    print(f"Wrote {peak_path} ({len(peak_df)} rows)")


if __name__ == "__main__":
    main()
