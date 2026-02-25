"""
3.2 Value breakdown - Pass, dribble, defend, shot value (season avg).
Usage: python viz/scripts/09_value_breakdown.py [player_slug]
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import matplotlib.pyplot as plt
import pandas as pd

from viz.config import DATA_SOURCE_FOOTNOTE, DEFAULT_PLAYER_SLUG, OUTPUT_DIR, OUTPUT_FORMAT, DPI
from viz.data_utils import load_player, VALUE_COLS


def plot_value_breakdown(player_slug: str) -> Path:
    out_dir = OUTPUT_DIR / "03_profile"
    out_dir.mkdir(parents=True, exist_ok=True)

    df = load_player(player_slug)
    name = df["player_shortName"].iloc[0] if "player_shortName" in df.columns else player_slug
    total_mins = df["stat_minutesPlayed"].sum()
    if total_mins <= 0:
        total_mins = 1

    labels = ["Pass", "Dribble", "Defend", "Shot"]
    vals = []
    for c in VALUE_COLS:
        if c not in df.columns:
            vals.append(0.0)
            continue
        # Per-90: sum(value) / total_mins * 90
        v = (df[c].fillna(0).sum() / total_mins) * 90
        vals.append(float(v))

    y_max = max(max(vals) * 1.15, 0.5) if vals else 0.5
    fig, ax = plt.subplots(figsize=(7, 4))
    colors = ["#2ecc71", "#3498db", "#e74c3c", "#f39c12"]
    ax.bar(labels, vals, color=colors, edgecolor="white")
    ax.set_ylim(0, y_max)
    ax.set_ylabel("Normalized value per 90 (season)")
    ax.set_title(f"{name} — Sofascore value breakdown")
    fig.text(0.5, 0.01, f"{DATA_SOURCE_FOOTNOTE} Value = Sofascore action weights, season avg per 90.", ha="center", fontsize=7, color="gray")
    plt.tight_layout(rect=[0, 0.05, 1, 1])

    out_path = out_dir / f"value_breakdown_{player_slug}.{OUTPUT_FORMAT}"
    fig.savefig(out_path, dpi=DPI, bbox_inches="tight")
    plt.close()
    return out_path


if __name__ == "__main__":
    player = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_PLAYER_SLUG
    p = plot_value_breakdown(player)
    print(f"Saved: {p}")
