"""
5.1 Goal timeline - Goals and assists per match over time (chronological).
Usage: python viz/scripts/16_goal_timeline.py [player_slug]
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import numpy as np
import matplotlib.pyplot as plt
import pandas as pd

from viz.config import DATA_SOURCE_FOOTNOTE, DEFAULT_PLAYER_SLUG, OUTPUT_DIR, OUTPUT_FORMAT, DPI
from viz.data_utils import load_player


def plot_goal_timeline(player_slug: str) -> Path:
    out_dir = OUTPUT_DIR / "05_incidents"
    out_dir.mkdir(parents=True, exist_ok=True)

    df = load_player(player_slug)
    df = df.sort_values("match_date_utc").reset_index(drop=True)
    name = df["player_shortName"].iloc[0] if "player_shortName" in df.columns else player_slug

    goals = df.get("incident_goals", df.get("stat_goals", 0))
    if hasattr(goals, "fillna"):
        goals = goals.fillna(0).values
    else:
        goals = np.array([float(goals)] * len(df) if len(df) else [])
    assists = df.get("stat_goalAssist", 0)
    if hasattr(assists, "fillna"):
        assists = assists.fillna(0).values
    else:
        assists = np.array([float(assists)] * len(df) if len(df) else [])

    dates = pd.to_datetime(df["match_date_utc"])
    ga = goals + assists
    roll_ga = pd.Series(ga).rolling(5, min_periods=1).mean()

    fig, ax = plt.subplots(figsize=(12, 5))
    x = np.arange(len(dates))
    w = 0.35
    ax.bar(x - w / 2, goals, width=w, color="steelblue", alpha=0.8, label="Goals")
    ax.bar(x + w / 2, assists, width=w, color="coral", alpha=0.8, label="Assists")
    ax.plot(x, roll_ga, color="darkgreen", linewidth=2, label="Rolling 5G (G+A)")
    step = max(1, len(x) // 20)
    ax.set_xticks(x[::step])
    ax.set_xticklabels([dates.iloc[i].strftime("%Y-%m-%d") for i in range(0, len(dates), step)], rotation=45, ha="right")
    ax.set_ylabel("Goals / Assists")
    ax.set_title(f"{name} — Goal timeline (per match, chronological)")
    ax.legend()
    ax.grid(True, alpha=0.3, axis="y")
    fig.text(0.5, 0.01, DATA_SOURCE_FOOTNOTE, ha="center", fontsize=7, color="gray")
    plt.tight_layout(rect=[0, 0.05, 1, 1])

    out_path = out_dir / f"goal_timeline_{player_slug}.{OUTPUT_FORMAT}"
    fig.savefig(out_path, dpi=DPI, bbox_inches="tight")
    plt.close()
    return out_path


if __name__ == "__main__":
    player = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_PLAYER_SLUG
    p = plot_goal_timeline(player)
    print(f"Saved: {p}")
