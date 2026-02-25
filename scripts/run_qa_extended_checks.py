#!/usr/bin/env python3
"""
Extended QA checks from DATA_QA_MEGA_PROMPT: index vs raw, football.db, stratified raw sample.
Read-only; prints JSON-friendly summary to stdout.
"""
import json
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

try:
    from src.config import RAW_BASE, DERIVED_DIR, PROCESSED_DIR, INDEX_DIR
except ImportError:
    RAW_BASE = ROOT / "data" / "raw"
    DERIVED_DIR = ROOT / "data" / "derived"
    PROCESSED_DIR = ROOT / "data" / "processed"
    INDEX_DIR = ROOT / "data" / "index"

DB_PATH = ROOT / "data" / "football.db"


def get_raw_match_ids():
    ids = set()
    if not RAW_BASE.exists():
        return ids
    for season_dir in RAW_BASE.iterdir():
        if not season_dir.is_dir():
            continue
        for realm_dir in season_dir.iterdir():
            if not realm_dir.is_dir() or realm_dir.name.startswith("."):
                continue
            for comp_dir in realm_dir.iterdir():
                if not comp_dir.is_dir():
                    continue
                for match_dir in comp_dir.iterdir():
                    if match_dir.is_dir() and (match_dir / "lineups.csv").exists():
                        ids.add(match_dir.name)
    return ids


def get_raw_sample_list(n_per_pair=2, min_pairs=5, min_total=20):
    """Stratified: (season, realm, competition_slug, match_id) per pair."""
    if not RAW_BASE.exists():
        return []
    pairs = {}  # (season, realm, comp) -> [match_id, ...]
    for season_dir in sorted(RAW_BASE.iterdir()):
        if not season_dir.is_dir():
            continue
        season = season_dir.name
        for realm_dir in sorted(season_dir.iterdir()):
            if not realm_dir.is_dir() or realm_dir.name.startswith("."):
                continue
            realm = realm_dir.name
            for comp_dir in sorted(realm_dir.iterdir()):
                if not comp_dir.is_dir():
                    continue
                comp = comp_dir.name
                key = (season, realm, comp)
                for match_dir in sorted(comp_dir.iterdir()):
                    if match_dir.is_dir() and (match_dir / "lineups.csv").exists():
                        if key not in pairs:
                            pairs[key] = []
                        pairs[key].append(match_dir.name)
    # Sample: at least n_per_pair from min_pairs pairs, then fill to min_total
    sampled = []
    keys = sorted(pairs.keys())
    for key in keys[: min_pairs + 10]:  # take a few extra pairs
        if len(sampled) >= min_total and len([s for s in sampled if s[0:3] == key]) >= min_pairs:
            break
        match_ids = pairs[key][:n_per_pair]
        for mid in match_ids:
            sampled.append((key[0], key[1], key[2], mid))
        if len(sampled) >= min_total:
            break
    return sampled[: max(min_total, min_pairs * n_per_pair)]


def check_raw_sample(sample_list):
    """For each sampled dir: lineups.csv, incidents.csv, team_statistics.csv exist and readable; incidents has FT."""
    results = []
    required_lineup_cols = ["player_id", "match_id", "stat_minutesPlayed", "stat_rating"]
    for season, realm, comp, match_id in sample_list:
        match_dir = RAW_BASE / season / realm / comp / match_id
        rec = {"season": season, "realm": realm, "competition_slug": comp, "match_id": match_id}
        rec["dir_exists"] = match_dir.is_dir()
        lineups = match_dir / "lineups.csv"
        incidents = match_dir / "incidents.csv"
        team_stats = match_dir / "team_statistics.csv"
        rec["lineups_exists"] = lineups.exists()
        rec["incidents_exists"] = incidents.exists()
        rec["team_statistics_exists"] = team_stats.exists()
        rec["lineups_readable"] = False
        rec["lineups_columns_ok"] = False
        rec["incidents_has_ft"] = False
        rec["encoding_note"] = None
        if lineups.exists():
            try:
                import pandas as pd
                df = pd.read_csv(lineups, nrows=5, encoding="utf-8")
                rec["lineups_readable"] = True
                missing = [c for c in required_lineup_cols if c not in df.columns]
                rec["lineups_columns_ok"] = len(missing) == 0
                if missing:
                    rec["missing_columns"] = missing
            except Exception as e:
                rec["lineups_error"] = str(e)[:200]
        if incidents.exists():
            try:
                import pandas as pd
                df = pd.read_csv(incidents, encoding="utf-8")
                if "incidentType" in df.columns:
                    rec["incidents_has_ft"] = (df["incidentType"].astype(str).str.strip() == "FT").any()
                elif "type" in df.columns:
                    rec["incidents_has_ft"] = (df["type"].astype(str).str.strip() == "FT").any()
                else:
                    rec["incidents_has_ft"] = False
            except Exception as e:
                rec["incidents_error"] = str(e)[:200]
        results.append(rec)
    return results


def main():
    import pandas as pd

    out = {
        "index_match_id_has_raw": {},
        "football_db": {},
        "raw_sample": {},
        "derived_match_scores_vs_00": {},
        "optional_artifacts": {},
    }

    # Index vs raw
    index_path = INDEX_DIR / "matches.csv"
    if index_path.exists():
        matches = pd.read_csv(index_path)
        matches["match_id"] = matches["match_id"].astype(str)
        index_ids = set(matches["match_id"].unique())
    else:
        index_ids = set()
    raw_ids = get_raw_match_ids()
    in_index_not_raw = index_ids - raw_ids
    in_raw_not_index = raw_ids - index_ids
    out["index_match_id_has_raw"] = {
        "index_count": len(index_ids),
        "raw_count": len(raw_ids),
        "in_index_not_raw_count": len(in_index_not_raw),
        "in_index_not_raw_sample": list(in_index_not_raw)[:10] if in_index_not_raw else [],
        "in_raw_not_index_count": len(in_raw_not_index),
        "status": "PASS" if len(in_index_not_raw) == 0 else "WARN",
        "detail": "indexed but not yet extracted" if in_index_not_raw else "all index matches have raw",
    }

    # football.db
    if DB_PATH.exists():
        conn = sqlite3.connect(str(DB_PATH))
        cur = conn.cursor()
        cur.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
        tables = [r[0] for r in cur.fetchall()]
        expected_tables = ["player_season_stats", "player_team_lookup", "team_season_stats", "match_summary", "players_index"]
        out["football_db"] = {
            "exists": True,
            "tables_found": tables,
            "expected_tables": expected_tables,
            "all_expected_present": all(t in tables for t in expected_tables),
            "row_counts": {},
        }
        for t in expected_tables:
            if t in tables:
                cur.execute(f"SELECT COUNT(*) FROM [{t}]")
                out["football_db"]["row_counts"][t] = cur.fetchone()[0]
        conn.close()
        # Compare to sources
        try:
            df03 = pd.read_parquet(PROCESSED_DIR / "03_player_season_stats.parquet")
            df02 = pd.read_parquet(PROCESSED_DIR / "02_match_summary.parquet")
            df01 = pd.read_parquet(PROCESSED_DIR / "01_team_season_stats.parquet")
            out["football_db"]["source_rows"] = {
                "03_player_season_stats": len(df03),
                "02_match_summary": len(df02),
                "01_team_season_stats": len(df01),
            }
            out["football_db"]["row_count_match"] = (
                out["football_db"]["row_counts"].get("player_season_stats") == len(df03)
                and out["football_db"]["row_counts"].get("match_summary") == len(df02)
                and out["football_db"]["row_counts"].get("team_season_stats") == len(df01)
            )
        except Exception as e:
            out["football_db"]["source_comparison_error"] = str(e)[:200]
    else:
        out["football_db"] = {"exists": False, "note": "football.db not built yet"}

    # Stratified raw sample
    sample_list = get_raw_sample_list(2, 5, 20)
    out["raw_sample"] = {
        "sample_size": len(sample_list),
        "sample_list": sample_list[:25],
        "checks": check_raw_sample(sample_list),
    }
    checks = out["raw_sample"]["checks"]
    out["raw_sample"]["all_dirs_ok"] = all(c.get("dir_exists") and c.get("lineups_exists") and c.get("lineups_readable") for c in checks)
    out["raw_sample"]["all_columns_ok"] = all(c.get("lineups_columns_ok", False) for c in checks)
    out["raw_sample"]["all_ft_ok"] = all(c.get("incidents_has_ft", False) for c in checks if c.get("incidents_exists"))

    # derived match_scores vs 00
    try:
        ms = pd.read_parquet(DERIVED_DIR / "match_scores.parquet")
        df00 = pd.read_parquet(PROCESSED_DIR / "00_match_scores_full.parquet")
        ms["match_id"] = ms["match_id"].astype(str)
        df00["match_id"] = df00["match_id"].astype(str)
        merged = ms.merge(df00, on="match_id", how="inner", suffixes=("_derived", "_00"))
        if len(merged) > 0:
            h_match = (merged["home_score"] == merged["home_score_00"]) | (merged["home_score"].isna() & merged["home_score_00"].isna())
            a_match = (merged["away_score"] == merged["away_score_00"]) | (merged["away_score"].isna() & merged["away_score_00"].isna())
            mismatches = (~(h_match & a_match)).sum()
            out["derived_match_scores_vs_00"] = {"merged_count": len(merged), "score_mismatches": int(mismatches), "status": "PASS" if mismatches == 0 else "FAIL"}
        else:
            out["derived_match_scores_vs_00"] = {"merged_count": 0, "status": "WARN", "detail": "no overlap"}
    except Exception as e:
        out["derived_match_scores_vs_00"] = {"status": "WARN", "error": str(e)[:200]}

    # Optional artifacts
    for name, path in [
        ("extraction_batch_errors.csv", INDEX_DIR / "extraction_batch_errors.csv"),
        ("pipeline_runs.csv", INDEX_DIR / "pipeline_runs.csv"),
        ("latest_successful_run.json", INDEX_DIR / "latest_successful_run.json"),
    ]:
        if path.exists():
            try:
                if path.suffix == ".json":
                    with open(path) as f:
                        json.load(f)
                    out["optional_artifacts"][name] = {"present": True, "readable": True}
                else:
                    pd.read_csv(path, nrows=1)
                    out["optional_artifacts"][name] = {"present": True, "readable": True}
            except Exception as e:
                out["optional_artifacts"][name] = {"present": True, "readable": False, "error": str(e)[:100]}
        else:
            out["optional_artifacts"][name] = {"present": False, "note": "optional artifact absent"}

    def to_serializable(obj):
        if isinstance(obj, dict):
            return {k: to_serializable(v) for k, v in obj.items()}
        if isinstance(obj, list):
            return [to_serializable(x) for x in obj]
        if hasattr(obj, "item") and callable(obj.item):  # numpy scalar
            return obj.item()
        if isinstance(obj, (bool, int, float, str, type(None))):
            return obj
        return str(obj)

    print(json.dumps(to_serializable(out), indent=2))


if __name__ == "__main__":
    main()
