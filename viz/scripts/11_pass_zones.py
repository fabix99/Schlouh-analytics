"""
3.4 Pass zone - Own half vs opposition half pass volume/accuracy (and per 90).
Usage: python viz/scripts/11_pass_zones.py [player_slug]
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


def plot_pass_zones(player_slug: str) -> Path:
    out_dir = OUTPUT_DIR / "03_profile"
    out_dir.mkdir(parents=True, exist_ok=True)

    df = load_player(player_slug)
    name = df["player_shortName"].iloc[0] if "player_shortName" in df.columns else player_slug
    total_mins = df["stat_minutesPlayed"].sum()
    if total_mins <= 0:
        total_mins = 1
    mins_90 = total_mins / 90

    # Use half columns if present, else fallback to total pass split (we don't have thirds in standard schema)
    if "stat_totalOwnHalfPasses" in df.columns and "stat_totalOppositionHalfPasses" in df.columns:
        own_tot = df["stat_totalOwnHalfPasses"].fillna(0).sum()
        opp_tot = df["stat_totalOppositionHalfPasses"].fillna(0).sum()
        own_acc_v = df["stat_accurateOwnHalfPasses"].fillna(0).sum()
        opp_acc_v = df["stat_accurateOppositionHalfPasses"].fillna(0).sum()
    else:
        # Fallback: assume ~30% own half, 70% opposition for forwards (rough)
        total_pass = df["stat_totalPass"].fillna(0).sum()
        total_acc = df["stat_accuratePass"].fillna(0).sum()
        own_tot = total_pass * 0.3
        opp_tot = total_pass * 0.7
        own_acc_v = total_acc * 0.3
        opp_acc_v = total_acc * 0.7

    own_acc = 100 * own_acc_v / own_tot if own_tot > 0 else 0
    opp_acc = 100 * opp_acc_v / opp_tot if opp_tot > 0 else 0

    own_per90 = own_tot / mins_90
    opp_per90 = opp_tot / mins_90

    fig, axes = plt.subplots(1, 2, figsize=(8, 4))

    axes[0].set_ylim(0, max(own_tot, opp_tot) * 1.12)
    bars0 = axes[0].bar(["Own half", "Opposition half"], [own_tot, opp_tot], color=["#3498db", "#e74c3c"], alpha=0.8)
    for bar, val in zip(bars0, [own_tot, opp_tot]):
        axes[0].text(bar.get_x() + bar.get_width() / 2, bar.get_height(),
                     f"{int(val)}", ha="center", va="bottom", fontsize=10, fontweight="bold")
    axes[0].set_ylabel("Total passes")
    axes[0].set_title(f"Pass volume by zone\n(per 90: {own_per90:.0f} / {opp_per90:.0f})")

    axes[1].set_ylim(0, 105)
    bars1 = axes[1].bar(["Own half", "Opposition half"], [own_acc, opp_acc], color=["#3498db", "#e74c3c"], alpha=0.8)
    for bar, val in zip(bars1, [own_acc, opp_acc]):
        axes[1].text(bar.get_x() + bar.get_width() / 2, bar.get_height(),
                     f"{val:.0f}%", ha="center", va="bottom", fontsize=10, fontweight="bold")
    axes[1].set_ylabel("Accuracy %")
    axes[1].set_title("Pass accuracy by zone")

    fig.suptitle(f"{name} — Pass zones (season)", fontsize=12, y=1.02)
    fig.text(0.5, 0.01, DATA_SOURCE_FOOTNOTE, ha="center", fontsize=7, color="gray")
    plt.tight_layout(rect=[0, 0.04, 1, 0.96])

    out_path = out_dir / f"pass_zones_{player_slug}.{OUTPUT_FORMAT}"
    fig.savefig(out_path, dpi=DPI, bbox_inches="tight")
    plt.close()
    return out_path


if __name__ == "__main__":
    player = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_PLAYER_SLUG
    p = plot_pass_zones(player)
    print(f"Saved: {p}")
