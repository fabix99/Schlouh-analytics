"""
Export form-over-time data (rolling 5G rating, xG/90, goals/90) as JSON for the web app.
Run from project root: python export/scripts/export_form.py [player_slug]
"""
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from viz.config import DEFAULT_PLAYER_SLUG
from viz.data_utils import load_player, rolling_mean, rolling_std, season_aggregates


def export_form(player_slug: str, window: int = 5, min_minutes_per_game: int = 45) -> dict:
    df = load_player(player_slug)
    if min_minutes_per_game > 0 and "stat_minutesPlayed" in df.columns:
        df = df[df["stat_minutesPlayed"] >= min_minutes_per_game].copy()
    df = df.sort_values("match_date_utc").reset_index(drop=True)
    name = df["player_shortName"].iloc[0] if "player_shortName" in df.columns else player_slug
    n = len(df)

    df["roll_rating"] = rolling_mean(df, "stat_rating", window=window, per_90=False)
    df["roll_xg"] = rolling_mean(df, "stat_expectedGoals", window=window, per_90=True)
    df["roll_goals"] = rolling_mean(df, "stat_goals", window=window, per_90=True)
    roll_rating_std = rolling_std(df, "stat_rating", window=window)

    season_agg = season_aggregates(df)
    season_rating = float(df["stat_rating"].mean())
    season_xg = float(season_agg.get("stat_expectedGoals", 0) or 0)
    season_goals = float(season_agg.get("stat_goals", 0) or 0)

    se = roll_rating_std / np.sqrt(np.minimum(np.arange(len(df)) + 1, window))
    se = se.fillna(0).values
    se = np.clip(se, 0, 2.0)  # cap for display

    points = []
    for i in range(len(df)):
        row = df.iloc[i]
        # Player's team: from "team" column or derive from side
        if "team" in df.columns and pd.notna(row.get("team")) and str(row["team"]).strip():
            team = str(row["team"]).strip()
        elif "side" in df.columns and "home_team_name" in df.columns and "away_team_name" in df.columns:
            team = str(row["home_team_name"] if row["side"] == "home" else row["away_team_name"])
        else:
            team = ""
        # Opponent
        if "side" in df.columns and "home_team_name" in df.columns and "away_team_name" in df.columns:
            opponent = str(row["away_team_name"] if row["side"] == "home" else row["home_team_name"])
        else:
            opponent = ""
        # Score (if available in index/derived data)
        score_str = ""
        if "home_score" in df.columns and "away_score" in df.columns and pd.notna(row.get("home_score")) and pd.notna(row.get("away_score")):
            try:
                h, a = int(row["home_score"]), int(row["away_score"])
                score_str = f"{h}-{a}"
            except (ValueError, TypeError):
                pass
        points.append({
            "date": row["match_date_utc"].strftime("%Y-%m-%d"),
            "rating": round(float(row["stat_rating"]), 2),
            "rollRating": round(float(row["roll_rating"]), 2),
            "rollRatingSeLower": round(float(row["roll_rating"] - se[i]), 2),
            "rollRatingSeUpper": round(float(row["roll_rating"] + se[i]), 2),
            "rollXg90": round(float(row["roll_xg"]), 3),
            "rollGoals90": round(float(row["roll_goals"]), 3),
            "team": team,
            "opponent": opponent,
            "score": score_str if score_str else None,
        })

    return {
        "playerSlug": player_slug,
        "playerName": name,
        "nMatches": n,
        "window": window,
        "seasonAvg": {
            "rating": round(season_rating, 2),
            "xg90": round(season_xg, 3),
            "goals90": round(season_goals, 3),
        },
        "points": points,
    }


def main():
    player = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_PLAYER_SLUG
    data = export_form(player)
    web_data = ROOT / "web" / "public" / "data" / "player" / player
    web_data.mkdir(parents=True, exist_ok=True)
    out_path = web_data / "form.json"
    with open(out_path, "w") as f:
        json.dump(data, f, indent=2)
    print(f"Wrote {out_path}")


if __name__ == "__main__":
    main()
