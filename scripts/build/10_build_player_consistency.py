"""
Step 10: Per (player_id, season, competition) consistency — mean, std, CV for rating, xG, key_passes.
Output: data/processed/10_player_consistency.parquet
"""

import sys
from pathlib import Path

import pandas as pd
import numpy as np

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

from scripts.build.utils import DERIVED_DIR, PROCESSED_DIR


def main():
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    app = pd.read_parquet(DERIVED_DIR / "player_appearances.parquet")
    app = app[app["stat_minutesPlayed"].fillna(0) >= 1]

    id_cols = ["player_id", "season", "competition_slug"]
    stats = ["stat_rating", "stat_expectedGoals", "stat_expectedAssists", "stat_keyPass", "stat_touches"]
    stats = [s for s in stats if s in app.columns]

    def consistency(g):
        row = {"n_appearances": len(g)}
        for s in stats:
            x = g[s].dropna()
            if len(x) < 2:
                row[s.replace("stat_", "") + "_mean"] = x.mean() if len(x) == 1 else np.nan
                row[s.replace("stat_", "") + "_std"] = np.nan
                row[s.replace("stat_", "") + "_cv"] = np.nan
            else:
                mu, std = x.mean(), x.std()
                row[s.replace("stat_", "") + "_mean"] = mu
                row[s.replace("stat_", "") + "_std"] = std
                row[s.replace("stat_", "") + "_cv"] = (std / mu) if mu and mu != 0 else np.nan
        if "stat_rating" in g.columns:
            r = g["stat_rating"].dropna()
            row["rating_mean"] = r.mean()
            row["rating_std"] = r.std() if len(r) > 1 else np.nan
            row["rating_cv"] = (row["rating_std"] / row["rating_mean"]) if row["rating_mean"] and row["rating_mean"] != 0 else np.nan
            row["rating_min"] = r.min()
            row["rating_max"] = r.max()
        return pd.Series(row)

    agg = app.groupby(id_cols, group_keys=False).apply(consistency, include_groups=False).reset_index()
    agg["consistency_tier"] = "variable"
    if "rating_cv" in agg.columns:
        agg.loc[agg["rating_cv"].notna() & (agg["rating_cv"] < 0.08), "consistency_tier"] = "very_consistent"
        agg.loc[agg["rating_cv"].notna() & (agg["rating_cv"] >= 0.08) & (agg["rating_cv"] < 0.15), "consistency_tier"] = "consistent"
        agg.loc[agg["rating_cv"].notna() & (agg["rating_cv"] >= 0.2), "consistency_tier"] = "very_variable"
    agg = agg[agg["n_appearances"] >= 5]
    identity = app.groupby(id_cols).agg(player_name=("player_name", "first"), player_position=("player_position", "first")).reset_index()
    out = identity.merge(agg, on=id_cols, how="inner")
    out_path = PROCESSED_DIR / "10_player_consistency.parquet"
    out.to_parquet(out_path, index=False)
    print(f"Wrote {out_path} ({len(out)} rows)")


if __name__ == "__main__":
    main()
