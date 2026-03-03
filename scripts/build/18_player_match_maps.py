"""
Step 18: Build heatmap and shotmap parquet from raw players/*.json (optional).

Reads data/raw/{season}/club/{competition_slug}/{match_id}/players/heatmap_{id}.json
and shotmap_{id}.json where present.
Outputs:
  - data/processed/18_heatmap_points.parquet (match_id, player_id, x, y)
  - data/processed/18_shotmap_events.parquet (match_id, player_id, shot_type, situation, x, y, xg, ...)
Skips matches with no players/ subdir or empty files.
"""

import json
import sys
from pathlib import Path
from typing import Optional

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

from scripts.build.utils import RAW_DIR, PROCESSED_DIR, INDEX_DIR


def get_raw_match_dir(match_id: str, season: str, competition_slug: str) -> Optional[Path]:
    p = RAW_DIR / str(season) / "club" / competition_slug / str(match_id)
    return p if p.exists() else None


def main():
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    matches = pd.read_csv(INDEX_DIR / "matches.csv")
    matches["match_id"] = matches["match_id"].astype(str)

    heatmap_rows = []
    shotmap_rows = []

    for _, row in matches.iterrows():
        match_id = row["match_id"]
        season = row["season"]
        comp = row["competition_slug"]
        match_dir = get_raw_match_dir(match_id, season, comp)
        if not match_dir:
            continue
        players_dir = match_dir / "players"
        if not players_dir.exists():
            continue
        for path in players_dir.glob("heatmap_*.json"):
            try:
                with open(path, encoding="utf-8") as f:
                    data = json.load(f)
            except (json.JSONDecodeError, OSError):
                continue
            points = data.get("heatmap") if isinstance(data, dict) else []
            if not isinstance(points, list):
                continue
            try:
                player_id = int(path.stem.replace("heatmap_", ""))
            except ValueError:
                continue
            for pt in points:
                if isinstance(pt, dict) and "x" in pt and "y" in pt:
                    heatmap_rows.append({
                        "match_id": match_id,
                        "player_id": player_id,
                        "x": pt.get("x"),
                        "y": pt.get("y"),
                    })

        for path in players_dir.glob("shotmap_*.json"):
            try:
                with open(path, encoding="utf-8") as f:
                    data = json.load(f)
            except (json.JSONDecodeError, OSError):
                continue
            shots = data.get("shotmap") if isinstance(data, dict) else []
            if not isinstance(shots, list):
                continue
            try:
                player_id = int(path.stem.replace("shotmap_", ""))
            except ValueError:
                continue
            for s in shots:
                if not isinstance(s, dict):
                    continue
                coords = s.get("playerCoordinates") or {}
                x = coords.get("x") if isinstance(coords, dict) else None
                y = coords.get("y") if isinstance(coords, dict) else None
                shotmap_rows.append({
                    "match_id": match_id,
                    "player_id": player_id,
                    "shot_type": s.get("shotType"),
                    "situation": s.get("situation"),
                    "x": x,
                    "y": y,
                    "xg": s.get("xg"),
                })

    if heatmap_rows:
        df_h = pd.DataFrame(heatmap_rows)
        out_h = PROCESSED_DIR / "18_heatmap_points.parquet"
        df_h.to_parquet(out_h, index=False)
        print(f"Wrote {out_h} ({len(df_h)} rows)")
    else:
        print("No heatmap JSONs found; skipping 18_heatmap_points.parquet")

    if shotmap_rows:
        df_s = pd.DataFrame(shotmap_rows)
        out_s = PROCESSED_DIR / "18_shotmap_events.parquet"
        df_s.to_parquet(out_s, index=False)
        print(f"Wrote {out_s} ({len(df_s)} rows)")
    else:
        print("No shotmap JSONs found; skipping 18_shotmap_events.parquet")


if __name__ == "__main__":
    main()
