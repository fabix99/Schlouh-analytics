"""
5.2 Penalty profile - Conversion rate, scored vs missed.
Usage: python viz/scripts/17_penalty_profile.py [player_slug]
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import matplotlib.pyplot as plt
import pandas as pd

from viz.config import DATA_SOURCE_FOOTNOTE, DEFAULT_PLAYER_SLUG, OUTPUT_DIR, OUTPUT_FORMAT, DPI
from viz.data_utils import load_player


def plot_penalty_profile(player_slug: str) -> Path:
    out_dir = OUTPUT_DIR / "05_incidents"
    out_dir.mkdir(parents=True, exist_ok=True)

    df = load_player(player_slug)
    name = df["player_shortName"].iloc[0] if "player_shortName" in df.columns else player_slug

    penalty_goals = df.get("incident_penalty_goals", 0)
    penalty_missed = df.get("incident_penalty_missed", 0)
    if hasattr(penalty_goals, "sum"):
        scored = int(penalty_goals.sum())
    else:
        scored = int(penalty_goals) if pd.notna(penalty_goals) else 0
    if hasattr(penalty_missed, "sum"):
        missed = int(penalty_missed.sum())
    else:
        missed = int(penalty_missed) if pd.notna(penalty_missed) else 0

    total = scored + missed
    conv = 100 * scored / total if total > 0 else 0

    period = ""
    if "match_date_utc" in df.columns and df["match_date_utc"].notna().any():
        df["match_date_utc"] = pd.to_datetime(df["match_date_utc"])
        period = f" ({df['match_date_utc'].min().strftime('%Y')}–{df['match_date_utc'].max().strftime('%Y')})"

    fig, axes = plt.subplots(1, 2, figsize=(8, 4))

    axes[0].bar(["Scored", "Missed"], [scored, missed], color=["#2ecc71", "#e74c3c"])
    axes[0].set_ylabel("Count")
    axes[0].set_title(f"Penalties (n={total})")

    axes[1].text(0.5, 0.6, f"{conv:.0f}%\n({scored}/{total})", ha="center", va="center", fontsize=24)
    axes[1].text(0.5, 0.25, "League Fwd avg ~78%", ha="center", va="center", fontsize=10, color="gray")
    axes[1].set_title("Conversion rate")
    axes[1].axis("off")

    fig.suptitle(f"{name} — Penalty profile{period}", fontsize=12, y=1.02)
    fig.text(0.5, 0.01, DATA_SOURCE_FOOTNOTE, ha="center", fontsize=7, color="gray")
    plt.tight_layout(rect=[0, 0.04, 1, 0.96])

    out_path = out_dir / f"penalty_profile_{player_slug}.{OUTPUT_FORMAT}"
    fig.savefig(out_path, dpi=DPI, bbox_inches="tight")
    plt.close()
    return out_path


if __name__ == "__main__":
    player = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_PLAYER_SLUG
    p = plot_penalty_profile(player)
    print(f"Saved: {p}")
