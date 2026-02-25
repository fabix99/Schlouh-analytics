"""
Regenerate data/derived/players/{slug}.csv for each player in data/index/players.csv.

Uses data/derived/player_appearances.parquet and data/derived/player_incidents.parquet
so each file has the correct player_id (from the index) and consistent schema.
Fixes validation failures where player_id in the CSV did not match the index (e.g. name collisions).

Usage:
  python scripts/build_derived_player_csvs.py
  python scripts/build_derived_player_csvs.py --dry-run
"""

import argparse
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
INDEX_DIR = ROOT / "data" / "index"
DERIVED_DIR = ROOT / "data" / "derived"
APPEARANCES_PATH = DERIVED_DIR / "player_appearances.parquet"
INCIDENTS_PATH = DERIVED_DIR / "player_incidents.parquet"
PLAYERS_DIR = DERIVED_DIR / "players"


def main() -> None:
    parser = argparse.ArgumentParser(description="Regenerate per-player CSVs from parquet and index.")
    parser.add_argument("--dry-run", action="store_true", help="Print what would be written, do not write")
    args = parser.parse_args()

    players_path = INDEX_DIR / "players.csv"
    if not players_path.exists():
        print(f"Not found: {players_path}")
        return
    if not APPEARANCES_PATH.exists():
        print(f"Not found: {APPEARANCES_PATH}")
        return

    players = pd.read_csv(players_path)
    players["player_id"] = pd.to_numeric(players["player_id"], errors="coerce")
    players = players.dropna(subset=["player_id", "player_slug"])
    players["player_id"] = players["player_id"].astype(int)

    appearances = pd.read_parquet(APPEARANCES_PATH)
    appearances["player_id"] = pd.to_numeric(appearances["player_id"], errors="coerce").astype("Int64")

    # Optional: incident counts per (player_id, match_id) for incident_* columns
    incident_counts = None
    if INCIDENTS_PATH.exists():
        inc = pd.read_parquet(INCIDENTS_PATH)
        if "player_id" in inc.columns and "match_id" in inc.columns and "incidentType" in inc.columns and "incidentClass" in inc.columns:
            inc["player_id"] = pd.to_numeric(inc["player_id"], errors="coerce")
            inc = inc.dropna(subset=["player_id", "match_id"])
            goals = inc[(inc["incidentType"] == "goal") & (inc["incidentClass"].isin(["regular", "penalty", "ownGoal"]))]
            goals = goals.groupby(["player_id", "match_id"]).size().reset_index(name="incident_goals")
            cards_y = inc[(inc["incidentType"] == "card") & (inc["incidentClass"] == "yellow")]
            cards_y = cards_y.groupby(["player_id", "match_id"]).size().reset_index(name="incident_yellow_cards")
            cards_r = inc[(inc["incidentType"] == "card") & (inc["incidentClass"].isin(["red", "yellowRed"]))]
            cards_r = cards_r.groupby(["player_id", "match_id"]).size().reset_index(name="incident_red_cards")
            penalty_goals = inc[(inc["incidentType"] == "goal") & (inc["incidentClass"] == "penalty")]
            penalty_goals = penalty_goals.groupby(["player_id", "match_id"]).size().reset_index(name="incident_penalty_goals")
            penalty_missed = inc[(inc["incidentType"] == "inGamePenalty") & (inc["incidentClass"] == "missed")]
            penalty_missed = penalty_missed.groupby(["player_id", "match_id"]).size().reset_index(name="incident_penalty_missed")
            incident_counts = goals
            for part in [cards_y, cards_r, penalty_goals, penalty_missed]:
                incident_counts = incident_counts.merge(part, on=["player_id", "match_id"], how="outer")
            incident_counts = incident_counts.fillna(0)
            for c in incident_counts.columns:
                if c.startswith("incident_"):
                    incident_counts[c] = incident_counts[c].astype(int)

    PLAYERS_DIR.mkdir(parents=True, exist_ok=True)
    written = 0
    for _, row in players.iterrows():
        pid = int(row["player_id"])
        slug = str(row["player_slug"]).strip()
        if not slug:
            continue
        df = appearances[appearances["player_id"] == pid].copy()
        if df.empty:
            continue
        df["player_id"] = df["player_id"].astype(int)
        if incident_counts is not None:
            inc_sub = incident_counts[incident_counts["player_id"] == pid].copy()
            if not inc_sub.empty:
                df["match_id"] = df["match_id"].astype(str)
                inc_sub["match_id"] = inc_sub["match_id"].astype(str)
                merge_cols = [c for c in inc_sub.columns if c != "player_id"]
                df = df.merge(
                    inc_sub[merge_cols],
                    on="match_id",
                    how="left",
                )
                for c in ["incident_goals", "incident_yellow_cards", "incident_red_cards", "incident_penalty_goals", "incident_penalty_missed"]:
                    if c in df.columns:
                        df[c] = df[c].fillna(0).astype(int)
                if "incident_goals" in df.columns:
                    df["incident_count"] = df["incident_goals"].fillna(0)
                    if "incident_yellow_cards" in df.columns:
                        df["incident_count"] += df["incident_yellow_cards"].fillna(0)
                    if "incident_red_cards" in df.columns:
                        df["incident_count"] += df["incident_red_cards"].fillna(0)
                    df["incident_count"] = df["incident_count"].astype(int)
        out_path = PLAYERS_DIR / f"{slug}.csv"
        if args.dry_run:
            print(f"Would write {out_path.name} ({len(df)} rows)")
        else:
            df.to_csv(out_path, index=False)
        written += 1

    print(f"{'Would write' if args.dry_run else 'Wrote'} {written} player CSV(s) under {PLAYERS_DIR}")


if __name__ == "__main__":
    main()
