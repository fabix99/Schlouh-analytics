"""
Step 13: Parse graph.json files -> (match_id, minute, momentum_value); summary table.
Output: data/processed/13_match_momentum.parquet, match_momentum_summary.parquet
"""

import json
import sys
from pathlib import Path

import pandas as pd
import numpy as np

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

from scripts.build.utils import RAW_DIR, PROCESSED_DIR, INDEX_DIR


def iter_graph_files():
    for season_dir in sorted(RAW_DIR.iterdir()):
        if not season_dir.is_dir() or season_dir.name.startswith("."):
            continue
        club = season_dir / "club"
        if not club.exists():
            continue
        for comp_dir in sorted(club.iterdir()):
            if not comp_dir.is_dir() or comp_dir.name.startswith("."):
                continue
            for match_dir in sorted(comp_dir.iterdir()):
                if not match_dir.is_dir() or match_dir.name.startswith("."):
                    continue
                path = match_dir / "graph.json"
                if path.exists():
                    yield match_dir.name, path


def main():
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    rows = []
    for match_id, path in iter_graph_files():
        try:
            with open(path) as f:
                data = json.load(f)
        except Exception as e:
            continue
        points = data.get("graphPoints") or []
        for p in points:
            rows.append({
                "match_id": match_id,
                "minute": int(p.get("minute", 0)),
                "momentum_value": int(p.get("value", 0)),
                "period": "1ST" if p.get("minute", 0) <= 45 else "2ND",
            })
    detail = pd.DataFrame(rows)
    out_path = PROCESSED_DIR / "13_match_momentum.parquet"
    detail.to_parquet(out_path, index=False)
    print(f"Wrote {out_path} ({len(detail)} rows)")

    if detail.empty:
        summary = pd.DataFrame()
    else:
        summary = detail.groupby("match_id").agg(
            avg_home_momentum=("momentum_value", "mean"),
            home_dominated_minutes=("momentum_value", lambda x: (x > 0).sum()),
            away_dominated_minutes=("momentum_value", lambda x: (x < 0).sum()),
            momentum_swings=("momentum_value", lambda x: (x.diff().fillna(0) != 0).sum()),
        ).reset_index()
        half = detail[detail["minute"] <= 45].groupby("match_id")["momentum_value"].last().reset_index().rename(columns={"momentum_value": "halftime_momentum"})
        summary = summary.merge(half, on="match_id", how="left")
        last = detail.groupby("match_id")["momentum_value"].last().reset_index().rename(columns={"momentum_value": "final_momentum"})
        summary = summary.merge(last, on="match_id", how="left")
    summary_path = PROCESSED_DIR / "match_momentum_summary.parquet"
    summary.to_parquet(summary_path, index=False)
    print(f"Wrote {summary_path} ({len(summary)} rows)")


if __name__ == "__main__":
    main()
