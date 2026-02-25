"""
Step 3: Aggregate player_appearances by (player_id, season, competition_slug):
totals, per-90 stats, incidents (goals, assists, cards), sufficient_minutes flag.
Output: data/processed/03_player_season_stats.parquet
"""

import sys
from pathlib import Path

import pandas as pd
import numpy as np

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

from scripts.build.utils import (
    DERIVED_DIR,
    PROCESSED_DIR,
    STAT_COLS,
    MIN_MINUTES_SEASON,
    per90,
)

def main():
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    app = pd.read_parquet(DERIVED_DIR / "player_appearances.parquet")
    app["match_id"] = app["match_id"].astype(str)
    # Include rows with at least some minutes for aggregation
    app = app[app["stat_minutesPlayed"].fillna(0) >= 1].copy()
    app["minutes"] = app["stat_minutesPlayed"].astype(float)

    incidents = pd.read_parquet(DERIVED_DIR / "player_incidents.parquet")
    incidents["match_id"] = incidents["match_id"].astype(str)
    incidents["player_id"] = pd.to_numeric(incidents["player_id"], errors="coerce")

    id_cols = ["player_id", "season", "competition_slug"]
    # Identity (first per group) and DOB for age
    identity = app.groupby(id_cols).agg(
        player_name=("player_name", "first"),
        player_shortName=("player_shortName", "first"),
        player_position=("player_position", "first"),
        player_dateOfBirthTimestamp=("player_dateOfBirthTimestamp", "first") if "player_dateOfBirthTimestamp" in app.columns else ("player_id", "first"),
    ).reset_index()
    if "player_dateOfBirthTimestamp" not in identity.columns:
        identity["player_dateOfBirthTimestamp"] = np.nan

    # Appearances / minutes
    app_agg = app.groupby(id_cols).agg(
        appearances=("match_id", "nunique"),
        starts=("substitute", lambda s: (s == False).sum()),
        total_minutes=("minutes", "sum"),
    ).reset_index()
    app_agg["sub_appearances"] = app_agg["appearances"] - app_agg["starts"]
    app_agg["avg_minutes_per_game"] = app_agg["total_minutes"] / app_agg["appearances"]
    app_agg["sufficient_minutes"] = app_agg["total_minutes"] >= MIN_MINUTES_SEASON

    # Rating average (exclude nulls)
    rating_agg = app.groupby(id_cols)["stat_rating"].apply(lambda x: x.dropna().mean()).reset_index(name="avg_rating")

    # Totals for every stat column that exists
    stat_cols = [c for c in STAT_COLS if c in app.columns]
    totals = app.groupby(id_cols)[stat_cols].sum().reset_index()

    # Goals / assists from appearances
    if "stat_goals" in app.columns:
        goals_assists = app.groupby(id_cols).agg(
            goals=("stat_goals", "sum"),
            assists=("stat_goalAssist", "sum") if "stat_goalAssist" in app.columns else ("stat_goals", lambda x: 0),
        ).reset_index()
    else:
        goals_assists = app.groupby(id_cols).agg(goals=(id_cols[0], "count")).reset_index()
        goals_assists["goals"] = 0
        goals_assists["assists"] = 0
    if "stat_goalAssist" in app.columns and "assists" not in goals_assists.columns:
        goals_assists["assists"] = app.groupby(id_cols)["stat_goalAssist"].sum().reset_index(drop=True)
    goals_assists["goal_contributions"] = goals_assists["goals"] + goals_assists["assists"]

    # Cards from incidents
    inc_valid = incidents.dropna(subset=["player_id"]).copy()
    inc_valid["season"] = inc_valid["season"].astype(str)
    inc_valid["competition_slug"] = inc_valid["competition_slug"].astype(str)

    def _card_counts(g):
        yellow = ((g["incidentType"] == "card") & g["incidentClass"].astype(str).str.lower().str.contains("yellow", na=False)).sum()
        red = ((g["incidentType"] == "card") & g["incidentClass"].astype(str).str.lower().str.contains("red", na=False)).sum()
        return pd.Series({"yellow_cards": int(yellow), "red_cards": int(red)})
    card_agg = inc_valid.groupby(id_cols, group_keys=False).apply(_card_counts, include_groups=False).reset_index()

    # Age at season start: first match date in that season for player
    app["match_date_utc"] = pd.to_datetime(app["match_date"], unit="s", utc=True)
    first_match = app.groupby(id_cols)["match_date_utc"].min().reset_index(name="first_match_date")
    identity = identity.merge(first_match, on=id_cols, how="left")
    identity["age_at_season_start"] = np.nan
    mask = identity["first_match_date"].notna() & identity["player_dateOfBirthTimestamp"].notna()
    dob_sec = pd.to_numeric(identity.loc[mask, "player_dateOfBirthTimestamp"], errors="coerce")
    first_dt = identity.loc[mask, "first_match_date"]
    first_sec = first_dt.apply(lambda x: x.timestamp() if hasattr(x, "timestamp") else pd.NaT)
    identity.loc[mask, "age_at_season_start"] = (first_sec.values - dob_sec.values) / (365.25 * 24 * 3600)
    identity = identity.drop(columns=["first_match_date", "player_dateOfBirthTimestamp"], errors="ignore")

    # Merge all
    out = identity.merge(app_agg, on=id_cols, how="left")
    out = out.merge(rating_agg, on=id_cols, how="left")
    out = out.merge(goals_assists, on=id_cols, how="left")
    out = out.merge(card_agg, on=id_cols, how="left")
    out["yellow_cards"] = out["yellow_cards"].fillna(0).astype(int)
    out["red_cards"] = out["red_cards"].fillna(0).astype(int)
    out["goals"] = out["goals"].fillna(0).astype(int)
    out["assists"] = out["assists"].fillna(0).astype(int)
    out["goal_contributions"] = out["goal_contributions"].fillna(0).astype(int)

    # Merge totals with renamed columns (total_totalPass, total_accuratePass, ...)
    tot_renamed = totals.rename(columns={c: c.replace("stat_", "total_") for c in stat_cols})
    out = out.merge(tot_renamed, on=id_cols, how="left")

    # Per-90: for each stat, (total / total_minutes) * 90
    mins = out["total_minutes"].astype(float)
    for c in stat_cols:
        total_col = c.replace("stat_", "total_")
        if total_col not in out.columns:
            continue
        out[c.replace("stat_", "") + "_per90"] = per90(out[total_col], mins)

    # Pass accuracy, duel win rate, etc. (ratios) - use total_* column names
    if "total_accuratePass" in out.columns and "total_totalPass" in out.columns:
        out["pass_accuracy"] = out["total_accuratePass"] / out["total_totalPass"].replace(0, np.nan)
    if "total_duelWon" in out.columns and "total_duelLost" in out.columns:
        total_duels = out["total_duelWon"] + out["total_duelLost"]
        out["duel_win_rate"] = out["total_duelWon"] / total_duels.replace(0, np.nan)
    if "total_aerialWon" in out.columns and "total_aerialLost" in out.columns:
        total_aerial = out["total_aerialWon"] + out["total_aerialLost"]
        out["aerial_win_rate"] = out["total_aerialWon"] / total_aerial.replace(0, np.nan)
    if "total_wonTackle" in out.columns and "total_totalTackle" in out.columns:
        out["tackle_success_rate"] = out["total_wonTackle"] / out["total_totalTackle"].replace(0, np.nan)
    if "total_wonContest" in out.columns and "total_totalContest" in out.columns:
        out["dribble_success_rate"] = out["total_wonContest"] / out["total_totalContest"].replace(0, np.nan)
    if "total_accurateCross" in out.columns and "total_totalCross" in out.columns:
        out["cross_accuracy"] = out["total_accurateCross"] / out["total_totalCross"].replace(0, np.nan)
    if "total_accurateLongBalls" in out.columns and "total_totalLongBalls" in out.columns:
        out["long_ball_accuracy"] = out["total_accurateLongBalls"] / out["total_totalLongBalls"].replace(0, np.nan)

    # Value metrics average (plan names: pass_value_avg, shot_value_avg, defensive_value_avg, dribble_value_avg, gk_value_avg)
    value_name_map = {
        "passValueNormalized": "pass_value_avg",
        "shotValueNormalized": "shot_value_avg",
        "defensiveValueNormalized": "defensive_value_avg",
        "dribbleValueNormalized": "dribble_value_avg",
        "goalkeeperValueNormalized": "gk_value_avg",
    }
    for v, out_name in value_name_map.items():
        col = "stat_" + v
        if col in app.columns:
            avg_val = app.groupby(id_cols)[col].mean().reset_index()
            avg_val = avg_val.rename(columns={col: out_name})
            out = out.merge(avg_val, on=id_cols, how="left")

    # Drop total_ stat columns to reduce size (keep total_minutes)
    drop_cols = [c for c in out.columns if c.startswith("total_") and c != "total_minutes"]
    out = out.drop(columns=drop_cols, errors="ignore")

    out_path = PROCESSED_DIR / "03_player_season_stats.parquet"
    out.to_parquet(out_path, index=False)
    print(f"Wrote {out_path} ({len(out)} rows)")


if __name__ == "__main__":
    main()
