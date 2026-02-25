"""
Step 1: Aggregate raw team_statistics.csv into team-season level.
Output: data/processed/01_team_season_stats.parquet
"""

import sys
from pathlib import Path

import pandas as pd
import numpy as np

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

from scripts.build.utils import (
    RAW_DIR,
    PROCESSED_DIR,
    INDEX_DIR,
    parse_ratio,
    parse_pct,
)

# Map stat 'name' to a numeric value. Raw CSV formats:
# - Counts: "7", "12", "345" (Total shots, Tackles, Passes, etc.) -> keep as number.
# - Percentages: "35%", "65%" (Ball possession, Duels %, Tackles won %) -> 0.35, 0.65.
# - Ratios: "38/71 (54%)" (Final third phase, Long balls, etc.) -> 0.54 via parse_ratio.
# We must NOT treat plain counts as percentages (e.g. "7" must stay 7, not 0.07).
def parse_value(s):
    """Parse stat value: ratio (e.g. 23/56), percentage only if '%' in string, else plain number."""
    if pd.isna(s):
        return np.nan
    s = str(s).strip()
    r = parse_ratio(s)
    if r[0] is not None:
        return r[2] if r[1] and r[1] > 0 else np.nan  # return ratio
    # Only treat as percentage if the value explicitly contains '%' (e.g. "35%" or "52%")
    if "%" in s:
        p = parse_pct(s)
        if p is not None:
            return p
    try:
        return float(s)
    except ValueError:
        return np.nan


def iter_team_stat_files():
    """Yield (season, competition_slug, match_id, path) for each team_statistics.csv."""
    if not RAW_DIR.exists():
        return
    for season_dir in sorted(RAW_DIR.iterdir()):
        if not season_dir.is_dir() or season_dir.name.startswith("."):
            continue
        season = season_dir.name
        club = season_dir / "club"
        if not club.exists():
            continue
        for comp_dir in sorted(club.iterdir()):
            if not comp_dir.is_dir() or comp_dir.name.startswith("."):
                continue
            competition_slug = comp_dir.name
            for match_dir in sorted(comp_dir.iterdir()):
                if not match_dir.is_dir() or match_dir.name.startswith("."):
                    continue
                path = match_dir / "team_statistics.csv"
                if path.exists():
                    yield season, competition_slug, match_dir.name, path


def load_matches():
    p = INDEX_DIR / "matches.csv"
    if not p.exists():
        return pd.DataFrame()
    df = pd.read_csv(p)
    df["match_id"] = df["match_id"].astype(str)
    return df


def read_team_stats_one_match(path: Path, period: str = "ALL") -> pd.DataFrame:
    """Read one team_statistics.csv, return long df with parsed numeric values (one row per stat)."""
    df = pd.read_csv(path)
    df = df[df["period"] == period].copy()
    if df.empty:
        return pd.DataFrame()
    # Dedupe by name (take first when duplicate names)
    df = df.drop_duplicates(subset=["name"], keep="first")
    df["home_val"] = df["home"].apply(parse_value)
    df["away_val"] = df["away"].apply(parse_value)
    return df[["name", "home_val", "away_val"]]


def main():
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    matches = load_matches()
    if matches.empty:
        print("No matches index", file=sys.stderr)
        sys.exit(1)
    match_meta = matches.set_index("match_id")[["season", "competition_slug", "home_team_name", "away_team_name"]]

    # Name -> short key for columns (avoid duplicates like two "Total shots")
    name_to_key = {
        "Ball possession": "possession",
        "Expected goals": "xg",
        "Big chances": "big_chances",
        "Total shots": "total_shots",
        "Corner kicks": "corners",
        "Fouls": "fouls",
        "Passes": "passes",
        "Tackles": "tackles",
        "Free kicks": "free_kicks",
        "Yellow cards": "yellow_cards",
        "Shots on target": "shots_on_target",
        "Hit woodwork": "hit_woodwork",
        "Shots off target": "shots_off_target",
        "Blocked shots": "blocked_shots",
        "Shots inside box": "shots_inside_box",
        "Shots outside box": "shots_outside_box",
        "Big chances scored": "big_chances_scored",
        "Big chances missed": "big_chances_missed",
        "Touches in penalty area": "touches_penalty_area",
        "Fouled in final third": "fouled_final_third",
        "Offsides": "offsides",
        "Accurate passes": "accurate_passes",
        "Throw-ins": "throw_ins",
        "Final third entries": "final_third_entries",
        "Final third phase": "final_third_phase",
        "Long balls": "long_balls",
        "Crosses": "crosses",
        "Duels": "duels",
        "Dispossessed": "dispossessed",
        "Ground duels": "ground_duels",
        "Aerial duels": "aerial_duels",
        "Dribbles": "dribbles",
        "Tackles won": "tackles_won",
        "Total tackles": "total_tackles",
        "Interceptions": "interceptions",
        "Recoveries": "recoveries",
        "Clearances": "clearances",
        "Errors lead to a shot": "errors_lead_to_shot",
        "Errors lead to a goal": "errors_lead_to_goal",
        "Total saves": "total_saves",
        "Goals prevented": "goals_prevented",
        "High claims": "high_claims",
        "Punches": "punches",
        "Goal kicks": "goal_kicks",
        "Red cards": "red_cards",
    }

    rows = []
    for season, competition_slug, match_id, path in iter_team_stat_files():
        if match_id not in match_meta.index:
            continue
        meta = match_meta.loc[match_id]
        if meta["season"] != season or meta["competition_slug"] != competition_slug:
            continue
        home_team = meta["home_team_name"]
        away_team = meta["away_team_name"]
        try:
            stats = read_team_stats_one_match(path)
            stats_1st = read_team_stats_one_match(path, period="1ST")
            stats_2nd = read_team_stats_one_match(path, period="2ND")
        except Exception as e:
            print(f"Skip {path}: {e}", file=sys.stderr)
            continue
        if stats.empty:
            continue
        # One row per match per team (home row and away row)
        home_vals = dict(zip(stats["name"], stats["home_val"]))
        away_vals = dict(zip(stats["name"], stats["away_val"]))
        home_row = {"match_id": match_id, "season": season, "competition_slug": competition_slug, "team_name": home_team, "side": "home"}
        away_row = {"match_id": match_id, "season": season, "competition_slug": competition_slug, "team_name": away_team, "side": "away"}
        for name, key in name_to_key.items():
            if name in home_vals:
                home_row[key] = home_vals[name]
                away_row[key] = away_vals.get(name, np.nan)
        # First/second half xG and shots
        if not stats_1st.empty:
            h1 = dict(zip(stats_1st["name"], stats_1st["home_val"]))
            a1 = dict(zip(stats_1st["name"], stats_1st["away_val"]))
            home_row["xg_1st"] = h1.get("Expected goals", np.nan)
            home_row["shots_1st"] = h1.get("Total shots", np.nan)
            away_row["xg_1st"] = a1.get("Expected goals", np.nan)
            away_row["shots_1st"] = a1.get("Total shots", np.nan)
        else:
            home_row["xg_1st"] = np.nan
            home_row["shots_1st"] = np.nan
            away_row["xg_1st"] = np.nan
            away_row["shots_1st"] = np.nan
        if not stats_2nd.empty:
            h2 = dict(zip(stats_2nd["name"], stats_2nd["home_val"]))
            a2 = dict(zip(stats_2nd["name"], stats_2nd["away_val"]))
            home_row["xg_2nd"] = h2.get("Expected goals", np.nan)
            home_row["shots_2nd"] = h2.get("Total shots", np.nan)
            away_row["xg_2nd"] = a2.get("Expected goals", np.nan)
            away_row["shots_2nd"] = a2.get("Total shots", np.nan)
        else:
            home_row["xg_2nd"] = np.nan
            home_row["shots_2nd"] = np.nan
            away_row["xg_2nd"] = np.nan
            away_row["shots_2nd"] = np.nan
        rows.append(home_row)
        rows.append(away_row)

    if not rows:
        print("No team stats rows", file=sys.stderr)
        sys.exit(1)

    df = pd.DataFrame(rows)

    # Join actual goals from match scores
    scores = pd.read_parquet(PROCESSED_DIR / "00_match_scores_full.parquet")
    scores["match_id"] = scores["match_id"].astype(str)
    df = df.merge(scores[["match_id", "home_score", "away_score"]], on="match_id", how="left")
    df["goals_for_match"] = np.where(df["side"] == "home", df["home_score"], df["away_score"])
    df["goals_against_match"] = np.where(df["side"] == "home", df["away_score"], df["home_score"])
    df["goals_for_match"] = pd.to_numeric(df["goals_for_match"], errors="coerce")
    df["goals_against_match"] = pd.to_numeric(df["goals_against_match"], errors="coerce")

    # Aggregate by (team_name, season, competition_slug)
    id_cols = ["team_name", "season", "competition_slug"]
    # Count matches total / home / away
    match_count = df.groupby(id_cols).agg(
        matches_total=("match_id", "nunique"),
        matches_home=("side", lambda s: (s == "home").sum()),
        matches_away=("side", lambda s: (s == "away").sum()),
    ).reset_index()

    # Sum or mean of stats (sum for counting, mean for percentages/ratios)
    sum_cols = [
        "xg", "big_chances", "total_shots", "corners", "fouls", "passes", "tackles",
        "yellow_cards", "shots_on_target", "hit_woodwork", "shots_off_target", "blocked_shots",
        "shots_inside_box", "shots_outside_box", "big_chances_scored", "big_chances_missed",
        "touches_penalty_area", "final_third_entries", "accurate_passes", "throw_ins", "long_balls",
        "crosses", "dispossessed", "total_tackles", "tackles_won", "interceptions", "recoveries",
        "clearances", "errors_lead_to_shot", "errors_lead_to_goal", "total_saves", "goals_prevented",
        "high_claims", "punches", "goal_kicks", "free_kicks", "red_cards",
    ]
    sum_cols = [c for c in sum_cols if c in df.columns]
    mean_cols = [c for c in ["possession", "final_third_phase", "duels", "ground_duels", "aerial_duels", "dribbles"] if c in df.columns]

    agg_dict = {c: (c, "sum") for c in sum_cols}
    for c in mean_cols:
        agg_dict[c] = (c, "mean")
    agg_dict["match_id"] = ("match_id", "count")  # will drop later

    grouped = df.groupby(id_cols)
    sums = grouped[sum_cols].sum().reset_index() if sum_cols else match_count[id_cols].copy()
    means = grouped[mean_cols].mean().reset_index() if mean_cols else match_count[id_cols].copy()

    out = match_count.merge(sums, on=id_cols, how="left")
    if mean_cols:
        out = out.merge(means, on=id_cols, how="left", suffixes=("", "_mean"))
    # Rename for clarity
    out = out.rename(columns={
        "xg": "xg_for_total",
        "total_shots": "shots_total",
        "shots_on_target": "shots_on_target",
        "big_chances": "big_chances_total",
        "big_chances_scored": "big_chances_scored",
        "big_chances_missed": "big_chances_missed",
        "accurate_passes": "accurate_passes_total",
        "passes": "passes_total",
        "possession": "possession_avg",
        "total_tackles": "tackles_total",
        "tackles_won": "tackles_won",
        "interceptions": "interceptions_total",
        "clearances": "clearances_total",
        "recoveries": "recoveries_total",
        "total_saves": "goalkeeper_saves_total",
        "yellow_cards": "yellow_cards_total",
        "red_cards": "red_cards_total",
        "fouls": "fouls_total",
        "corners": "corners_total",
    })
    # Home/away split: aggregate separately for xg etc.
    home_agg = df[df["side"] == "home"].groupby(id_cols).agg(
        xg_for_home=("xg", "sum"),
        goals_for_home=("xg", "count"),  # placeholder; we don't have goals in team_statistics
    ).reset_index()
    away_agg = df[df["side"] == "away"].groupby(id_cols).agg(
        xg_for_away=("xg", "sum"),
    ).reset_index()
    out = out.merge(home_agg[id_cols + ["xg_for_home"]], on=id_cols, how="left")
    out = out.merge(away_agg[id_cols + ["xg_for_away"]], on=id_cols, how="left")
    # xg_against: for each team, sum of opponent xg (so for home team, xg_against = away team's xg in those matches)
    # Simpler: skip xg_against for now and add in step 2 from match summary if needed. Plan says xg_against_total etc.
    # We have xg_for_total = sum of xg in all matches. xg_against = sum of opponent xg. So we need per-match opponent xg.
    # For each row in df we have team_name and match_id; opponent xg = the other row's xg for that match. So:
    match_xg = df[["match_id", "team_name", "season", "competition_slug", "xg"]].copy()
    match_xg = match_xg.rename(columns={"xg": "xg_for"})
    # Pivot to get home_xg, away_xg per match
    match_wide = df.pivot_table(index=["match_id", "season", "competition_slug"], columns="side", values="xg").reset_index()
    match_wide = match_wide.rename(columns={"home": "home_xg", "away": "away_xg"})
    # For each team, xg_against in a match = opponent's xg. So for home_team_name, xg_against = away_xg; for away_team_name, xg_against = home_xg.
    home_team_xg_against = df[df["side"] == "home"][["match_id", "season", "competition_slug", "team_name"]].copy()
    home_team_xg_against = home_team_xg_against.merge(match_wide[["match_id", "away_xg"]], on="match_id")
    home_team_xg_against = home_team_xg_against.rename(columns={"away_xg": "xg_against"})
    away_team_xg_against = df[df["side"] == "away"][["match_id", "season", "competition_slug", "team_name"]].copy()
    away_team_xg_against = away_team_xg_against.merge(match_wide[["match_id", "home_xg"]], on="match_id")
    away_team_xg_against = away_team_xg_against.rename(columns={"home_xg": "xg_against"})
    xg_against_agg = pd.concat([home_team_xg_against, away_team_xg_against]).groupby(id_cols)["xg_against"].sum().reset_index()
    xg_against_agg = xg_against_agg.rename(columns={"xg_against": "xg_against_total"})
    out = out.merge(xg_against_agg, on=id_cols, how="left")

    # Goals for/against/diff from match scores
    goals_agg = df.groupby(id_cols).agg(
        goals_for=("goals_for_match", "sum"),
        goals_against=("goals_against_match", "sum"),
    ).reset_index()
    goals_agg["goal_diff"] = goals_agg["goals_for"] - goals_agg["goals_against"]
    out = out.merge(goals_agg, on=id_cols, how="left")

    # First/second half aggregates
    if "xg_1st" in df.columns:
        half_agg = df.groupby(id_cols).agg(
            xg_for_first_half=("xg_1st", "sum"),
            xg_for_second_half=("xg_2nd", "sum"),
            shots_first_half=("shots_1st", "sum"),
            shots_second_half=("shots_2nd", "sum"),
        ).reset_index()
        out = out.merge(half_agg, on=id_cols, how="left")

    if "goals_for_home" in out.columns:
        out = out.drop(columns=["goals_for_home"])

    # Pass accuracy ratio
    if "accurate_passes_total" in out.columns and "passes_total" in out.columns:
        out["pass_accuracy_avg"] = out["accurate_passes_total"] / out["passes_total"].replace(0, np.nan)

    out_path = PROCESSED_DIR / "01_team_season_stats.parquet"
    out.to_parquet(out_path, index=False)
    print(f"Wrote {out_path} ({len(out)} rows)")


if __name__ == "__main__":
    main()
