"""
Step 0: Build full match scores using matches.csv as the authoritative spine.

Priority order for score resolution:
  1. data/derived/match_scores.parquet  → score_source='original'
  2. player_incidents goal events        → score_source='derived_from_incidents'
  3. match present in player_appearances → score_source='zero_zero_assumed' (0-0)
  4. no data at all                      → score_source='not_scraped', null scores

Output: data/processed/00_match_scores_full.parquet  (one row per match in matches.csv)
"""

import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

from scripts.build.utils import PROCESSED_DIR, DERIVED_DIR, INDEX_DIR


def main():
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)

    # 1) Full match spine from matches.csv — authoritative list of all matches
    matches_path = INDEX_DIR / "matches.csv"
    if not matches_path.exists():
        print("Missing", matches_path, file=sys.stderr)
        sys.exit(1)
    spine = pd.read_csv(matches_path)[["match_id"]]
    spine["match_id"] = spine["match_id"].astype(str)

    # 2) Scores from incidents: max homeScore/awayScore per match from goal events
    incidents_path = DERIVED_DIR / "player_incidents.parquet"
    if not incidents_path.exists():
        print("Missing", incidents_path, file=sys.stderr)
        sys.exit(1)
    inc = pd.read_parquet(incidents_path)
    inc["match_id"] = inc["match_id"].astype(str)
    with_score = inc[inc["homeScore"].notna() & inc["awayScore"].notna()].copy()
    with_score["home_score"] = pd.to_numeric(with_score["homeScore"], errors="coerce").astype("Int64")
    with_score["away_score"] = pd.to_numeric(with_score["awayScore"], errors="coerce").astype("Int64")
    from_incidents = (
        with_score.groupby("match_id")
        .agg(home_score=("home_score", "max"), away_score=("away_score", "max"))
        .reset_index()
    )
    from_incidents["score_source"] = "derived_from_incidents"

    # 3) Existing match_scores.parquet — highest priority (labeled 'original')
    existing_path = DERIVED_DIR / "match_scores.parquet"
    if existing_path.exists():
        existing = pd.read_parquet(existing_path)
        existing["match_id"] = existing["match_id"].astype(str)
        existing = existing[["match_id", "home_score", "away_score"]].copy()
        existing["score_source"] = "original"
        existing["home_score"] = existing["home_score"].astype("Int64")
        existing["away_score"] = existing["away_score"].astype("Int64")
    else:
        existing = pd.DataFrame(columns=["match_id", "home_score", "away_score", "score_source"])

    # 4) Merge onto spine: existing > incidents > fallback
    out = spine.merge(existing, on="match_id", how="left")
    # Fill missing from incidents
    need_fill = out["home_score"].isna()
    inc_fill = from_incidents.rename(columns={"home_score": "h_i", "away_score": "a_i", "score_source": "src_i"})
    out = out.merge(inc_fill, on="match_id", how="left")
    out.loc[need_fill, "home_score"] = out.loc[need_fill, "h_i"].values
    out.loc[need_fill, "away_score"] = out.loc[need_fill, "a_i"].values
    out.loc[need_fill & out["h_i"].notna(), "score_source"] = "derived_from_incidents"
    out = out.drop(columns=["h_i", "a_i", "src_i"], errors="ignore")

    # 5) Patch matches with appearance data but no score as 0-0 (no goals recorded anywhere)
    app_match_ids = pd.read_parquet(DERIVED_DIR / "player_appearances.parquet", columns=["match_id"])
    app_match_ids["match_id"] = app_match_ids["match_id"].astype(str)
    app_ids_set = set(app_match_ids["match_id"].unique())
    mask_no_score = out["home_score"].isna()
    mask_in_app = out["match_id"].isin(app_ids_set)
    out.loc[mask_no_score & mask_in_app, "home_score"] = pd.array([0] * (mask_no_score & mask_in_app).sum(), dtype="Int64")
    out.loc[mask_no_score & mask_in_app, "away_score"] = pd.array([0] * (mask_no_score & mask_in_app).sum(), dtype="Int64")
    out.loc[mask_no_score & mask_in_app, "score_source"] = "zero_zero_assumed"

    # 6) Remaining nulls = truly unscraped matches (no raw data collected)
    out.loc[out["score_source"].isna(), "score_source"] = "not_scraped"

    # 7) Derived columns (only where scores are available)
    has_score = out["home_score"].notna() & out["away_score"].notna()
    out["total_goals"] = pd.NA
    out.loc[has_score, "total_goals"] = (
        out.loc[has_score, "home_score"].astype(int) + out.loc[has_score, "away_score"].astype(int)
    )
    out["total_goals"] = pd.to_numeric(out["total_goals"], errors="coerce").astype("Int64")

    out["result"] = pd.NA
    out.loc[has_score, "result"] = "D"
    out.loc[has_score & (out["home_score"] > out["away_score"]), "result"] = "H"
    out.loc[has_score & (out["home_score"] < out["away_score"]), "result"] = "A"
    # 0-0 derived_from_incidents with no goals: refine source label
    out.loc[(out["score_source"] == "derived_from_incidents") & (out["total_goals"] == 0), "score_source"] = "zero_zero_assumed"

    out_path = PROCESSED_DIR / "00_match_scores_full.parquet"
    out.to_parquet(out_path, index=False)

    src_counts = out["score_source"].value_counts().to_dict()
    print(f"Wrote {out_path} ({len(out)} rows)")
    print(f"  score_source breakdown: {src_counts}")


if __name__ == "__main__":
    main()
