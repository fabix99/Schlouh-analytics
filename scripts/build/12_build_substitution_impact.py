"""
Step 12: Substitution impact — one row per substitute appearance.

Source data has no substitution incident type (only card/goal/varDecision/inGamePenalty),
so we derive substitutions directly from player_appearances (substitute=True rows).

Fields:
  - player_in_id/name: the substitute player
  - sub_minute (estimated): 90 - stat_minutesPlayed  (normal-time approximation)
  - minutes_after_sub: stat_minutesPlayed
  - player_in_rating/goals/assists/xg/key_passes: their stats in that match
  - player_out_id/name: null (unavailable without sub incident data)
  - season, competition_slug, match_id

Output: data/processed/12_substitution_impact.parquet
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
    app["match_id"] = app["match_id"].astype(str)

    # Substitute appearances only — must have recorded playing time > 0
    # Players with stat_minutesPlayed == 0 or null are listed in lineups but never actually played:
    # they produce sub_minute=90 / minutes_after_sub=0 which is meaningless for impact analysis.
    subs = app[(app["substitute"] == True) & (app["stat_minutesPlayed"].fillna(0) > 0)].copy()
    if subs.empty:
        out_path = PROCESSED_DIR / "12_substitution_impact.parquet"
        pd.DataFrame(columns=[
            "match_id", "player_in_id", "player_in_name", "player_in_position",
            "player_out_id", "player_out_name",
            "sub_minute", "minutes_after_sub", "sub_minute_estimated", "confidence_tier",
            "player_in_rating", "player_in_goals", "player_in_assists",
            "player_in_xg", "player_in_key_passes",
            "season", "competition_slug",
        ]).to_parquet(out_path, index=False)
        print(f"Wrote {out_path} (0 rows — no substitute appearances)")
        return

    minutes = subs["stat_minutesPlayed"].fillna(0).astype(float)
    # Estimate sub_minute from minutes played (assumes 90-min match; no stoppage/ET data)
    subs = subs.copy()
    subs["minutes_after_sub"] = minutes
    subs["sub_minute"] = (90 - minutes).clip(lower=0)
    # Mark approximation for downstream transparency
    sub_minute_estimated = True
    confidence_tier = "estimated_90min"  # derived from minutes played, no sub-incident timestamp

    rows = []
    for _, row in subs.iterrows():
        rows.append({
            "match_id": row["match_id"],
            "player_in_id": row["player_id"],
            "player_in_name": row.get("player_name"),
            "player_in_position": row.get("player_position"),
            "player_out_id": None,
            "player_out_name": None,
            "sub_minute": row["sub_minute"],
            "minutes_after_sub": row["minutes_after_sub"],
            "sub_minute_estimated": sub_minute_estimated,
            "confidence_tier": confidence_tier,
            "player_in_rating": row["stat_rating"] if "stat_rating" in row.index else np.nan,
            "player_in_goals": int(row["stat_goals"]) if "stat_goals" in row.index and pd.notna(row["stat_goals"]) else 0,
            "player_in_assists": int(row["stat_goalAssist"]) if "stat_goalAssist" in row.index and pd.notna(row["stat_goalAssist"]) else 0,
            "player_in_xg": row["stat_expectedGoals"] if "stat_expectedGoals" in row.index else np.nan,
            "player_in_key_passes": int(row["stat_keyPass"]) if "stat_keyPass" in row.index and pd.notna(row["stat_keyPass"]) else 0,
            "season": row.get("season"),
            "competition_slug": row.get("competition_slug"),
        })

    out = pd.DataFrame(rows)
    out_path = PROCESSED_DIR / "12_substitution_impact.parquet"
    out.to_parquet(out_path, index=False)
    print(f"Wrote {out_path} ({len(out)} rows)")


if __name__ == "__main__":
    main()
