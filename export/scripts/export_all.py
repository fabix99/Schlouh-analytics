"""
Export all chart data as JSON for the web app.
Run from project root: python export/scripts/export_all.py [player_slug] [player_slug_2]
Writes to web/public/data/ (served by the web app).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from viz.config import DEFAULT_PLAYER_SLUG, DEFAULT_PLAYER_SLUG_2
from viz.data_utils import (
    FORWARD_RADAR_COLS,
    VALUE_COLS,
    get_season_competition,
    load_appearances,
    load_player,
    rolling_mean,
    rolling_std,
    season_aggregates,
    cv_band,
)


def cv(series: pd.Series) -> float:
    s = series.dropna()
    if len(s) < 2 or s.mean() == 0:
        return 0
    return s.std() / abs(s.mean())


def write_json(data: dict, *path_parts: str) -> None:
    web_out = ROOT / "web" / "public" / "data" / Path(*path_parts)
    web_out.parent.mkdir(parents=True, exist_ok=True)
    with open(web_out, "w") as f:
        json.dump(data, f, indent=2)
    print(f"  {web_out}")


def export_form(player_slug: str, window: int = 5, min_min: int = 45) -> dict:
    df = load_player(player_slug)
    if min_min > 0 and "stat_minutesPlayed" in df.columns:
        df = df[df["stat_minutesPlayed"] >= min_min].copy()
    df = df.sort_values("match_date_utc").reset_index(drop=True)
    name = df["player_shortName"].iloc[0] if "player_shortName" in df.columns else player_slug
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
    se = np.clip(se, 0, 2.0)
    points = []
    for i in range(len(df)):
        row = df.iloc[i]
        team = str(row["team"]).strip() if "team" in df.columns and pd.notna(row.get("team")) else (str(row["home_team_name"] if row["side"] == "home" else row["away_team_name"]) if "side" in df.columns and "home_team_name" in df.columns else "")
        opponent = str(row["away_team_name"] if row["side"] == "home" else row["home_team_name"]) if "side" in df.columns and "home_team_name" in df.columns and "away_team_name" in df.columns else ""
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
        "nMatches": len(df),
        "window": window,
        "seasonAvg": {"rating": round(season_rating, 2), "xg90": round(season_xg, 3), "goals90": round(season_goals, 3)},
        "points": points,
    }


def export_momentum(player_slug: str, n_recent: int = 5) -> dict:
    df = load_player(player_slug)
    df = df.sort_values("match_date_utc").reset_index(drop=True)
    name = df["player_shortName"].iloc[0] if "player_shortName" in df.columns else player_slug
    baseline = float(season_aggregates(df).get("stat_rating", 0) or df["stat_rating"].mean() or 7)
    weights = np.array([1.5 ** (n_recent - 1 - i) for i in range(n_recent)])
    weights = weights / weights.sum()
    form_scores = []
    for i in range(len(df)):
        start = max(0, i - n_recent + 1)
        window = df.iloc[start : i + 1]["stat_rating"].values
        w = weights[-len(window) :] / weights[-len(window) :].sum()
        form_scores.append(np.average(window, weights=w) if len(window) > 0 else np.nan)
    points = [
        {"date": df["match_date_utc"].iloc[i].strftime("%Y-%m-%d"), "formScore": round(float(x), 2)}
        for i, x in enumerate(form_scores)
    ]
    return {"playerSlug": player_slug, "playerName": name, "baseline": round(baseline, 2), "points": points}


def export_consistency(player_slug: str, min_min: int = 45) -> dict:
    df = load_player(player_slug)
    if min_min > 0 and "stat_minutesPlayed" in df.columns:
        df = df[df["stat_minutesPlayed"] >= min_min].copy()
    name = df["player_shortName"].iloc[0] if "player_shortName" in df.columns else player_slug
    xg = df["stat_expectedGoals"].fillna(0)
    rating = df["stat_rating"].fillna(0)
    cv_xg, cv_rating = cv(xg), cv(rating)
    return {
        "playerSlug": player_slug,
        "playerName": name,
        "nMatches": len(df),
        "xg": {"mean": round(xg.mean(), 2), "std": round(xg.std(), 2), "cv": round(cv_xg, 2), "band": cv_band(cv_xg), "bins": [round(x, 2) for x in xg.tolist()]},
        "rating": {"mean": round(rating.mean(), 2), "std": round(rating.std(), 2), "cv": round(cv_rating, 2), "band": cv_band(cv_rating), "bins": [round(x, 2) for x in rating.tolist()]},
    }


def export_distribution(player_slug: str, min_min: int = 45) -> dict:
    df = load_player(player_slug)
    if min_min > 0 and "stat_minutesPlayed" in df.columns:
        df = df[df["stat_minutesPlayed"] >= min_min].copy()
    name = df["player_shortName"].iloc[0] if "player_shortName" in df.columns else player_slug
    rating = df["stat_rating"].dropna()
    xg = df["stat_expectedGoals"].fillna(0)
    return {
        "playerSlug": player_slug,
        "playerName": name,
        "nMatches": len(df),
        "rating": {"values": [round(x, 2) for x in rating.tolist()], "mean": round(rating.mean(), 2), "median": round(rating.median(), 2)},
        "xg": {"values": [round(x, 2) for x in xg.tolist()], "mean": round(xg.mean(), 2), "median": round(xg.median(), 2)},
    }


def export_value_breakdown(player_slug: str) -> dict:
    df = load_player(player_slug)
    name = df["player_shortName"].iloc[0] if "player_shortName" in df.columns else player_slug
    total_mins = max(df["stat_minutesPlayed"].sum(), 1)
    labels = ["Pass", "Dribble", "Defend", "Shot"]
    vals = []
    for c in VALUE_COLS:
        if c not in df.columns:
            vals.append(0.0)
        else:
            vals.append(round(float((df[c].fillna(0).sum() / total_mins) * 90), 4))
    return {"playerSlug": player_slug, "playerName": name, "categories": labels, "values": vals}


def export_radar_profile(player_slug: str) -> dict:
    df = load_player(player_slug)
    agg = season_aggregates(df, stat_cols=FORWARD_RADAR_COLS)
    name = df["player_shortName"].iloc[0] if "player_shortName" in df.columns else player_slug
    labels = ["Shots", "xG", "Key passes", "Carries dist", "Progressive carries", "Duels won"]
    cols = ["stat_totalShots", "stat_expectedGoals", "stat_keyPass", "stat_totalBallCarriesDistance", "stat_totalProgressiveBallCarriesDistance", "stat_duelWon"]
    maxes = [6, 1.5, 4, 200, 150, 12]
    vals = [float(agg.get(c, 0) or 0) for c in cols]
    valsNorm = [round(min(v / m, 1.0), 3) for v, m in zip(vals, maxes)]
    return {"playerSlug": player_slug, "playerName": name, "labels": labels, "values": valsNorm}


def export_goal_timeline(player_slug: str) -> dict:
    df = load_player(player_slug)
    df = df.sort_values("match_date_utc").reset_index(drop=True)
    name = df["player_shortName"].iloc[0] if "player_shortName" in df.columns else player_slug
    goals = df.get("incident_goals", df.get("stat_goals", 0))
    assists = df.get("stat_goalAssist", 0)
    if hasattr(goals, "fillna"):
        goals = goals.fillna(0).values
    else:
        goals = np.array([float(goals)] * len(df) if len(df) else [])
    if hasattr(assists, "fillna"):
        assists = assists.fillna(0).values
    else:
        assists = np.array([float(assists)] * len(df) if len(df) else [])
    ga = np.array(goals) + np.array(assists)
    roll_ga = pd.Series(ga).rolling(5, min_periods=1).mean()
    points = []
    for i in range(len(df)):
        points.append({
            "date": df["match_date_utc"].iloc[i].strftime("%Y-%m-%d"),
            "goals": int(goals[i]),
            "assists": int(assists[i]),
            "gPlusA": int(ga[i]),
            "roll5GPlusA": round(float(roll_ga.iloc[i]), 2),
        })
    return {"playerSlug": player_slug, "playerName": name, "points": points}


def export_pass_zones(player_slug: str) -> dict:
    df = load_player(player_slug)
    name = df["player_shortName"].iloc[0] if "player_shortName" in df.columns else player_slug
    total_mins = max(df["stat_minutesPlayed"].sum(), 1)
    mins_90 = total_mins / 90
    if "stat_totalOwnHalfPasses" in df.columns and "stat_totalOppositionHalfPasses" in df.columns:
        own_tot = df["stat_totalOwnHalfPasses"].fillna(0).sum()
        opp_tot = df["stat_totalOppositionHalfPasses"].fillna(0).sum()
        own_acc_v = df["stat_accurateOwnHalfPasses"].fillna(0).sum()
        opp_acc_v = df["stat_accurateOppositionHalfPasses"].fillna(0).sum()
    else:
        total_pass = df["stat_totalPass"].fillna(0).sum()
        total_acc = df["stat_accuratePass"].fillna(0).sum()
        own_tot, opp_tot = total_pass * 0.3, total_pass * 0.7
        own_acc_v, opp_acc_v = total_acc * 0.3, total_acc * 0.7
    own_acc = 100 * own_acc_v / own_tot if own_tot > 0 else 0
    opp_acc = 100 * opp_acc_v / opp_tot if opp_tot > 0 else 0
    return {
        "playerSlug": player_slug,
        "playerName": name,
        "ownHalf": {"total": int(own_tot), "per90": round(own_tot / mins_90, 1), "accuracy": round(own_acc, 1)},
        "oppositionHalf": {"total": int(opp_tot), "per90": round(opp_tot / mins_90, 1), "accuracy": round(opp_acc, 1)},
    }


def export_percentiles(player_slug: str, competition: str = "spain-laliga", position: str = "F", min_min: int = 450) -> Optional[dict]:
    df = load_appearances(competition)
    if df.empty:
        return None
    total_mins = df.groupby("player_id")["stat_minutesPlayed"].sum()
    eligible = total_mins[total_mins >= min_min].index
    df = df[df["player_id"].isin(eligible)]
    if position:
        df = df[df["player_position"] == position]
    metrics = [
        ("stat_rating", "Rating"),
        ("stat_expectedGoals", "xG/90"),
        ("stat_expectedAssists", "xA/90"),
        ("stat_totalShots", "Shots/90"),
        ("stat_keyPass", "Key passes/90"),
        ("stat_totalProgressiveBallCarriesDistance", "Prog carries/90"),
        ("stat_duelWon", "Duels won/90"),
    ]
    def agg_one(g):
        s = g["stat_minutesPlayed"].sum()
        if s <= 0:
            out = {c: 0.0 for c, _ in metrics}
            out["stat_rating"] = 0.0
            return pd.Series(out)
        out = {c: g[c].sum() / s * 90 for c, _ in metrics}
        out["stat_rating"] = g["stat_rating"].mean()
        return pd.Series(out)
    agg = df.groupby("player_id", group_keys=False).apply(agg_one).reset_index()
    player_df = load_player(player_slug)
    pid = int(player_df["player_id"].iloc[0])
    name = player_df["player_shortName"].iloc[0] if "player_shortName" in player_df.columns else player_slug
    player_row = agg[agg["player_id"] == pid]
    if player_row.empty:
        return None
    labels = []
    percentiles = []
    for col, label in metrics:
        vals = agg[col].dropna()
        pval = player_row[col].iloc[0]
        pct = (vals < pval).sum() / len(vals) * 100 if len(vals) > 0 else 50
        labels.append(label)
        percentiles.append(round(pct, 1))
    return {
        "playerSlug": player_slug,
        "playerName": name,
        "competition": competition,
        "position": position,
        "nPeers": len(agg),
        "metrics": labels,
        "percentiles": percentiles,
    }


def export_compare_bar(player1: str, player2: str) -> dict:
    df1, df2 = load_player(player1), load_player(player2)
    agg1, agg2 = season_aggregates(df1), season_aggregates(df2)
    name1 = df1["player_shortName"].iloc[0] if "player_shortName" in df1.columns else player1
    name2 = df2["player_shortName"].iloc[0] if "player_shortName" in df2.columns else player2
    metrics = [
        ("stat_rating", "Rating"),
        ("stat_expectedGoals", "xG/90"),
        ("stat_expectedAssists", "xA/90"),
        ("stat_totalShots", "Shots/90"),
        ("stat_keyPass", "Key passes/90"),
        ("stat_totalBallCarriesDistance", "Carry dist/90"),
        ("stat_duelWon", "Duels won/90"),
    ]
    v1 = [float(agg1.get(c, 0) or 0) for c, _ in metrics]
    v2 = [float(agg2.get(c, 0) or 0) for c, _ in metrics]
    v1[0], v2[0] = float(df1["stat_rating"].mean()), float(df2["stat_rating"].mean())
    return {
        "player1": {"slug": player1, "name": name1, "values": [round(x, 3) for x in v1]},
        "player2": {"slug": player2, "name": name2, "values": [round(x, 3) for x in v2]},
        "metrics": [m[1] for m in metrics],
    }


def export_penalty(player_slug: str) -> dict:
    df = load_player(player_slug)
    name = df["player_shortName"].iloc[0] if "player_shortName" in df.columns else player_slug
    pg = df.get("incident_penalty_goals", 0)
    pm = df.get("incident_penalty_missed", 0)
    scored = int(pg.sum()) if hasattr(pg, "sum") else (int(pg) if pd.notna(pg) else 0)
    missed = int(pm.sum()) if hasattr(pm, "sum") else (int(pm) if pd.notna(pm) else 0)
    total = scored + missed
    conv = round(100 * scored / total, 1) if total > 0 else 0
    return {
        "playerSlug": player_slug,
        "playerName": name,
        "scored": scored,
        "missed": missed,
        "total": total,
        "conversionPct": conv,
    }


def export_card_risk(player_slug: str) -> dict:
    df = load_player(player_slug)
    df = df.sort_values("match_date_utc").copy()
    name = df["player_shortName"].iloc[0] if "player_shortName" in df.columns else player_slug
    yellow = df.get("incident_yellow_cards", pd.Series(0)).fillna(0)
    red = df.get("incident_red_cards", pd.Series(0)).fillna(0)
    cards = yellow + red
    fouls = df["stat_fouls"].fillna(0)
    mins = df["stat_minutesPlayed"].fillna(90).replace(0, 1)
    cards_per90 = (cards / mins * 90).tolist()
    fouls_per90 = (fouls / mins * 90).tolist()
    dates = df["match_date_utc"].astype(str).str[:10].tolist()
    return {
        "playerSlug": player_slug,
        "playerName": name,
        "points": [{"date": d, "cardsPer90": round(c, 3), "foulsPer90": round(f, 3)} for d, c, f in zip(dates, cards_per90, fouls_per90)],
        "avgCardsPer90": round(float(pd.Series(cards_per90).mean()), 3),
    }


def export_matrix_compare(player1: str, player2: str) -> dict:
    df1, df2 = load_player(player1), load_player(player2)
    agg1, agg2 = season_aggregates(df1), season_aggregates(df2)
    name1 = df1["player_shortName"].iloc[0] if "player_shortName" in df1.columns else player1
    name2 = df2["player_shortName"].iloc[0] if "player_shortName" in df2.columns else player2
    metrics = [
        ("stat_rating", "Rating"),
        ("stat_expectedGoals", "xG/90"),
        ("stat_expectedAssists", "xA/90"),
        ("stat_totalShots", "Shots/90"),
        ("stat_keyPass", "Key passes/90"),
        ("stat_totalBallCarriesDistance", "Carry dist/90"),
        ("stat_duelWon", "Duels won/90"),
    ]
    if "stat_rating" in df1.columns:
        agg1 = agg1.copy()
        agg1["stat_rating"] = df1["stat_rating"].mean()
    if "stat_rating" in df2.columns:
        agg2 = agg2.copy()
        agg2["stat_rating"] = df2["stat_rating"].mean()
    labels = [m[1] for m in metrics]
    cols = [m[0] for m in metrics]
    v1 = [float(agg1.get(c, 0) or 0) for c in cols]
    v2 = [float(agg2.get(c, 0) or 0) for c in cols]
    rows = []
    for i, (a, b) in enumerate(zip(v1, v2)):
        winner = name1 if a > b else (name2 if b > a else "Tie")
        effect = "" if a == b else f"{100 * (a - b) / (b or 1):+.0f}%"
        rows.append({"metric": labels[i], "player1Value": round(a, 3), "player2Value": round(b, 3), "winner": winner, "effectPct": effect})
    season1, comp1 = get_season_competition(df1)
    _, comp2 = get_season_competition(df2)
    context = comp1 if (comp1 and comp2 and comp1 == comp2) else ""
    return {
        "player1": {"slug": player1, "name": name1},
        "player2": {"slug": player2, "name": name2},
        "competition": context,
        "rows": rows,
    }


def export_radar_compare(player1: str, player2: str) -> dict:
    df1, df2 = load_player(player1), load_player(player2)
    agg1 = season_aggregates(df1, stat_cols=FORWARD_RADAR_COLS)
    agg2 = season_aggregates(df2, stat_cols=FORWARD_RADAR_COLS)
    name1 = df1["player_shortName"].iloc[0] if "player_shortName" in df1.columns else player1
    name2 = df2["player_shortName"].iloc[0] if "player_shortName" in df2.columns else player2
    labels = ["xG", "Shots", "Key passes", "Carries dist", "Progressive carries", "Duels won"]
    cols = FORWARD_RADAR_COLS
    vals1 = [float(agg1.get(c, 0) or 0) for c in cols]
    vals2 = [float(agg2.get(c, 0) or 0) for c in cols]
    maxes = [1.5, 6, 4, 200, 150, 12]
    vals1_norm = [round(min(v / m, 1.0), 3) for v, m in zip(vals1, maxes)]
    vals2_norm = [round(min(v / m, 1.0), 3) for v, m in zip(vals2, maxes)]
    season1, comp1 = get_season_competition(df1)
    season2, comp2 = get_season_competition(df2)
    same_league = comp1 and comp2 and comp1 == comp2
    return {
        "player1": {"slug": player1, "name": name1, "values": vals1_norm},
        "player2": {"slug": player2, "name": name2, "values": vals2_norm},
        "labels": labels,
        "sameLeague": same_league,
        "competition": comp1 if same_league else "",
    }


def export_scatter_compare(
    player1: str,
    player2: str,
    competition: str = "spain-laliga",
    min_minutes: int = 450,
) -> Optional[dict]:
    df = load_appearances(competition)
    if df.empty:
        return None
    total_mins = df.groupby("player_id")["stat_minutesPlayed"].sum()
    eligible = total_mins[total_mins >= min_minutes].index
    df = df[df["player_id"].isin(eligible)]

    def agg_one(g):
        s = g["stat_minutesPlayed"].sum()
        if s <= 0:
            return pd.Series({"xg_per90": 0.0, "xa_per90": 0.0, "player_slug": "", "player_name": ""})
        return pd.Series({
            "xg_per90": g["stat_expectedGoals"].sum() / s * 90,
            "xa_per90": g["stat_expectedAssists"].sum() / s * 90,
            "player_slug": g["player_slug"].iloc[0] if "player_slug" in g.columns else "",
            "player_name": g["player_shortName"].iloc[0] if "player_shortName" in g.columns else "",
        })
    agg = df.groupby("player_id", group_keys=False).apply(agg_one).reset_index()
    df1 = load_player(player1)
    df2 = load_player(player2)
    pid1 = int(df1["player_id"].iloc[0])
    pid2 = int(df2["player_id"].iloc[0])
    name1 = df1["player_shortName"].iloc[0] if "player_shortName" in df1.columns else player1
    name2 = df2["player_shortName"].iloc[0] if "player_shortName" in df2.columns else player2
    others = agg[~agg["player_id"].isin([pid1, pid2])]
    p1_row = agg[agg["player_id"] == pid1]
    p2_row = agg[agg["player_id"] == pid2]
    if p1_row.empty or p2_row.empty:
        return None
    p1_row, p2_row = p1_row.iloc[0], p2_row.iloc[0]
    med_xg = round(float(others["xg_per90"].median()), 3)
    med_xa = round(float(others["xa_per90"].median()), 3)
    others_sample = others.head(200).apply(lambda r: {"xg_per90": round(float(r["xg_per90"]), 3), "xa_per90": round(float(r["xa_per90"]), 3)}, axis=1).tolist()
    return {
        "player1": {"slug": player1, "name": name1, "xg_per90": round(float(p1_row["xg_per90"]), 3), "xa_per90": round(float(p1_row["xa_per90"]), 3)},
        "player2": {"slug": player2, "name": name2, "xg_per90": round(float(p2_row["xg_per90"]), 3), "xa_per90": round(float(p2_row["xa_per90"]), 3)},
        "medianXg": med_xg,
        "medianXa": med_xa,
        "others": others_sample,
        "nOthers": len(others),
        "competition": competition,
        "minMinutes": min_minutes,
    }


def export_archetype(competition: str = "spain-laliga", min_minutes: int = 450) -> Optional[dict]:
    df = load_appearances(competition)
    if df.empty:
        return None
    total_mins = df.groupby("player_id")["stat_minutesPlayed"].sum()
    eligible = total_mins[total_mins >= min_minutes].index
    df = df[df["player_id"].isin(eligible)]

    def agg_one(g):
        s = g["stat_minutesPlayed"].sum()
        if s <= 0:
            return pd.Series({"xg_per90": 0.0, "kp_per90": 0.0, "position": "?", "player_name": ""})
        return pd.Series({
            "xg_per90": g["stat_expectedGoals"].sum() / s * 90,
            "kp_per90": g["stat_keyPass"].sum() / s * 90,
            "position": g["player_position"].mode().iloc[0] if "player_position" in g.columns else "?",
            "player_name": g["player_shortName"].iloc[0] if "player_shortName" in g.columns else str(g["player_id"].iloc[0]),
        })
    agg = df.groupby("player_id", group_keys=False).apply(agg_one).reset_index()
    pos_map = {"G": "GK", "D": "Def", "M": "Mid", "F": "Fwd"}
    agg["pos_label"] = agg["position"].map(pos_map).fillna(agg["position"])
    med_xg = round(float(agg["xg_per90"].median()), 3)
    med_kp = round(float(agg["kp_per90"].median()), 3)
    positions = ["GK", "Def", "Mid", "Fwd"]
    points_by_pos: dict = {p: [] for p in positions}
    for _, r in agg.iterrows():
        pos = str(r["pos_label"]) if pd.notna(r["pos_label"]) else "?"
        if pos not in points_by_pos:
            points_by_pos[pos] = []
        points_by_pos[pos].append({"xg_per90": round(float(r["xg_per90"]), 3), "kp_per90": round(float(r["kp_per90"]), 3)})
    return {
        "competition": competition,
        "minMinutes": min_minutes,
        "medianXg": med_xg,
        "medianKp": med_kp,
        "positions": points_by_pos,
        "positionOrder": positions,
    }


def main():
    player = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_PLAYER_SLUG
    player2 = sys.argv[2] if len(sys.argv) > 2 else DEFAULT_PLAYER_SLUG_2

    print("Exporting player charts:", player)
    write_json(export_form(player), "player", player, "form.json")
    write_json(export_momentum(player), "player", player, "momentum.json")
    write_json(export_consistency(player), "player", player, "consistency.json")
    write_json(export_distribution(player), "player", player, "distribution.json")
    write_json(export_value_breakdown(player), "player", player, "value_breakdown.json")
    write_json(export_radar_profile(player), "player", player, "radar_profile.json")
    write_json(export_goal_timeline(player), "player", player, "goal_timeline.json")
    write_json(export_pass_zones(player), "player", player, "pass_zones.json")
    pct = export_percentiles(player)
    if pct:
        write_json(pct, "player", player, "percentiles.json")
    else:
        print("  (skip percentiles: player not in appearances or no data)")

    write_json(export_penalty(player), "player", player, "penalty.json")
    write_json(export_card_risk(player), "player", player, "card_risk.json")

    print("Exporting comparison:", player, "vs", player2)
    write_json(export_compare_bar(player, player2), "compare", f"{player}_vs_{player2}_bar.json")
    write_json(export_matrix_compare(player, player2), "compare", f"{player}_vs_{player2}_matrix.json")
    write_json(export_radar_compare(player, player2), "compare", f"{player}_vs_{player2}_radar.json")
    sc = export_scatter_compare(player, player2)
    if sc:
        write_json(sc, "compare", f"{player}_vs_{player2}_scatter.json")
    else:
        print("  (skip scatter compare: appearances data or player not in league)")

    print("Exporting league archetype (spain-laliga)")
    arch = export_archetype("spain-laliga")
    if arch:
        write_json(arch, "league", "archetype_spain-laliga.json")
    else:
        print("  (skip archetype: no appearances data)")

    print("Done.")


if __name__ == "__main__":
    main()
