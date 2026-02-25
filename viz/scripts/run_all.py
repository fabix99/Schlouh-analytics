"""
Regenerate all visualizations. Run from project root:
  python viz/scripts/run_all.py
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from viz.config import (
    DEFAULT_MATCH_ID,
    DEFAULT_PLAYER_SLUG,
    DEFAULT_PLAYER_SLUG_2,
)


def run_all():
    import importlib.util

    scripts_dir = Path(__file__).resolve().parent
    runners = [
        ("01_match_dashboard", lambda: _run(scripts_dir / "01_match_dashboard.py", "plot_match_dashboard", DEFAULT_PLAYER_SLUG, DEFAULT_MATCH_ID)),
        ("02_match_card", lambda: _run(scripts_dir / "02_match_card.py", "plot_match_card", DEFAULT_PLAYER_SLUG, DEFAULT_MATCH_ID)),
        ("03_match_radar", lambda: _run(scripts_dir / "03_match_radar.py", "plot_match_radar", DEFAULT_PLAYER_SLUG, DEFAULT_MATCH_ID)),
        ("04_rolling_form", lambda: _run(scripts_dir / "04_rolling_form.py", "plot_rolling_form", DEFAULT_PLAYER_SLUG)),
        ("05_form_score", lambda: _run(scripts_dir / "05_form_score.py", "plot_form_score", DEFAULT_PLAYER_SLUG)),
        ("06_consistency", lambda: _run(scripts_dir / "06_consistency.py", "plot_consistency", DEFAULT_PLAYER_SLUG)),
        ("07_distribution", lambda: _run(scripts_dir / "07_distribution.py", "plot_distribution", DEFAULT_PLAYER_SLUG)),
        ("08_radar_profile", lambda: _run(scripts_dir / "08_radar_profile.py", "plot_radar_profile", DEFAULT_PLAYER_SLUG)),
        ("09_value_breakdown", lambda: _run(scripts_dir / "09_value_breakdown.py", "plot_value_breakdown", DEFAULT_PLAYER_SLUG)),
        ("10_archetype_scatter", lambda: _run(scripts_dir / "10_archetype_scatter.py", "plot_archetype_scatter")),
        ("11_pass_zones", lambda: _run(scripts_dir / "11_pass_zones.py", "plot_pass_zones", DEFAULT_PLAYER_SLUG)),
        ("12_radar_compare", lambda: _run(scripts_dir / "12_radar_compare.py", "plot_radar_compare", DEFAULT_PLAYER_SLUG, DEFAULT_PLAYER_SLUG_2)),
        ("13_bar_compare", lambda: _run(scripts_dir / "13_bar_compare.py", "plot_bar_compare", DEFAULT_PLAYER_SLUG, DEFAULT_PLAYER_SLUG_2)),
        ("14_matrix_compare", lambda: _run(scripts_dir / "14_matrix_compare.py", "plot_matrix_compare", DEFAULT_PLAYER_SLUG, DEFAULT_PLAYER_SLUG_2)),
        ("15_scatter_compare", lambda: _run(scripts_dir / "15_scatter_compare.py", "plot_scatter_compare", DEFAULT_PLAYER_SLUG, DEFAULT_PLAYER_SLUG_2)),
        ("16_goal_timeline", lambda: _run(scripts_dir / "16_goal_timeline.py", "plot_goal_timeline", DEFAULT_PLAYER_SLUG)),
        ("17_penalty_profile", lambda: _run(scripts_dir / "17_penalty_profile.py", "plot_penalty_profile", DEFAULT_PLAYER_SLUG)),
        ("18_card_risk", lambda: _run(scripts_dir / "18_card_risk.py", "plot_card_risk", DEFAULT_PLAYER_SLUG)),
        ("19_percentile", lambda: _run(scripts_dir / "19_percentile.py", "plot_percentile", DEFAULT_PLAYER_SLUG)),
    ]

    def _run(module_path, func_name, *args):
        spec = importlib.util.spec_from_file_location("mod", module_path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        func = getattr(mod, func_name)
        return func(*args)

    done = []
    failed = []
    for name, run in runners:
        try:
            result = run()
            if isinstance(result, (list, tuple)):
                done.extend([str(p) for p in result])
            else:
                done.append(str(result))
            print(f"OK: {name}")
        except Exception as e:
            print(f"FAIL: {name} — {e}")
            failed.append((name, str(e)))

    print(f"\nGenerated {len(done)} files.")
    if failed:
        print(f"Failed: {[n for n, _ in failed]}")
    return done, failed


if __name__ == "__main__":
    run_all()
