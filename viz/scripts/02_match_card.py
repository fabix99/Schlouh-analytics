"""
1.2 Match card - Key stats for one match vs season average.
Usage: python viz/scripts/02_match_card.py [player_slug] [match_id]
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import matplotlib.pyplot as plt
import pandas as pd
import numpy as np

from viz.config import (
    DATA_SOURCE_FOOTNOTE,
    DEFAULT_MATCH_ID,
    DEFAULT_PLAYER_SLUG,
    OUTPUT_DIR,
    OUTPUT_FORMAT,
    DPI,
)
from viz.data_utils import load_player, get_match_row, season_aggregates


def plot_match_card(player_slug: str, match_id: str) -> Path:
    out_dir = OUTPUT_DIR / "01_single_game"
    out_dir.mkdir(parents=True, exist_ok=True)

    df = load_player(player_slug)
    row = get_match_row(df, match_id)
    name = row.get("player_shortName") or row.get("player_name") or player_slug
    opp = row["away_team_name"] if row["side"] == "home" else row["home_team_name"]
    date_str = str(row.get("match_date_utc", ""))[:10] if pd.notna(row.get("match_date_utc")) else ""
    mins = int(row.get("stat_minutesPlayed") or 0)

    # Season per-90 aggregates
    season_agg = season_aggregates(df)

    # Metrics to compare: match value (scaled to per-90) vs season per-90
    metrics = [
        ("Rating", "stat_rating", False),
        ("xG", "stat_expectedGoals", True),
        ("Shots", "stat_totalShots", True),
        ("Key passes", "stat_keyPass", True),
        ("Touches", "stat_touches", True),
    ]

    match_vals = []
    season_vals = []
    labels = []
    for label, col, per_90_scale in metrics:
        match_val = row.get(col)
        if pd.isna(match_val):
            match_val = 0
        else:
            match_val = float(match_val)
        if per_90_scale and row.get("stat_minutesPlayed") and float(row["stat_minutesPlayed"]) > 0:
            match_val = match_val / float(row["stat_minutesPlayed"]) * 90
        season_val = season_agg.get(col, 0) if isinstance(season_agg.get(col), (int, float)) else 0
        if pd.isna(season_val):
            season_val = 0
        match_vals.append(match_val)
        season_vals.append(season_val)
        labels.append(label)

    fig, ax = plt.subplots(figsize=(8, 5))
    x = np.arange(len(labels))
    w = 0.35
    bars1 = ax.bar(x - w / 2, match_vals, w, label="This match (per 90)", color="steelblue")
    bars2 = ax.bar(x + w / 2, season_vals, w, label="Season avg (per 90)", color="lightgray", alpha=0.8)
    ax.set_xticks(x)
    ax.set_xticklabels(labels)
    ax.set_ylabel("Value")
    ax.set_title(f"{name} vs {opp} — Match vs season\n{date_str}" + (f" · {mins} min" if mins else ""))
    ax.legend()
    fig.text(0.5, 0.01, DATA_SOURCE_FOOTNOTE, ha="center", fontsize=7, color="gray")
    plt.tight_layout(rect=[0, 0.03, 1, 1])

    out_path = out_dir / f"match_card_{player_slug}_{match_id}.{OUTPUT_FORMAT}"
    fig.savefig(out_path, dpi=DPI, bbox_inches="tight")
    plt.close()
    return out_path


if __name__ == "__main__":
    player = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_PLAYER_SLUG
    match = sys.argv[2] if len(sys.argv) > 2 else DEFAULT_MATCH_ID
    p = plot_match_card(player, match)
    print(f"Saved: {p}")
