"""
1.1 Match dashboard - KPI panel for one match.
Usage: python viz/scripts/01_match_dashboard.py [player_slug] [match_id]
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import matplotlib.pyplot as plt
import pandas as pd

from viz.config import (
    DATA_SOURCE_FOOTNOTE,
    DEFAULT_MATCH_ID,
    DEFAULT_PLAYER_SLUG,
    OUTPUT_DIR,
    OUTPUT_FORMAT,
    DPI,
)
from viz.data_utils import load_player, get_match_row


def plot_match_dashboard(player_slug: str, match_id: str) -> Path:
    out_dir = OUTPUT_DIR / "01_single_game"
    out_dir.mkdir(parents=True, exist_ok=True)

    df = load_player(player_slug)
    row = get_match_row(df, match_id)
    name = row.get("player_shortName") or row.get("player_name") or player_slug
    opp = row["away_team_name"] if row["side"] == "home" else row["home_team_name"]
    date_str = str(row["match_date_utc"])[:10] if pd.notna(row.get("match_date_utc")) else ""
    mins = int(row.get("stat_minutesPlayed") or 0)
    comp = str(row.get("competition_name") or row.get("competition_slug") or "")

    fig, axes = plt.subplots(2, 2, figsize=(10, 8))
    title = f"{name} — Match dashboard"
    sub = f"vs {opp} · {date_str}"
    if comp:
        sub += f" · {comp}"
    if mins:
        sub += f" · {mins} min"
    fig.suptitle(f"{title}\n{sub}", fontsize=14)

    # Top left: main KPIs
    ax = axes[0, 0]
    kpis = [
        ("Rating", row.get("stat_rating")),
        ("xG", row.get("stat_expectedGoals")),
        ("xA", row.get("stat_expectedAssists")),
        ("Shots", row.get("stat_totalShots")),
        ("Key passes", row.get("stat_keyPass")),
        ("Goals", row.get("stat_goals")),
        ("Assists", row.get("stat_goalAssist")),
    ]
    labels = [k[0] for k in kpis]
    vals = [float(k[1]) if pd.notna(k[1]) else 0 for k in kpis]
    bars = ax.barh(labels, vals, color="steelblue", alpha=0.8)
    ax.set_xlim(0, max(vals) * 1.2 if vals else 10)
    ax.set_title("Match KPIs")

    # Top right: value metrics
    ax = axes[0, 1]
    value_names = ["Pass", "Dribble", "Defend", "Shot"]
    value_cols = [
        "stat_passValueNormalized",
        "stat_dribbleValueNormalized",
        "stat_defensiveValueNormalized",
        "stat_shotValueNormalized",
    ]
    v_vals = [float(row.get(c)) if pd.notna(row.get(c)) else 0 for c in value_cols]
    ax.bar(value_names, v_vals, color=["#2ecc71", "#3498db", "#e74c3c", "#f39c12"], alpha=0.8)
    ax.set_title("Value metrics")
    ax.set_ylabel("Normalized value")

    # Bottom left: passing
    ax = axes[1, 0]
    pass_acc = 0
    if pd.notna(row.get("stat_totalPass")) and float(row["stat_totalPass"]) > 0:
        pass_acc = 100 * float(row["stat_accuratePass"] or 0) / float(row["stat_totalPass"])
    ax.bar(["Total", "Accurate"], [row.get("stat_totalPass") or 0, row.get("stat_accuratePass") or 0], color="teal", alpha=0.7)
    ax.set_title(f"Passes (accuracy: {pass_acc:.0f}%)")

    # Bottom right: duels / ball
    ax = axes[1, 1]
    ball_metrics = ["Touches", "Duels won", "Ball recovery"]
    ball_vals = [row.get("stat_touches") or 0, row.get("stat_duelWon") or 0, row.get("stat_ballRecovery") or 0]
    ax.bar(ball_metrics, [float(v) for v in ball_vals], color="coral", alpha=0.7)
    ax.set_title("Ball involvement")

    fig.text(0.5, 0.01, DATA_SOURCE_FOOTNOTE, ha="center", fontsize=7, color="gray")
    plt.tight_layout(rect=[0, 0.03, 1, 0.96])
    out_path = out_dir / f"match_dashboard_{player_slug}_{match_id}.{OUTPUT_FORMAT}"
    fig.savefig(out_path, dpi=DPI, bbox_inches="tight")
    plt.close()
    return out_path


if __name__ == "__main__":
    player = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_PLAYER_SLUG
    match = sys.argv[2] if len(sys.argv) > 2 else DEFAULT_MATCH_ID
    p = plot_match_dashboard(player, match)
    print(f"Saved: {p}")
