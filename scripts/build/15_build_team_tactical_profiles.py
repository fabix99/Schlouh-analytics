"""
Step 15: Team tactical style indices from 01_team_season_stats (possession, directness, pressing, etc.).
Output: data/processed/15_team_tactical_profiles.parquet
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
    df = pd.read_parquet(PROCESSED_DIR / "01_team_season_stats.parquet")
    id_cols = ["team_name", "season", "competition_slug"]
    out = df[id_cols].copy()
    if "possession_avg" in df.columns:
        out["possession_index"] = df["possession_avg"]
    if "passes_total" in df.columns and "long_balls" in df.columns:
        out["directness_index"] = df["long_balls"] / df["passes_total"].replace(0, np.nan)
    if "tackles_total" in df.columns and "interceptions_total" in df.columns:
        out["pressing_index"] = df["tackles_total"] + df["interceptions_total"]
    if "aerial_duels" in df.columns:
        out["aerial_index"] = df["aerial_duels"]
    if "crosses" in df.columns:
        out["crossing_index"] = df["crosses"]
    if "big_chances_total" in df.columns:
        out["chance_creation_index"] = df["big_chances_total"]
    if "xg_against_total" in df.columns:
        out["defensive_solidity"] = 1 / df["xg_against_total"].replace(0, np.nan)
    if "xg_for_home" in df.columns and "xg_for_away" in df.columns and "matches_home" in df.columns and "matches_away" in df.columns:
        xg_home_pg = df["xg_for_home"] / df["matches_home"].replace(0, np.nan)
        xg_away_pg = df["xg_for_away"] / df["matches_away"].replace(0, np.nan)
        out["home_away_consistency"] = 1 / (1 + (xg_home_pg - xg_away_pg).abs())
    if "shots_second_half" in df.columns and "shots_first_half" in df.columns:
        out["second_half_intensity"] = df["shots_second_half"] / df["shots_first_half"].replace(0, np.nan)
    for col in ["possession_index", "directness_index", "pressing_index", "aerial_index", "crossing_index", "chance_creation_index", "defensive_solidity", "home_away_consistency", "second_half_intensity"]:
        if col in out.columns:
            out[col + "_pct"] = out.groupby(["season", "competition_slug"])[col].rank(pct=True)
    out_path = PROCESSED_DIR / "15_team_tactical_profiles.parquet"
    out.to_parquet(out_path, index=False)
    print(f"Wrote {out_path} ({len(out)} rows)")


if __name__ == "__main__":
    main()
