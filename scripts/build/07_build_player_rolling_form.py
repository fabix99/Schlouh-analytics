"""
Step 7: Rolling form — last 5, 10, 20 appearances per player (rating, goals, xG, xA, etc.).
Output: data/processed/07_player_rolling_form.parquet (latest snapshot per player per window).
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
    app["match_date_utc"] = pd.to_datetime(app["match_date"], unit="s", utc=True)
    app = app.sort_values(["player_id", "match_date_utc"])

    windows = [5, 10, 20]
    keys = ["stat_rating", "stat_goals", "stat_goalAssist", "stat_expectedGoals", "stat_expectedAssists", "stat_keyPass", "stat_minutesPlayed", "stat_totalShots", "stat_totalTackle", "stat_interceptionWon", "stat_wonContest", "stat_touches"]
    keys = [k for k in keys if k in app.columns]

    rows = []
    for player_id, g in app.groupby("player_id"):
        g = g.reset_index(drop=True)
        for w in windows:
            if len(g) < 1:
                continue
            last = g.tail(w)
            n_available = len(last)
            rec = {
                "player_id": player_id,
                "player_name": g["player_name"].iloc[-1],
                "player_position": g["player_position"].iloc[-1],
                "as_of_match_id": str(g["match_id"].iloc[-1]),
                "as_of_date": g["match_date_utc"].iloc[-1],
                "window": w,
                "n_available": n_available,
                "is_current": True,
            }
            rec["avg_rating"] = last["stat_rating"].mean() if "stat_rating" in last.columns else np.nan
            rec["goals"] = last["stat_goals"].sum() if "stat_goals" in last.columns else 0
            rec["assists"] = last["stat_goalAssist"].sum() if "stat_goalAssist" in last.columns else 0
            rec["xg_total"] = last["stat_expectedGoals"].sum() if "stat_expectedGoals" in last.columns else np.nan
            rec["xa_total"] = last["stat_expectedAssists"].sum() if "stat_expectedAssists" in last.columns else np.nan
            rec["total_minutes"] = last["stat_minutesPlayed"].sum() if "stat_minutesPlayed" in last.columns else 0
            rec["avg_key_passes"] = last["stat_keyPass"].mean() if "stat_keyPass" in last.columns else np.nan
            rec["avg_shots"] = last["stat_totalShots"].mean() if "stat_totalShots" in last.columns else np.nan
            rec["avg_tackles"] = last["stat_totalTackle"].mean() if "stat_totalTackle" in last.columns else np.nan
            rec["avg_interceptions"] = last["stat_interceptionWon"].mean() if "stat_interceptionWon" in last.columns else np.nan
            rec["avg_dribbles_won"] = last["stat_wonContest"].mean() if "stat_wonContest" in last.columns else np.nan
            rec["avg_touches"] = last["stat_touches"].mean() if "stat_touches" in last.columns else np.nan
            rows.append(rec)

    out = pd.DataFrame(rows)
    out_path = PROCESSED_DIR / "07_player_rolling_form.parquet"
    out.to_parquet(out_path, index=False)
    print(f"Wrote {out_path} ({len(out)} rows)")


if __name__ == "__main__":
    main()
