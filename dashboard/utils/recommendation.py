"""Team recommendation and narrative helpers for the Profile (scouting) page.

Holds get_teams_for_recommendation, get_team_data_for_fit, and build_player_narrative_blobs
so the Profile page does not depend on dashboard.utils.data loading successfully.
"""

from __future__ import annotations

from typing import Any, List, Optional

import numpy as np
import pandas as pd


def get_teams_for_recommendation(season: str | None = None) -> list:
    """
    List of teams for "Recommendation for [Team]" selector.
    Current season only; one entry per team (aggregate across all competitions).
    Returns list of dicts with "team_name" and "label" (team name only).
    """
    from dashboard.utils.constants import CURRENT_SEASON
    from dashboard.utils.data import load_team_season_stats, load_tactical_profiles

    use_season = season or CURRENT_SEASON
    team_stats = load_team_season_stats()
    tactical = load_tactical_profiles()
    team_key = "team_name" if "team_name" in (team_stats.columns if not team_stats.empty else []) else "team"
    if not team_stats.empty and "season" in team_stats.columns:
        df = team_stats[team_stats["season"].astype(str) == str(use_season)]
        teams = df[team_key].dropna().unique().tolist() if team_key in df.columns else []
    elif not tactical.empty and "season" in tactical.columns:
        tc = "team_name" if "team_name" in tactical.columns else "team"
        df = tactical[tactical["season"].astype(str) == str(use_season)]
        teams = df[tc].dropna().unique().tolist() if tc in df.columns else []
    else:
        teams = []
    return [{"team_name": t, "label": str(t)} for t in sorted(teams)]


def get_team_data_for_fit(
    team_name: str,
    season: str,
    competition_slug: str,
    df_all: pd.DataFrame,
    team_stats_df: pd.DataFrame,
    tactical_df: pd.DataFrame,
) -> tuple:
    """
    Build team_data Series for calculate_fit_score: 01 row + position averages from df_all.
    Returns (team_data_series, team_tactical_row or None).
    """
    team_key_01 = "team_name" if "team_name" in team_stats_df.columns else "team"
    tr = team_stats_df[
        (team_stats_df[team_key_01].astype(str) == str(team_name))
        & (team_stats_df["season"].astype(str) == str(season))
        & (team_stats_df["competition_slug"].astype(str) == str(competition_slug))
    ]
    team_row = tr.iloc[0].copy() if not tr.empty else pd.Series(dtype=object)
    subset = df_all[
        (df_all["team"].astype(str) == str(team_name))
        & (df_all["season"].astype(str) == str(season))
        & (df_all["competition_slug"].astype(str) == str(competition_slug))
    ]
    pos_stats = [
        "goals_per90", "expectedGoals_per90", "keyPass_per90", "expectedAssists_per90",
        "pass_accuracy", "duelWon_per90", "interceptionWon_per90", "totalTackle_per90",
        "aerialWon_per90", "saves_per90", "goalsPrevented_per90",
    ]
    for pos in ["F", "M", "D", "G"]:
        sub = subset[subset["player_position"] == pos]
        if sub.empty:
            continue
        for stat in pos_stats:
            if stat not in sub.columns:
                continue
            col = f"{pos}_{stat}_avg"
            team_row[col] = sub[stat].mean()
    tactical_row = None
    if not tactical_df.empty:
        tc = "team_name" if "team_name" in tactical_df.columns else "team"
        tac = tactical_df[
            (tactical_df[tc].astype(str) == str(team_name))
            & (tactical_df["season"].astype(str) == str(season))
            & (tactical_df["competition_slug"].astype(str) == str(competition_slug))
        ]
        if not tac.empty:
            tactical_row = tac.iloc[0]
    return (team_row, tactical_row)


def get_team_data_for_fit_aggregated(
    team_name: str,
    season: str,
    df_all: pd.DataFrame,
    team_stats_df: pd.DataFrame,
    tactical_df: pd.DataFrame,
) -> tuple:
    """
    Build team_data Series for current season aggregated across all competitions.
    One row per team: sums for counting stats, means for rates; tactical = mean of indices.
    Returns (team_data_series, team_tactical_row or None).
    """
    team_key = "team_name" if "team_name" in team_stats_df.columns else "team"
    tr = team_stats_df[
        (team_stats_df[team_key].astype(str) == str(team_name))
        & (team_stats_df["season"].astype(str) == str(season))
    ]
    if tr.empty:
        team_row = pd.Series(dtype=object)
    else:
        # Aggregate across competitions: mean of numeric stats (typical profile)
        id_cols = [c for c in ["team_name", "team", "season"] if c in tr.columns]
        numeric = [c for c in tr.columns if c not in id_cols and pd.api.types.is_numeric_dtype(tr[c])]
        agg = {c: tr[c].iloc[0] for c in id_cols}
        for c in numeric:
            agg[c] = tr[c].mean()
        team_row = pd.Series(agg)
    # Position averages from df_all: team + season, all competitions
    subset = df_all[
        (df_all["team"].astype(str) == str(team_name))
        & (df_all["season"].astype(str) == str(season))
    ]
    pos_stats = [
        "goals_per90", "expectedGoals_per90", "keyPass_per90", "expectedAssists_per90",
        "pass_accuracy", "duelWon_per90", "interceptionWon_per90", "totalTackle_per90",
        "aerialWon_per90", "saves_per90", "goalsPrevented_per90",
    ]
    for pos in ["F", "M", "D", "G"]:
        sub = subset[subset["player_position"] == pos]
        if sub.empty:
            continue
        for stat in pos_stats:
            if stat not in sub.columns:
                continue
            team_row[f"{pos}_{stat}_avg"] = sub[stat].mean()
    tactical_row = None
    if not tactical_df.empty:
        tc = "team_name" if "team_name" in tactical_df.columns else "team"
        tac = tactical_df[
            (tactical_df[tc].astype(str) == str(team_name))
            & (tactical_df["season"].astype(str) == str(season))
        ]
        if not tac.empty:
            # Mean of tactical indices across competitions
            num = tac.select_dtypes(include=[np.number])
            tactical_row = num.mean()
    return (team_row, tactical_row)


def build_player_narrative_blobs(
    prow: "pd.Series",
    badges: "Optional[List[Any]]",
    form_row: "Optional[pd.DataFrame]",
    scout_row: "Optional[pd.Series]",
    fit_result: "Optional[dict]",
    performance_index_label: "Optional[str]" = None,
    pool_label: "Optional[str]" = None,
) -> tuple:
    """
    Rule-based scouting narrative in three blobs: role, strengths, concerns.
    Used for Profile page executive summary.
    """
    from dashboard.utils.constants import POSITION_NAMES

    name = prow.get("player_name", "Player")
    pos = prow.get("player_position", "?")
    pos_label = POSITION_NAMES.get(pos, pos)
    team = prow.get("team", "?")
    league = prow.get("league_name", prow.get("competition_slug", "?"))
    season = prow.get("season", "?")
    age = int(prow.get("age_at_season_start", 0))
    mins = int(prow.get("total_minutes", 0))
    rating = prow.get("avg_rating")
    role_para = (
        f"{name} is a {pos_label} at {team} in {league}, {season}. "
        f"{age} years old, {mins:,} minutes, {rating:.2f} average rating."
        if pd.notna(rating) else
        f"{name} is a {pos_label} at {team} in {league}, {season}. {age} years old, {mins:,} minutes."
    )
    if performance_index_label and pool_label:
        role_para += f" Performance index: {performance_index_label} in comparison pool ({pool_label})."

    strength_parts = []
    if badges:
        positive = [b for b in badges if getattr(b, "is_positive", True)]
        if positive:
            names = [getattr(b, "name", str(b)) for b in positive]
            descs = [getattr(b, "description", "") for b in positive]
            strength_parts.append("Strengths include " + ", ".join(names) + ": " + "; ".join(d for d in descs if d) + ".")
        else:
            strength_parts.append("No standout strength badges this season; see key percentiles and radar below.")
    if scout_row is not None and not strength_parts:
        for i in range(1, 4):
            sname = scout_row.get(f"top_pct_stat_{i}_name")
            spct = scout_row.get(f"top_pct_stat_{i}_pct")
            if pd.notna(sname) and pd.notna(spct) and spct >= 70:
                label = sname.replace("_per90", "/90").replace("_", " ").title()
                strength_parts.append(f"Top strength: {label} ({spct:.0f}th percentile).")
    strengths_para = " ".join(strength_parts) if strength_parts else "No standout strength badges this season; see key percentiles and radar below."

    concern_parts = []
    if badges:
        negative = [b for b in badges if not getattr(b, "is_positive", True)]
        if negative:
            names = [getattr(b, "name", str(b)) for b in negative]
            descs = [getattr(b, "description", "") for b in negative]
            concern_parts.append("Concerns: " + ", ".join(names) + ": " + "; ".join(d for d in descs if d) + ".")
    if fit_result and fit_result.get("selected_team_label"):
        pct = fit_result.get("recommendation_pct", fit_result.get("overall_score", 0))
        label = fit_result.get("recommendation_label", "")
        expl = fit_result.get("explanation", "")
        if "Statistical match" in expl or "Squad upgrade:" in expl or "/100" in expl:
            if pct >= 70:
                expl = "He would strengthen the squad and fits our style."
            elif pct >= 55:
                expl = "He would add to the squad but may need a clear role or time to adapt."
            else:
                expl = "Doesn't align well with our profile."
        concern_parts.append(
            f"For {fit_result['selected_team_label']}, recommendation is {pct:.0f}% ({label}). {expl}"
        )
    elif fit_result is not None:
        concern_parts.append("Select a team above to see how he fits a specific club.")
    concerns_para = " ".join(concern_parts) if concern_parts else ""

    return (role_para, strengths_para, concerns_para)
