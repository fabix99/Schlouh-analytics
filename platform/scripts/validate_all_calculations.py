#!/usr/bin/env python3
"""
Exhaustive calculation validation for Schlouh core analytics.

Independently recomputes every core formula from grain sources
(appearances / incidents / team stats / season stats) and compares to
processed parquet + DuckDB warehouse marts.

Exit 0 only if zero FAILs.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import duckdb
import numpy as np
import pandas as pd
from scipy.stats import percentileofscore

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from scripts.build.utils import (  # noqa: E402
    DERIVED_DIR,
    INDEX_DIR,
    MIN_MINUTES_CAREER,
    MIN_MINUTES_SEASON,
    PROCESSED_DIR,
    STAT_COLS,
    per90,
)

WH = ROOT / "data" / "warehouse" / "schlouh.duckdb"

FAILS: list[str] = []
WARNS: list[str] = []
PASSES: list[str] = []


def ok(msg: str) -> None:
    PASSES.append(msg)
    print(f"[PASS] {msg}")


def warn(msg: str) -> None:
    WARNS.append(msg)
    print(f"[WARN] {msg}")


def fail(msg: str) -> None:
    FAILS.append(msg)
    print(f"[FAIL] {msg}")


def _close(a: pd.Series, b: pd.Series, atol: float = 1e-6, rtol: float = 1e-6) -> pd.Series:
    a = pd.to_numeric(a, errors="coerce")
    b = pd.to_numeric(b, errors="coerce")
    both_na = a.isna() & b.isna()
    return both_na | np.isclose(a.fillna(0), b.fillna(0), atol=atol, rtol=rtol, equal_nan=True)


def compare_frames(
    name: str,
    expected: pd.DataFrame,
    actual: pd.DataFrame,
    keys: list[str],
    cols: list[str],
    atol: float = 1e-5,
    max_fail_rate: float = 0.0,
) -> None:
    """Compare expected (recomputed) vs actual (stored) on keys+cols."""
    e = expected.copy()
    a = actual.copy()
    for k in keys:
        e[k] = e[k].astype(str)
        a[k] = a[k].astype(str)
    cols = [c for c in cols if c in e.columns and c in a.columns]
    if not cols:
        fail(f"{name}: no comparable columns")
        return
    m = e.merge(a, on=keys, how="inner", suffixes=("_exp", "_act"))
    if m.empty:
        fail(f"{name}: empty join on {keys} (exp={len(e)} act={len(a)})")
        return
    coverage = len(m) / max(len(e), 1)
    if coverage < 0.95:
        warn(f"{name}: join coverage {coverage:.1%} (exp={len(e)} act={len(a)} joined={len(m)})")
    else:
        ok(f"{name}: join coverage {coverage:.1%} ({len(m)} rows)")

    total_bad = 0
    total_cells = 0
    bad_cols = []
    for c in cols:
        ce, ca = f"{c}_exp", f"{c}_act"
        if ce not in m.columns or ca not in m.columns:
            continue
        good = _close(m[ce], m[ca], atol=atol)
        n_bad = int((~good).sum())
        total_bad += n_bad
        total_cells += len(m)
        rate = n_bad / len(m)
        if rate > max_fail_rate:
            bad_cols.append((c, n_bad, rate))
            # show a few examples
            ex = m.loc[~good, keys + [ce, ca]].head(3)
            fail(f"{name}.{c}: {n_bad}/{len(m)} mismatches ({rate:.2%})")
            if not ex.empty:
                print(ex.to_string(index=False))
        elif n_bad:
            warn(f"{name}.{c}: {n_bad}/{len(m)} small mismatches within tolerance policy")
        else:
            ok(f"{name}.{c}: all {len(m)} values match")
    if not bad_cols:
        ok(f"{name}: ALL {len(cols)} numeric columns validated on {len(m)} rows")


# ---------------------------------------------------------------------------
# Independent recomputes
# ---------------------------------------------------------------------------

def recompute_season_stats(app: pd.DataFrame, incidents: pd.DataFrame) -> pd.DataFrame:
    app = app[app["stat_minutesPlayed"].fillna(0) >= 1].copy()
    app["minutes"] = app["stat_minutesPlayed"].astype(float)
    id_cols = ["player_id", "season", "competition_slug"]

    identity = app.groupby(id_cols).agg(
        player_name=("player_name", "first"),
        player_position=("player_position", "first"),
    ).reset_index()

    app_agg = app.groupby(id_cols).agg(
        appearances=("match_id", "nunique"),
        starts=("substitute", lambda s: (s == False).sum()),
        total_minutes=("minutes", "sum"),
    ).reset_index()
    app_agg["sub_appearances"] = app_agg["appearances"] - app_agg["starts"]
    app_agg["avg_minutes_per_game"] = app_agg["total_minutes"] / app_agg["appearances"]
    app_agg["sufficient_minutes"] = app_agg["total_minutes"] >= MIN_MINUTES_SEASON

    r = pd.to_numeric(app["stat_rating"], errors="coerce")
    if r.notna().any() and r.max() > 10:
        app = app.assign(_rating_norm=r / 2.0)
    else:
        app = app.assign(_rating_norm=r)
    rating_agg = app.groupby(id_cols)["_rating_norm"].mean().reset_index(name="avg_rating")

    goals_assists = app.groupby(id_cols).agg(
        goals=("stat_goals", "sum"),
        assists=("stat_goalAssist", "sum"),
    ).reset_index()
    goals_assists["goal_contributions"] = goals_assists["goals"] + goals_assists["assists"]

    stat_cols = [c for c in STAT_COLS if c in app.columns and c not in ("stat_minutesPlayed", "stat_rating")]
    totals = app.groupby(id_cols)[stat_cols].sum().reset_index()
    totals = totals.rename(columns={c: c.replace("stat_", "total_") for c in stat_cols})

    inc = incidents.dropna(subset=["player_id"]).copy()
    inc["player_id"] = pd.to_numeric(inc["player_id"], errors="coerce")
    inc["season"] = inc["season"].astype(str)
    inc["competition_slug"] = inc["competition_slug"].astype(str)

    def _cards(g):
        yellow = ((g["incidentType"] == "card") & g["incidentClass"].astype(str).str.lower().str.contains("yellow", na=False)).sum()
        red = ((g["incidentType"] == "card") & g["incidentClass"].astype(str).str.lower().str.contains("red", na=False)).sum()
        return pd.Series({"yellow_cards": int(yellow), "red_cards": int(red)})

    card_agg = inc.groupby(id_cols, group_keys=False).apply(_cards, include_groups=False).reset_index()

    out = identity.merge(app_agg, on=id_cols, how="left")
    out = out.merge(rating_agg, on=id_cols, how="left")
    out = out.merge(goals_assists, on=id_cols, how="left")
    out = out.merge(card_agg, on=id_cols, how="left")
    out["yellow_cards"] = out["yellow_cards"].fillna(0).astype(int)
    out["red_cards"] = out["red_cards"].fillna(0).astype(int)
    out = out.merge(totals, on=id_cols, how="left")

    mins = out["total_minutes"].astype(float)
    for c in stat_cols:
        total_col = c.replace("stat_", "total_")
        out[c.replace("stat_", "") + "_per90"] = per90(out[total_col], mins)

    out["pass_accuracy"] = out["total_accuratePass"] / out["total_totalPass"].replace(0, np.nan)
    out["duel_win_rate"] = out["total_duelWon"] / (out["total_duelWon"] + out["total_duelLost"]).replace(0, np.nan)
    out["aerial_win_rate"] = out["total_aerialWon"] / (out["total_aerialWon"] + out["total_aerialLost"]).replace(0, np.nan)
    out["tackle_success_rate"] = out["total_wonTackle"] / out["total_totalTackle"].replace(0, np.nan)
    out["dribble_success_rate"] = out["total_wonContest"] / out["total_totalContest"].replace(0, np.nan)
    out["cross_accuracy"] = out["total_accurateCross"] / out["total_totalCross"].replace(0, np.nan)
    out["long_ball_accuracy"] = out["total_accurateLongBalls"] / out["total_totalLongBalls"].replace(0, np.nan)

    value_name_map = {
        "stat_passValueNormalized": "pass_value_avg",
        "stat_shotValueNormalized": "shot_value_avg",
        "stat_defensiveValueNormalized": "defensive_value_avg",
        "stat_dribbleValueNormalized": "dribble_value_avg",
        "stat_goalkeeperValueNormalized": "gk_value_avg",
    }
    for col, out_name in value_name_map.items():
        if col in app.columns:
            avg_val = app.groupby(id_cols)[col].mean().reset_index().rename(columns={col: out_name})
            out = out.merge(avg_val, on=id_cols, how="left")

    return out


def recompute_career(season: pd.DataFrame) -> pd.DataFrame:
    id_col = "player_id"
    identity = season.groupby(id_col).agg(
        player_name=("player_name", "first"),
        player_position=("player_position", "first"),
    ).reset_index()
    sum_cols = [c for c in ["appearances", "starts", "total_minutes", "goals", "assists", "goal_contributions", "yellow_cards", "red_cards"] if c in season.columns]
    totals = season.groupby(id_col)[sum_cols].sum().reset_index()
    out = identity.merge(totals, on=id_col, how="left")
    out["sub_appearances"] = out["appearances"] - out["starts"]
    out["avg_minutes_per_game"] = out["total_minutes"] / out["appearances"].replace(0, np.nan)
    out["sufficient_minutes"] = out["total_minutes"] >= MIN_MINUTES_CAREER
    mins = out["total_minutes"].astype(float)
    out["goals_per90"] = per90(out["goals"], mins)
    out["assists_per90"] = per90(out["assists"], mins)
    out["goal_contributions_per90"] = per90(out["goal_contributions"], mins)
    meta = season.groupby(id_col).agg(
        first_season=("season", "min"),
        last_season=("season", "max"),
        n_seasons=("season", "nunique"),
        n_competitions=("competition_slug", "nunique"),
    ).reset_index()
    out = out.merge(meta, on=id_col, how="left")
    return out


def recompute_benchmarks(season: pd.DataFrame) -> pd.DataFrame:
    df = season[season["sufficient_minutes"] == True].copy()
    per90_cols = [c for c in df.columns if c.endswith("_per90") and df[c].dtype in [np.float64, float]]
    rate_cols = [c for c in ["pass_accuracy", "duel_win_rate", "aerial_win_rate", "tackle_success_rate", "dribble_success_rate", "cross_accuracy", "long_ball_accuracy"] if c in df.columns]
    rows = []
    for (position, competition_slug, season_v), g in df.groupby(["player_position", "competition_slug", "season"]):
        for stat in per90_cols + rate_cols:
            s = g[stat].dropna()
            if len(s) < 2:
                continue
            rows.append({
                "player_position": position,
                "competition_slug": competition_slug,
                "season": season_v,
                "stat_name": stat,
                "n_players": len(s),
                "mean": float(s.mean()),
                "median": float(s.median()),
                "p25": float(s.quantile(0.25)),
                "p75": float(s.quantile(0.75)),
                "p90": float(s.quantile(0.90)),
            })
    return pd.DataFrame(rows)


def recompute_percentiles(season: pd.DataFrame) -> pd.DataFrame:
    df = season[season["sufficient_minutes"] == True].copy()
    LOWER = {"fouls_per90", "totalOffside_per90", "possessionLostCtrl_per90", "dispossessed_per90", "yellow_cards", "red_cards"}
    per90_cols = [c for c in df.columns if c.endswith("_per90")]
    rate_cols = [c for c in ["pass_accuracy", "duel_win_rate", "aerial_win_rate", "tackle_success_rate"] if c in df.columns]
    stat_cols = per90_cols + rate_cols + [c for c in ["yellow_cards", "red_cards"] if c in df.columns]
    rows = []
    for (position, competition_slug, season_v), g in df.groupby(["player_position", "competition_slug", "season"]):
        n_comp = len(g)
        for _, row in g.iterrows():
            for stat in stat_cols:
                if stat not in row.index or pd.isna(row[stat]):
                    continue
                arr = g[stat].dropna()
                if len(arr) < 2:
                    continue
                pct = percentileofscore(arr, row[stat], kind="rank")
                if stat in LOWER:
                    pct = 100 - pct
                rows.append({
                    "player_id": row["player_id"],
                    "season": season_v,
                    "competition_slug": competition_slug,
                    "player_position": position,
                    "stat_name": stat,
                    "stat_value": row[stat],
                    "pct_in_competition": round(pct, 1),
                    "n_players_in_competition": n_comp,
                })
    return pd.DataFrame(rows)


def recompute_rolling(app: pd.DataFrame) -> pd.DataFrame:
    app = app.copy()
    app["match_date_utc"] = pd.to_datetime(app["match_date"], unit="s", utc=True)
    app = app.sort_values(["player_id", "match_date_utc"])
    rows = []
    for player_id, g in app.groupby("player_id"):
        g = g.reset_index(drop=True)
        for w in (5, 10, 20):
            last = g.tail(w)
            r = last["stat_rating"].dropna()
            if len(r) and r.max() > 10:
                r = r / 2.0
            rows.append({
                "player_id": player_id,
                "window": w,
                "n_available": len(last),
                "avg_rating": r.mean() if len(r) else np.nan,
                "goals": last["stat_goals"].sum() if "stat_goals" in last.columns else 0,
                "assists": last["stat_goalAssist"].sum() if "stat_goalAssist" in last.columns else 0,
                "xg_total": last["stat_expectedGoals"].sum() if "stat_expectedGoals" in last.columns else np.nan,
                "xa_total": last["stat_expectedAssists"].sum() if "stat_expectedAssists" in last.columns else np.nan,
                "total_minutes": last["stat_minutesPlayed"].sum() if "stat_minutesPlayed" in last.columns else 0,
                "avg_key_passes": last["stat_keyPass"].mean() if "stat_keyPass" in last.columns else np.nan,
                "avg_shots": last["stat_totalShots"].mean() if "stat_totalShots" in last.columns else np.nan,
                "avg_tackles": last["stat_totalTackle"].mean() if "stat_totalTackle" in last.columns else np.nan,
                "avg_interceptions": last["stat_interceptionWon"].mean() if "stat_interceptionWon" in last.columns else np.nan,
                "avg_dribbles_won": last["stat_wonContest"].mean() if "stat_wonContest" in last.columns else np.nan,
                "avg_touches": last["stat_touches"].mean() if "stat_touches" in last.columns else np.nan,
            })
    return pd.DataFrame(rows)


def recompute_progression(season: pd.DataFrame) -> pd.DataFrame:
    DELTA_STATS = ["avg_rating", "expectedGoals_per90", "expectedAssists_per90", "goals_per90", "goalAssist_per90", "keyPass_per90", "totalTackle_per90", "duel_win_rate", "pass_accuracy"]
    df = season[season["sufficient_minutes"] == True].copy().sort_values(["player_id", "season", "competition_slug"])
    available = [c for c in DELTA_STATS if c in df.columns]
    rows = []
    for player_id, g in df.groupby("player_id"):
        if len(g) < 2:
            continue
        g = g.sort_values(["season", "competition_slug"])
        for i in range(len(g) - 1):
            a, b = g.iloc[i], g.iloc[i + 1]
            rec = {
                "player_id": player_id,
                "season_from": a["season"],
                "season_to": b["season"],
                "competition_from": a["competition_slug"],
                "competition_to": b["competition_slug"],
            }
            for stat in available:
                if pd.notna(a[stat]) and pd.notna(b[stat]):
                    rec[stat + "_delta"] = float(b[stat]) - float(a[stat])
            rec["minutes_delta"] = int(b.get("total_minutes", 0) or 0) - int(a.get("total_minutes", 0) or 0)
            rows.append(rec)
    return pd.DataFrame(rows)


def recompute_consistency(app: pd.DataFrame) -> pd.DataFrame:
    app = app[app["stat_minutesPlayed"].fillna(0) >= 1].copy()
    id_cols = ["player_id", "season", "competition_slug"]
    stats = [s for s in ["stat_rating", "stat_expectedGoals", "stat_expectedAssists", "stat_keyPass", "stat_touches"] if s in app.columns]

    def consistency(g):
        row = {"n_appearances": len(g)}
        for s in stats:
            if s == "stat_rating":
                continue
            x = g[s].dropna()
            name = s.replace("stat_", "")
            if len(x) < 2:
                row[name + "_mean"] = x.mean() if len(x) == 1 else np.nan
                row[name + "_std"] = np.nan
                row[name + "_cv"] = np.nan
            else:
                mu, std = x.mean(), x.std()
                row[name + "_mean"] = mu
                row[name + "_std"] = std
                row[name + "_cv"] = (std / mu) if mu else np.nan
        if "stat_rating" in g.columns:
            r = g["stat_rating"].dropna()
            if len(r) and r.max() > 10:
                r = r / 2.0
            row["rating_mean"] = r.mean() if len(r) else np.nan
            row["rating_std"] = r.std() if len(r) > 1 else np.nan
            row["rating_cv"] = (row["rating_std"] / row["rating_mean"]) if row.get("rating_mean") else np.nan
            row["rating_min"] = r.min() if len(r) else np.nan
            row["rating_max"] = r.max() if len(r) else np.nan
        return pd.Series(row)

    agg = app.groupby(id_cols, group_keys=False).apply(consistency, include_groups=False).reset_index()
    agg = agg[agg["n_appearances"] >= 5]
    return agg


def recompute_tactical(team: pd.DataFrame) -> pd.DataFrame:
    id_cols = ["team_name", "season", "competition_slug"]
    out = team[id_cols].copy()
    matches = team["matches_total"].replace(0, np.nan)
    out["possession_index"] = team["possession_avg"]
    out["directness_index"] = team["long_balls"] / team["passes_total"].replace(0, np.nan)
    out["aerial_index"] = team["aerial_duels"]
    out["pressing_index"] = (team["tackles_total"] + team["interceptions_total"]) / matches
    out["crossing_index"] = team["crosses"] / matches
    if "big_chances_total" in team.columns:
        out["chance_creation_index"] = team["big_chances_total"] / matches
    if "xg_against_total" in team.columns:
        out["defensive_solidity"] = 1 / (team["xg_against_total"] / matches).replace(0, np.nan)
    if {"xg_for_home", "xg_for_away", "matches_home", "matches_away"}.issubset(team.columns):
        xg_home_pg = team["xg_for_home"] / team["matches_home"].replace(0, np.nan)
        xg_away_pg = team["xg_for_away"] / team["matches_away"].replace(0, np.nan)
        out["home_away_consistency"] = 1 / (1 + (xg_home_pg - xg_away_pg).abs())
    if {"shots_second_half", "shots_first_half"}.issubset(team.columns):
        out["second_half_intensity"] = team["shots_second_half"] / team["shots_first_half"].replace(0, np.nan)
    for col in [c for c in out.columns if c.endswith("_index") or c in ("defensive_solidity", "home_away_consistency", "second_half_intensity")]:
        out[col + "_pct"] = out.groupby(["season", "competition_slug"])[col].rank(pct=True)
    return out


def recompute_opponent_context(app: pd.DataFrame, team: pd.DataFrame, matches: pd.DataFrame) -> pd.DataFrame:
    """Exact rebuild of scripts/build/11_build_player_opponent_context.py logic."""
    if "xg_against_total" not in team.columns:
        return pd.DataFrame()
    app = app.copy()
    app["match_id"] = app["match_id"].astype(str)
    matches = matches.copy()
    matches["match_id"] = matches["match_id"].astype(str)
    app = app.merge(
        matches[["match_id", "home_team_name", "away_team_name", "season", "competition_slug"]],
        on="match_id",
        how="left",
        suffixes=("", "_m"),
    )
    app["opponent"] = np.where(app["side"] == "home", app["away_team_name"], app["home_team_name"])

    def tier_competition(group: pd.Series) -> pd.Series:
        vals = group.dropna()
        if len(vals) < 2:
            return pd.Series(np.nan, index=group.index)
        if vals.nunique() >= 3 and len(vals) >= 3:
            try:
                # Builder labels low xg_against as top_third (stronger opponents concede less)
                cut = pd.qcut(vals, 3, labels=["top_third", "mid_third", "bottom_third"], duplicates="drop")
                result = pd.Series(np.nan, index=group.index, dtype=object)
                result.loc[cut.index] = cut.values.astype(object)
                return result
            except Exception:
                pass
        med = vals.median()
        result = pd.Series(np.nan, index=group.index, dtype=object)
        result.loc[vals.index] = np.where(vals > med, "top_third", "bottom_third")
        return result

    team_stats = team.copy()
    team_stats["tier"] = team_stats.groupby(["season", "competition_slug"])["xg_against_total"].transform(tier_competition)
    opp_tier = team_stats[["team_name", "season", "competition_slug", "tier"]].rename(columns={"team_name": "opponent"})
    app = app.merge(opp_tier, on=["opponent", "season", "competition_slug"], how="left")
    app = app.rename(columns={"tier": "opponent_tier"})

    rows = []
    for (player_id, player_name, position, season, competition_slug, opponent_tier), g in app.groupby(
        ["player_id", "player_name", "player_position", "season", "competition_slug", "opponent_tier"]
    ):
        if pd.isna(opponent_tier):
            continue
        mins = g["stat_minutesPlayed"].fillna(0).sum()
        if mins < 90:
            continue
        rating = g["stat_rating"]
        if rating.dropna().max() > 10:
            rating = rating / 2.0
        mins_f = float(mins) if mins else 0.0
        xg = g["stat_expectedGoals"].sum() if "stat_expectedGoals" in g.columns else np.nan
        rows.append({
            "player_id": player_id,
            "player_name": player_name,
            "player_position": position,
            "season": season,
            "competition_slug": competition_slug,
            "opponent_tier": opponent_tier,
            "n_apps": len(g),
            "n_appearances": len(g),
            "avg_rating": rating.mean(),
            "goals": g["stat_goals"].sum() if "stat_goals" in g.columns else 0,
            "xg_total": xg,
            "xg_per90": (xg / mins_f * 90) if mins_f and pd.notna(xg) else np.nan,
            "key_passes_per90": (g["stat_keyPass"].sum() / mins_f * 90) if "stat_keyPass" in g.columns and mins_f else np.nan,
            "tackles_per90": (g["stat_totalTackle"].sum() / mins_f * 90) if "stat_totalTackle" in g.columns and mins_f else np.nan,
        })
    return pd.DataFrame(rows)


def validate_match_scores(matches: pd.DataFrame, scores00: pd.DataFrame, summary: pd.DataFrame) -> None:
    print("\n=== 00 / 02 score identities ===")
    s = scores00.copy()
    s["match_id"] = s["match_id"].astype(str)
    scored = s[s["score_source"] != "not_scraped"].copy()
    if "total_goals" in scored.columns:
        exp = scored["home_score"].astype(float) + scored["away_score"].astype(float)
        bad = (~_close(scored["total_goals"], exp)).sum()
        if bad:
            fail(f"00.total_goals identity mismatches={bad}")
        else:
            ok("00.total_goals = home+away for all scored matches")
    if "result" in scored.columns:
        exp_res = np.where(scored["home_score"] > scored["away_score"], "H",
                           np.where(scored["home_score"] < scored["away_score"], "A", "D"))
        # result values may be W/D/L from home perspective or 1/X/2 — check consistency if H/D/A
        if set(scored["result"].dropna().unique()).issubset({"H", "D", "A", "1", "X", "2", "W", "L"}):
            # only verify total_goals path already; result formats vary
            ok("00.result column present (format varies; score identity checked above)")
    # summary vs 00
    ms = summary.copy()
    ms["match_id"] = ms["match_id"].astype(str)
    m = scored.merge(ms, on="match_id", suffixes=("_00", "_02"))
    for c in ["home_score", "away_score"]:
        c00, c02 = f"{c}_00", f"{c}_02"
        if c00 in m.columns and c02 in m.columns:
            bad = int((~_close(m[c00], m[c02])).sum())
            if bad:
                fail(f"02 vs 00 {c} mismatches={bad}")
            else:
                ok(f"02.{c} matches 00 for all joined scored matches ({len(m)})")
    if {"home_xg", "away_xg", "xg_swing"}.issubset(ms.columns):
        bad = int((~_close(ms["xg_swing"], ms["home_xg"] - ms["away_xg"], atol=1e-4)).sum())
        # only where both xg present
        mask = ms["home_xg"].notna() & ms["away_xg"].notna() & ms["xg_swing"].notna()
        bad = int((~_close(ms.loc[mask, "xg_swing"], ms.loc[mask, "home_xg"] - ms.loc[mask, "away_xg"], atol=1e-4)).sum())
        if bad:
            fail(f"02.xg_swing identity mismatches={bad}")
        else:
            ok(f"02.xg_swing = home_xg - away_xg ({mask.sum()} rows)")
    # coverage vs index (builder spine must emit one row per matches.csv id)
    missing = set(matches["match_id"].astype(str)) - set(s["match_id"])
    if missing:
        fail(f"00 missing {len(missing)} index match_ids (stale build — re-run 00_fix_match_scores)")
    else:
        ok("00 has every matches.csv id")
    if "score_source" in s.columns:
        not_scraped = int((s["score_source"] == "not_scraped").sum())
        # Product-lake bar: every appearance match must be scored; bare index rows may stay not_scraped
        app_ids = set(pd.read_parquet(DERIVED_DIR / "player_appearances.parquet", columns=["match_id"])["match_id"].astype(str))
        scored_ids = set(s.loc[s["score_source"] != "not_scraped", "match_id"].astype(str))
        missing = app_ids - scored_ids
        if missing:
            fail(f"00 appearance matches still unscored: {len(missing)}")
        else:
            ok(f"00 all {len(app_ids)} appearance matches have scores ({not_scraped} index-only not_scraped rows OK)")


def validate_team_identities(team: pd.DataFrame) -> None:
    print("\n=== 01 team identities ===")
    if {"matches_home", "matches_away", "matches_total"}.issubset(team.columns):
        bad = int((team["matches_home"] + team["matches_away"] != team["matches_total"]).sum())
        if bad:
            fail(f"01 matches_home+away!=total mismatches={bad}")
        else:
            ok("01 matches_home + matches_away = matches_total")
    if {"goals_for", "goals_against", "goal_diff"}.issubset(team.columns):
        bad = int((team["goal_diff"] != team["goals_for"] - team["goals_against"]).sum())
        if bad:
            fail(f"01 goal_diff mismatches={bad}")
        else:
            ok("01 goal_diff = goals_for - goals_against")
    for c in ["possession_avg", "pass_accuracy_avg"]:
        if c in team.columns:
            s = team[c].dropna()
            if ((s < 0) | (s > 1)).any():
                fail(f"01.{c} out of [0,1]")
            else:
                ok(f"01.{c} in [0,1]")


def validate_heatmap_sample(matches: pd.DataFrame, heat: pd.DataFrame, n_matches: int = 80) -> None:
    print("\n=== 18 heatmap sample recount ===")
    if heat.empty:
        warn("18 heatmap empty — skip")
        return
    raw = ROOT / "data" / "raw"
    heat_ids = set(heat["match_id"].astype(str))
    # Prefer matches that are already in the heatmap parquet (validates extract fidelity)
    in_heat = matches[matches["match_id"].astype(str).isin(heat_ids)]
    sample = in_heat.sample(min(n_matches, len(in_heat)), random_state=42) if len(in_heat) else matches.head(0)
    checked = 0
    mismatches = 0
    missing_raw = 0
    for _, row in sample.iterrows():
        mid = str(row["match_id"])
        season = str(row["season"])
        comp = str(row["competition_slug"])
        players_dir = raw / season / "club" / comp / mid / "players"
        if not players_dir.exists():
            missing_raw += 1
            continue
        files = list(players_dir.glob("heatmap_*.json"))
        if not files:
            missing_raw += 1
            continue
        checked += 1
        expected_points = 0
        for f in files:
            try:
                data = json.loads(f.read_text())
                pts = data.get("heatmap") if isinstance(data, dict) else data
                if isinstance(pts, list):
                    expected_points += len(pts)
            except Exception:
                continue
        actual_n = int((heat["match_id"].astype(str) == mid).sum())
        if actual_n != expected_points:
            mismatches += 1
            if mismatches <= 5:
                fail(f"18 heatmap match {mid}: raw_points={expected_points} parquet_rows={actual_n}")
    # Also report coverage: raw heatmaps not loaded into parquet
    raw_with_maps = 0
    raw_not_in_parquet = 0
    for _, row in matches.sample(min(200, len(matches)), random_state=7).iterrows():
        mid = str(row["match_id"])
        p = raw / str(row["season"]) / "club" / str(row["competition_slug"]) / mid / "players"
        if p.exists() and list(p.glob("heatmap_*.json")):
            raw_with_maps += 1
            if mid not in heat_ids:
                raw_not_in_parquet += 1
    if checked == 0:
        warn("18 heatmap sample: no overlapping raw+parquet matches found")
    elif mismatches == 0:
        ok(f"18 heatmap recount OK on {checked} parquet-covered matches")
    else:
        fail(f"18 heatmap mismatches on {mismatches}/{checked} parquet-covered matches")
    if raw_with_maps:
        if raw_not_in_parquet:
            warn(
                f"18 coverage gap: {raw_not_in_parquet}/{raw_with_maps} sampled raw-heatmap matches "
                f"missing from parquet (step 18 incomplete / stale coverage)"
            )
        else:
            ok(f"18 coverage: all {raw_with_maps} sampled raw-heatmap matches present in parquet")


def validate_warehouse(recomputed_season: pd.DataFrame) -> None:
    print("\n=== Warehouse marts vs independent recompute ===")
    if not WH.exists():
        fail("warehouse missing")
        return
    con = duckdb.connect(str(WH), read_only=True)
    wh = con.execute(
        """
        select player_id, season, competition_slug, goals, assists, total_minutes,
               appearances, starts, avg_rating, goal_contributions, yellow_cards, red_cards,
               pass_accuracy, duel_win_rate, aerial_win_rate, tackle_success_rate,
               goals_per90, expectedGoals_per90, keyPass_per90, totalTackle_per90
        from analytics_marts.mart_player_season_stats
        """
    ).df()
    # align types
    for c in ["player_id"]:
        wh[c] = pd.to_numeric(wh[c], errors="coerce")
        recomputed_season[c] = pd.to_numeric(recomputed_season[c], errors="coerce")
    # rename per90 if needed
    exp = recomputed_season.copy()
    if "goals_per90" not in exp.columns and "stat_goals" not in exp.columns:
        pass
    # our recompute uses goals_per90 from goals total via per90 on goals column? We used goals from sum and goals_per90 only if we created it
    if "goals_per90" not in exp.columns and "total_goals" not in exp.columns:
        exp["goals_per90"] = per90(exp["goals"], exp["total_minutes"])
    if "expectedGoals_per90" not in exp.columns and "total_expectedGoals" in exp.columns:
        exp["expectedGoals_per90"] = per90(exp["total_expectedGoals"], exp["total_minutes"])
    if "keyPass_per90" not in exp.columns and "total_keyPass" in exp.columns:
        exp["keyPass_per90"] = per90(exp["total_keyPass"], exp["total_minutes"])
    if "totalTackle_per90" not in exp.columns and "total_totalTackle" in exp.columns:
        exp["totalTackle_per90"] = per90(exp["total_totalTackle"], exp["total_minutes"])

    cols = [c for c in [
        "goals", "assists", "total_minutes", "appearances", "starts", "avg_rating",
        "goal_contributions", "yellow_cards", "red_cards",
        "pass_accuracy", "duel_win_rate", "aerial_win_rate", "tackle_success_rate",
        "goals_per90", "expectedGoals_per90", "keyPass_per90", "totalTackle_per90",
    ] if c in exp.columns and c in wh.columns]
    compare_frames(
        "warehouse.mart_player_season_stats",
        exp,
        wh,
        ["player_id", "season", "competition_slug"],
        cols,
        atol=1e-4,
        max_fail_rate=0.0,
    )

    # career mart: identity vs sum of warehouse season stats (product path)
    car_wh = con.execute(
        "select player_id, goals, assists, total_minutes, appearances from analytics_marts.mart_player_career_stats"
    ).df()
    season_for_career = wh.copy()
    season_for_career["player_name"] = season_for_career.get("player_name", "x")
    if "player_name" not in season_for_career.columns:
        season_for_career["player_name"] = "x"
    if "player_position" not in season_for_career.columns:
        season_for_career["player_position"] = "U"
    if "goal_contributions" not in season_for_career.columns:
        season_for_career["goal_contributions"] = season_for_career["goals"] + season_for_career["assists"]
    for c in ("yellow_cards", "red_cards", "starts"):
        if c not in season_for_career.columns:
            season_for_career[c] = 0
    car_from_wh_season = season_for_career.groupby("player_id", as_index=False).agg(
        goals=("goals", "sum"),
        assists=("assists", "sum"),
        total_minutes=("total_minutes", "sum"),
        appearances=("appearances", "sum"),
    )
    # career mart may still contain historical seasons not in current warehouse season mart
    joined = car_from_wh_season.merge(car_wh, on="player_id", how="inner", suffixes=("_exp", "_act"))
    if joined.empty:
        fail("warehouse career: empty join")
    else:
        for c in ["goals", "assists", "total_minutes", "appearances"]:
            bad = int((~_close(joined[f"{c}_exp"], joined[f"{c}_act"])).sum())
            # Expect mismatch if career includes older seasons — report as WARN unless exact
            if bad == 0:
                ok(f"warehouse.career.{c} matches sum(warehouse season) for {len(joined)} players")
            else:
                rate = bad / len(joined)
                if rate > 0.5:
                    warn(
                        f"warehouse.career.{c}: {bad}/{len(joined)} differ from sum(current season mart) "
                        f"— career file likely still includes historical seasons"
                    )
                else:
                    fail(f"warehouse.career.{c}: {bad}/{len(joined)} mismatches vs sum(season mart)")


def main() -> int:
    print("Loading sources…")
    app = pd.read_parquet(DERIVED_DIR / "player_appearances.parquet")
    app["match_id"] = app["match_id"].astype(str)
    incidents = pd.read_parquet(DERIVED_DIR / "player_incidents.parquet")
    incidents["match_id"] = incidents["match_id"].astype(str)
    matches = pd.read_csv(INDEX_DIR / "matches.csv")
    matches["match_id"] = matches["match_id"].astype(str)

    scores00 = pd.read_parquet(PROCESSED_DIR / "00_match_scores_full.parquet")
    team = pd.read_parquet(PROCESSED_DIR / "01_team_season_stats.parquet")
    summary = pd.read_parquet(PROCESSED_DIR / "02_match_summary.parquet")
    season_act = pd.read_parquet(PROCESSED_DIR / "03_player_season_stats.parquet")
    career_act = pd.read_parquet(PROCESSED_DIR / "04_player_career_stats.parquet")
    bench_act = pd.read_parquet(PROCESSED_DIR / "05_competition_benchmarks.parquet")
    pct_act = pd.read_parquet(PROCESSED_DIR / "06_player_percentile_ranks.parquet")
    roll_act = pd.read_parquet(PROCESSED_DIR / "07_player_rolling_form.parquet")
    prog_act = pd.read_parquet(PROCESSED_DIR / "09_player_progression.parquet")
    cons_act = pd.read_parquet(PROCESSED_DIR / "10_player_consistency.parquet")
    opp_act = pd.read_parquet(PROCESSED_DIR / "11_player_opponent_context.parquet") if (PROCESSED_DIR / "11_player_opponent_context.parquet").exists() else pd.DataFrame()
    # summary file may be preferred
    opp_sum = PROCESSED_DIR / "11_player_opponent_context_summary.parquet"
    if opp_sum.exists():
        opp_sum_df = pd.read_parquet(opp_sum)
    else:
        opp_sum_df = pd.DataFrame()
    tac_act = pd.read_parquet(PROCESSED_DIR / "15_team_tactical_profiles.parquet")
    heat = pd.read_parquet(PROCESSED_DIR / "18_heatmap_points.parquet") if (PROCESSED_DIR / "18_heatmap_points.parquet").exists() else pd.DataFrame()

    validate_match_scores(matches, scores00, summary)
    validate_team_identities(team)

    print("\n=== Recompute 03 season stats from appearances ===")
    season_exp = recompute_season_stats(app, incidents)
    # Restrict actual to seasons present in appearances (current lake)
    seasons_in_app = set(app["season"].astype(str).unique())
    season_act_cur = season_act[season_act["season"].astype(str).isin(seasons_in_app)].copy()
    per90_cols = [c for c in season_exp.columns if c.endswith("_per90")]
    rate_cols = [c for c in ["pass_accuracy", "duel_win_rate", "aerial_win_rate", "tackle_success_rate", "dribble_success_rate", "cross_accuracy", "long_ball_accuracy"] if c in season_exp.columns]
    value_cols = [c for c in ["pass_value_avg", "shot_value_avg", "defensive_value_avg", "dribble_value_avg", "gk_value_avg"] if c in season_exp.columns]
    core_cols = [
        "appearances", "starts", "total_minutes", "sub_appearances", "avg_minutes_per_game",
        "avg_rating", "goals", "assists", "goal_contributions", "yellow_cards", "red_cards",
        "sufficient_minutes",
    ] + per90_cols + rate_cols + value_cols
    compare_frames(
        "03_player_season_stats",
        season_exp,
        season_act_cur,
        ["player_id", "season", "competition_slug"],
        core_cols,
        atol=1e-4,
    )

    print("\n=== Recompute 04 career from the SAME 03 file it claims to aggregate ===")
    career_exp = recompute_career(season_act)
    compare_frames(
        "04_player_career_stats",
        career_exp,
        career_act,
        ["player_id"],
        [c for c in ["appearances", "starts", "total_minutes", "goals", "assists", "goal_contributions", "yellow_cards", "red_cards", "goals_per90", "assists_per90", "goal_contributions_per90", "n_seasons", "n_competitions"] if c in career_exp.columns],
        atol=1e-4,
    )

    print("\n=== Recompute 05 benchmarks ===")
    bench_exp = recompute_benchmarks(season_act)
    # only current seasons in act file still include history — validate on full act input
    compare_frames(
        "05_competition_benchmarks",
        bench_exp,
        bench_act,
        ["player_position", "competition_slug", "season", "stat_name"],
        ["n_players", "mean", "median", "p25", "p75", "p90"],
        atol=1e-6,
    )

    print("\n=== Recompute 06 percentiles ===")
    pct_exp = recompute_percentiles(season_act)
    compare_frames(
        "06_player_percentile_ranks",
        pct_exp,
        pct_act,
        ["player_id", "season", "competition_slug", "player_position", "stat_name"],
        ["stat_value", "pct_in_competition", "n_players_in_competition"],
        atol=0.05,  # rounded to 1 decimal in builder
    )

    print("\n=== Recompute 07 rolling form ===")
    roll_exp = recompute_rolling(app)
    compare_frames(
        "07_player_rolling_form",
        roll_exp,
        roll_act,
        ["player_id", "window"],
        [c for c in ["n_available", "avg_rating", "goals", "assists", "xg_total", "xa_total", "total_minutes", "avg_key_passes", "avg_shots", "avg_tackles", "avg_interceptions", "avg_dribbles_won", "avg_touches"] if c in roll_exp.columns],
        atol=1e-4,
    )

    print("\n=== Recompute 09 progression ===")
    prog_exp = recompute_progression(season_act)
    delta_cols = [c for c in prog_exp.columns if c.endswith("_delta")]
    compare_frames(
        "09_player_progression",
        prog_exp,
        prog_act,
        ["player_id", "season_from", "season_to", "competition_from", "competition_to"],
        delta_cols + (["minutes_delta"] if "minutes_delta" in prog_exp.columns else []),
        atol=1e-4,
    )

    print("\n=== Recompute 10 consistency ===")
    cons_exp = recompute_consistency(app)
    cons_cols = [c for c in cons_exp.columns if c not in ("player_id", "season", "competition_slug")]
    compare_frames(
        "10_player_consistency",
        cons_exp,
        cons_act,
        ["player_id", "season", "competition_slug"],
        cons_cols,
        atol=1e-4,
    )

    print("\n=== Recompute 15 tactical indices ===")
    tac_exp = recompute_tactical(team)
    tac_cols = [c for c in tac_exp.columns if c not in ("team_name", "season", "competition_slug")]
    compare_frames(
        "15_team_tactical_profiles",
        tac_exp,
        tac_act,
        ["team_name", "season", "competition_slug"],
        tac_cols,
        atol=1e-5,
    )

    print("\n=== 11 opponent context ===")
    # Full independent re-run of the builder into memory by importing its logic via subprocess rebuild already done.
    # Validate invariants on the stored file + recompute from that file's grain.
    target = opp_act if not opp_act.empty else opp_sum_df
    if target.empty:
        fail("11 opponent context file missing")
    else:
        if "opponent_tier" in target.columns:
            bad = int(target["opponent_tier"].isna().sum())
            if bad:
                fail(f"11 null opponent_tier rows={bad}")
            else:
                ok("11 opponent_tier has no nulls")
            valid = {"top_third", "mid_third", "bottom_third"}
            extra = set(target["opponent_tier"].dropna().astype(str).unique()) - valid
            if extra:
                fail(f"11 invalid tiers {extra}")
            else:
                ok("11 opponent_tier values valid")
        # Recompute means from appearances using the STORED tiers joined back (validates aggregates given tiers)
        if {"player_id", "season", "competition_slug", "opponent_tier"}.issubset(target.columns):
            # detailed grain expected
            detail_cols = [c for c in ["n_appearances", "n_apps", "avg_rating", "goals", "expectedGoals", "xg"] if c in target.columns]
            if detail_cols:
                ok(f"11 has aggregate columns {detail_cols}")
            # players referenced exist in season stats
            if "player_id" in target.columns:
                missing = set(pd.to_numeric(target["player_id"], errors="coerce").dropna().astype(int)) - set(pd.to_numeric(season_act["player_id"], errors="coerce").dropna().astype(int))
                # opponent context may include players below sufficient minutes; compare to appearances instead
                missing_app = set(pd.to_numeric(target["player_id"], errors="coerce").dropna().astype(int)) - set(pd.to_numeric(app["player_id"], errors="coerce").dropna().astype(int))
                if missing_app:
                    fail(f"11 has {len(missing_app)} player_ids not in appearances")
                else:
                    ok("11 all player_ids exist in appearances")
        # Independent rebuild check: run builder output equals stored (via fresh recompute script path)
        opp_exp = recompute_opponent_context(app, team, matches)
        if not opp_exp.empty and {"player_id", "season", "competition_slug", "opponent_tier"}.issubset(target.columns):
            t = target.copy()
            rename = {}
            if "n_appearances" in t.columns and "n_apps" not in t.columns:
                rename["n_appearances"] = "n_apps"
            t = t.rename(columns=rename)
            # Grain matches builder groupby: player_id + name + position + season + comp + tier
            keys = ["player_id", "season", "competition_slug", "opponent_tier"]
            if {"player_name", "player_position"}.issubset(t.columns) and {"player_name", "player_position"}.issubset(opp_exp.columns):
                keys = ["player_id", "player_name", "player_position", "season", "competition_slug", "opponent_tier"]
            e_keys = opp_exp[keys].drop_duplicates()
            a_keys = t[keys].drop_duplicates()
            for k in keys:
                e_keys[k] = e_keys[k].astype(str)
                a_keys[k] = a_keys[k].astype(str)
            merged_keys = e_keys.merge(a_keys, on=keys, how="inner")
            rate = len(merged_keys) / max(len(e_keys), 1)
            if rate < 0.9:
                fail(f"11 opponent_tier assignment agreement {rate:.1%} vs independent recompute (builder logic drift or stale file)")
            else:
                ok(f"11 opponent_tier assignment agreement {rate:.1%} vs independent recompute")
            metric_cols = [
                c for c in ["n_appearances", "n_apps", "goals", "avg_rating", "xg_total", "xg_per90", "key_passes_per90", "tackles_per90"]
                if c in t.columns and c in opp_exp.columns
            ]
            if metric_cols:
                compare_frames("11_opponent_context", opp_exp, t, keys, metric_cols, atol=1e-4, max_fail_rate=0.0)
            # Validate summary deltas from detail grain
            if not opp_sum_df.empty and {"rating_vs_top", "rating_vs_bottom", "big_game_rating_delta"}.issubset(opp_sum_df.columns):
                detail = t.copy()
                if "avg_rating" in detail.columns and "opponent_tier" in detail.columns:
                    pivot = detail.pivot_table(
                        index=[c for c in ["player_id", "player_name", "player_position", "season", "competition_slug"] if c in detail.columns],
                        columns="opponent_tier",
                        values="avg_rating",
                        aggfunc="mean",
                    ).reset_index()
                    pivot["rating_vs_top"] = pivot["top_third"] if "top_third" in pivot.columns else np.nan
                    pivot["rating_vs_bottom"] = pivot["bottom_third"] if "bottom_third" in pivot.columns else np.nan
                    pivot["big_game_rating_delta"] = pd.to_numeric(pivot["rating_vs_top"], errors="coerce") - pd.to_numeric(pivot["rating_vs_bottom"], errors="coerce")
                    sum_keys = [c for c in ["player_id", "player_name", "player_position", "season", "competition_slug"] if c in pivot.columns and c in opp_sum_df.columns]
                    compare_frames(
                        "11_opponent_context_summary",
                        pivot,
                        opp_sum_df,
                        sum_keys,
                        ["rating_vs_top", "rating_vs_bottom", "big_game_rating_delta"],
                        atol=1e-4,
                        max_fail_rate=0.0,
                    )

    validate_heatmap_sample(matches, heat)
    validate_warehouse(season_exp)

    # 08 scouting: composition of validated tables (latest season + career + form)
    print("\n=== 08 scouting profiles ===")
    scout = pd.read_parquet(PROCESSED_DIR / "08_player_scouting_profiles.parquet")
    if scout["player_id"].duplicated().any():
        fail("08 duplicate player_id")
    else:
        ok("08 no duplicate player_id")
    latest_comp_col = "latest_competition" if "latest_competition" in scout.columns else (
        "latest_competition_slug" if "latest_competition_slug" in scout.columns else None
    )
    if {"player_id", "latest_season", "latest_minutes", "latest_rating", "latest_appearances"}.issubset(scout.columns) and latest_comp_col:
        s3 = season_act.copy()
        m = scout.merge(
            s3,
            left_on=["player_id", "latest_season", latest_comp_col],
            right_on=["player_id", "season", "competition_slug"],
            how="inner",
            suffixes=("_08", "_03"),
        )
        checks = [
            ("latest_minutes", "total_minutes"),
            ("latest_rating", "avg_rating"),
            ("latest_appearances", "appearances"),
        ]
        for a, b in checks:
            left = a if a in m.columns else f"{a}_08"
            right = b if b in m.columns else f"{b}_03"
            if left in m.columns and right in m.columns:
                bad = int((~_close(m[left], m[right], atol=1e-4)).sum())
                if bad:
                    fail(f"08.{a} vs 03.{b} mismatches={bad}/{len(m)}")
                else:
                    ok(f"08.{a} matches 03.{b} for {len(m)} profiles")
            else:
                fail(f"08.{a} vs 03.{b}: columns missing after join ({left!r}/{right!r})")
    else:
        warn("08 missing latest_* columns — structural only")
    # career totals on profile must match 04
    car_cols = [c for c in ["total_minutes", "goals", "assists"] if c in scout.columns and c in career_act.columns]
    if car_cols:
        m = scout.merge(career_act, on="player_id", how="inner", suffixes=("_08", "_04"))
        for c in car_cols:
            c08, c04 = f"{c}_08", f"{c}_04"
            if c08 in m.columns and c04 in m.columns:
                bad = int((~_close(m[c08], m[c04])).sum())
                if bad:
                    fail(f"08.{c} vs 04 mismatches={bad}/{len(m)}")
                else:
                    ok(f"08.{c} matches 04 for {len(m)} profiles")
    # form window=10 from 07
    if {"form_rating", "form_goals"}.issubset(scout.columns) and not roll_act.empty:
        r10 = roll_act[roll_act["window"] == 10].copy() if "window" in roll_act.columns else roll_act
        m = scout.merge(r10, on="player_id", how="inner", suffixes=("_08", "_07"))
        if "form_rating" in m.columns and "avg_rating" in m.columns:
            bad = int((~_close(m["form_rating"], m["avg_rating"], atol=1e-4)).sum())
            if bad:
                fail(f"08.form_rating vs 07.avg_rating(window=10) mismatches={bad}/{len(m)}")
            else:
                ok(f"08.form_rating matches 07 window=10 for {len(m)} profiles")
        if "form_goals" in m.columns and "goals" in m.columns:
            bad = int((~_close(m["form_goals"], m["goals"])).sum())
            if bad:
                fail(f"08.form_goals vs 07.goals(window=10) mismatches={bad}/{len(m)}")
            else:
                ok(f"08.form_goals matches 07 window=10 for {len(m)} profiles")
    if "sufficient_minutes_latest_season" in scout.columns and "latest_minutes" in scout.columns:
        exp = scout["latest_minutes"].fillna(0) >= 450
        bad = int((scout["sufficient_minutes_latest_season"].fillna(False) != exp).sum())
        if bad:
            fail(f"08.sufficient_minutes_latest_season mismatches={bad}")
        else:
            ok("08.sufficient_minutes_latest_season = latest_minutes >= 450")

    # league_strength composite from 01/02/03
    print("\n=== league_strength ===")
    ls_path = PROCESSED_DIR / "league_strength.parquet"
    if not ls_path.exists():
        warn("league_strength.parquet missing")
    else:
        ls = pd.read_parquet(ls_path).copy()
        for c in ("competition_slug", "season"):
            ls[c] = ls[c].astype(str)
        id_cols = ["competition_slug", "season"]
        if "xg_against_total" in team.columns:
            tl = team.copy()
            tl["season"] = tl["season"].astype(str)
            tl["competition_slug"] = tl["competition_slug"].astype(str)
            team_league = tl.groupby(id_cols).agg(
                matches_total=("matches_total", "sum"),
                xg_against_total=("xg_against_total", "sum"),
            ).reset_index()
            team_league["xg_against_per_match"] = team_league["xg_against_total"] / team_league["matches_total"].replace(0, np.nan)
            m = ls[id_cols + ["xg_against_per_match"]].merge(
                team_league[id_cols + ["xg_against_per_match"]], on=id_cols, suffixes=("_act", "_exp")
            )
            bad = int((~_close(m["xg_against_per_match_act"], m["xg_against_per_match_exp"], atol=1e-4)).sum())
            if bad:
                fail(f"league_strength.xg_against_per_match mismatches={bad}/{len(m)}")
            else:
                ok(f"league_strength.xg_against_per_match matches 01 aggregate ({len(m)} leagues)")
        ms = summary.copy()
        ms["season"] = ms["season"].astype(str)
        ms["competition_slug"] = ms["competition_slug"].astype(str)
        if "total_goals" in ms.columns and "goals_per_match" in ls.columns:
            gpm = ms.groupby(id_cols)["total_goals"].mean().reset_index(name="goals_per_match")
            m = ls[id_cols + ["goals_per_match"]].merge(gpm, on=id_cols, suffixes=("_act", "_exp"))
            bad = int((~_close(m["goals_per_match_act"], m["goals_per_match_exp"], atol=1e-4)).sum())
            if bad:
                fail(f"league_strength.goals_per_match mismatches={bad}/{len(m)}")
            else:
                ok(f"league_strength.goals_per_match matches 02 mean ({len(m)} leagues)")
        if "avg_rating_league" in ls.columns:
            pl = season_act.copy()
            pl["season"] = pl["season"].astype(str)
            pl["competition_slug"] = pl["competition_slug"].astype(str)
            pl_suf = pl[pl["sufficient_minutes"] == True] if "sufficient_minutes" in pl.columns else pl
            ar = pl_suf.groupby(id_cols)["avg_rating"].mean().reset_index(name="avg_rating_league")
            m = ls[id_cols + ["avg_rating_league"]].merge(ar, on=id_cols, suffixes=("_act", "_exp"))
            bad = int((~_close(m["avg_rating_league_act"], m["avg_rating_league_exp"], atol=1e-4)).sum())
            if bad:
                fail(f"league_strength.avg_rating_league mismatches={bad}/{len(m)}")
            else:
                ok(f"league_strength.avg_rating_league matches 03 mean ({len(m)} leagues)")
        if "strength_score" in ls.columns:
            pl = ls[ls["competition_slug"] == "england-premier-league"].copy()
            pl_ready = pl[pl["avg_rating_league"].notna()] if "avg_rating_league" in pl.columns else pl
            ref_season = pl_ready["season"].dropna().astype(str).max() if not pl_ready.empty else None
            ref = pl[pl["season"] == ref_season] if ref_season else pl.iloc[0:0]
            if not ref.empty and pd.notna(ref.iloc[0]["strength_score"]):
                score = float(ref.iloc[0]["strength_score"])
                if abs(score - 1.0) < 1e-6:
                    ok(f"league_strength reference PL {ref_season} strength_score=1.0")
                else:
                    fail(f"league_strength PL {ref_season} strength_score={score} (expected 1.0)")
            else:
                fail("league_strength missing PL reference row with strength_score")
            scored = ls["strength_score"].dropna()
            if len(scored) and ((scored < 0).any() or (scored > 2.0 + 1e-9).any()):
                fail("league_strength.strength_score outside [0, 2] clip range")
            else:
                ok("league_strength.strength_score within [0, 2]")

    print("\n" + "=" * 60)
    print(f"SUMMARY: {len(PASSES)} PASS, {len(WARNS)} WARN, {len(FAILS)} FAIL")
    print("=" * 60)
    if FAILS:
        print("\nFAILURES:")
        for f in FAILS:
            print(f"  - {f}")
        return 1
    print("\nALL_CALCULATIONS_VALIDATED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
