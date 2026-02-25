"""
Step 9: Season-over-season deltas (rating, xg_per90, etc.) for players with >= 2 seasons.
Output: data/processed/09_player_progression.parquet
"""

import sys
from pathlib import Path

import pandas as pd
import numpy as np

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

from scripts.build.utils import PROCESSED_DIR

DELTA_STATS = ["avg_rating", "expectedGoals_per90", "expectedAssists_per90", "goals_per90", "goalAssist_per90", "keyPass_per90", "totalTackle_per90", "duel_win_rate", "pass_accuracy"]


def main():
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    df = pd.read_parquet(PROCESSED_DIR / "03_player_season_stats.parquet")
    df = df[df["sufficient_minutes"] == True].copy()
    df = df.sort_values(["player_id", "season"])

    available = [c for c in DELTA_STATS if c in df.columns]
    rows = []
    for player_id, g in df.groupby("player_id"):
        if len(g) < 2:
            continue
        g = g.sort_values("season")
        for i in range(len(g) - 1):
            row_from = g.iloc[i]
            row_to = g.iloc[i + 1]
            rec = {
                "player_id": player_id,
                "player_name": row_to["player_name"],
                "player_position": row_to["player_position"],
                "season_from": row_from["season"],
                "season_to": row_to["season"],
                "competition_from": row_from["competition_slug"],
                "competition_to": row_to["competition_slug"],
                "same_competition": row_from["competition_slug"] == row_to["competition_slug"],
                "age_at_season_to": row_to.get("age_at_season_start", np.nan),
            }
            for stat in available:
                v_from = row_from[stat]
                v_to = row_to[stat]
                if pd.notna(v_from) and pd.notna(v_to):
                    rec[stat + "_delta"] = float(v_to) - float(v_from)
            rec["rating_delta"] = rec.get("avg_rating_delta", np.nan)
            if pd.notna(rec["rating_delta"]):
                rec["progression_direction"] = "improving" if rec["rating_delta"] > 0.1 else ("declining" if rec["rating_delta"] < -0.1 else "stable")
            else:
                rec["progression_direction"] = None
            rec["minutes_delta"] = int(row_to.get("total_minutes", 0) or 0) - int(row_from.get("total_minutes", 0) or 0)
            rows.append(rec)

    out = pd.DataFrame(rows)
    out_path = PROCESSED_DIR / "09_player_progression.parquet"
    out.to_parquet(out_path, index=False)
    print(f"Wrote {out_path} ({len(out)} rows)")


if __name__ == "__main__":
    main()
