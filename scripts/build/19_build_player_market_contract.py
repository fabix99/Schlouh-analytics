"""
Step 19: Build player-level market value, salary, and contract end for scouting.

Merges:
  - data/index/players.csv (player_id, player_name)
  - 17_player_profile_extras.parquet (market_value_eur from Sofascore best-players)
  - transfermarkt_players.parquet (if present; market_value_eur, contract_end_date; preferred over 17 for value)
  - capology_salaries.parquet (optional; salary_eur_annual, contract_end_date)

Output: data/processed/19_player_market_contract.parquet
  Columns: player_id, player_name, market_value_eur, salary_eur_annual, contract_end_date,
           source_market_value, source_salary, last_updated

Linking: Transfermarkt and Capology are matched by normalized player_name. Step does not fail if any external file is missing.
"""

import re
import sys
from pathlib import Path
from datetime import datetime, timezone

import pandas as pd
import numpy as np

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

from scripts.build.utils import PROCESSED_DIR, INDEX_DIR


def _normalize_name(s: str) -> str:
    if pd.isna(s) or not isinstance(s, str):
        return ""
    s = s.lower().strip()
    s = re.sub(r"\s+", " ", s)
    s = re.sub(r"[^\w\s]", "", s)
    return s


def main():
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)

    # Players index: player_id, player_name
    players_path = INDEX_DIR / "players.csv"
    if not players_path.exists():
        print("No players index; skipping 19_player_market_contract.parquet")
        return
    players = pd.read_csv(players_path)
    players["player_id"] = pd.to_numeric(players["player_id"], errors="coerce")
    players = players.dropna(subset=["player_id"])
    players["player_id"] = players["player_id"].astype(int)
    if "player_name" not in players.columns:
        players["player_name"] = players.get("name", "")
    players["name_norm"] = players["player_name"].astype(str).apply(_normalize_name)
    players = players[players["name_norm"] != ""].drop_duplicates(subset=["player_id"], keep="first")

    # Base: one row per player from index (keep name_norm for Capology match)
    out = players[["player_id", "player_name", "name_norm"]].copy()
    out["market_value_eur"] = np.nan
    out["salary_eur_annual"] = np.nan
    out["contract_end_date"] = ""
    out["source_market_value"] = ""
    out["source_salary"] = ""
    out["last_updated"] = pd.NaT

    # 17: latest market_value_eur per player (from Sofascore best-players)
    p17_path = PROCESSED_DIR / "17_player_profile_extras.parquet"
    if p17_path.exists():
        try:
            p17 = pd.read_parquet(p17_path)
            if not p17.empty and "player_id" in p17.columns and "market_value_eur" in p17.columns:
                p17 = p17.dropna(subset=["market_value_eur"])
                if not p17.empty:
                    latest = p17.sort_values("match_id", ascending=True).groupby("player_id", as_index=False).last()
                    latest = latest[["player_id", "market_value_eur"]]
                    out = out.merge(latest, on="player_id", how="left", suffixes=("", "_y"))
                    if "market_value_eur_y" in out.columns:
                        out["market_value_eur"] = out["market_value_eur"].fillna(out["market_value_eur_y"])
                        out = out.drop(columns=["market_value_eur_y"])
                    out.loc[out["market_value_eur"].notna(), "source_market_value"] = "sofascore_best_players"
        except Exception as e:
            print(f"Warning: could not read 17_player_profile_extras: {e}")

    if "market_value_eur" not in out.columns:
        out["market_value_eur"] = np.nan
    if "source_market_value" not in out.columns:
        out["source_market_value"] = ""

    # Transfermarkt: match by normalized name; prefer TM for market_value and set contract_end (TM does not have wages)
    tm_path = PROCESSED_DIR / "transfermarkt_players.parquet"
    if tm_path.exists():
        try:
            tm = pd.read_parquet(tm_path)
            if not tm.empty and "player_name" in tm.columns:
                tm["name_norm"] = tm["player_name"].astype(str).apply(_normalize_name)
                tm = tm[tm["name_norm"] != ""]
                tm = tm.drop_duplicates(subset=["name_norm"], keep="first")
                if "market_value_eur" in tm.columns:
                    mv_map = tm.set_index("name_norm")["market_value_eur"].dropna().to_dict()
                    tm_mv = out["name_norm"].map(mv_map)
                    out["market_value_eur"] = tm_mv.fillna(out["market_value_eur"])
                    out.loc[tm_mv.notna(), "source_market_value"] = "transfermarkt"
                if "contract_end_date" in tm.columns:
                    ce = tm.set_index("name_norm")["contract_end_date"].dropna()
                    ce = ce[ce.astype(str).str.strip().str.lower() != "nan"]
                    ce_map = ce.astype(str).to_dict()
                    out["contract_end_date"] = out["name_norm"].map(ce_map).fillna(out["contract_end_date"]).fillna("").astype(str).replace("nan", "", regex=False)
        except Exception as e:
            print(f"Warning: could not read transfermarkt_players: {e}")

    if "contract_end_date" not in out.columns:
        out["contract_end_date"] = ""

    # Capology (optional): match by normalized name, fill salary and contract_end
    cap_path = PROCESSED_DIR / "capology_salaries.parquet"
    if cap_path.exists():
        try:
            cap = pd.read_parquet(cap_path)
            if not cap.empty and "player_name" in cap.columns:
                cap["name_norm"] = cap["player_name"].astype(str).apply(_normalize_name)
                cap = cap[cap["name_norm"] != ""]
                cap = cap.drop_duplicates(subset=["name_norm"], keep="first")
                name_to_salary = cap.set_index("name_norm")["salary_eur_annual"].to_dict() if "salary_eur_annual" in cap.columns else {}
                name_to_contract = cap.set_index("name_norm")["contract_end_date"].to_dict() if "contract_end_date" in cap.columns else {}
                out["salary_eur_annual"] = out["name_norm"].map(name_to_salary)
                out["contract_end_date"] = out["name_norm"].map(name_to_contract).fillna("").astype(str)
                out.loc[out["salary_eur_annual"].notna() | (out["contract_end_date"] != ""), "source_salary"] = "capology"
        except Exception as e:
            print(f"Warning: could not read capology_salaries: {e}")

    if "salary_eur_annual" not in out.columns:
        out["salary_eur_annual"] = np.nan
    if "contract_end_date" not in out.columns:
        out["contract_end_date"] = ""
    if "source_salary" not in out.columns:
        out["source_salary"] = ""

    out["last_updated"] = datetime.now(timezone.utc)
    out = out.drop(columns=["name_norm"], errors="ignore")
    out_path = PROCESSED_DIR / "19_player_market_contract.parquet"
    out.to_parquet(out_path, index=False)
    print(f"Wrote {out_path} ({len(out)} rows)")


if __name__ == "__main__":
    main()
