#!/usr/bin/env python3
"""
Deterministic pipeline: derived data, processed build steps (00–16), dq_check, validate_data.

Run from project root. Stops on first failure when --fail-fast is set.

Usage:
  python scripts/run_pipeline.py
  python scripts/run_pipeline.py --from-step 00 --to-step 02
  python scripts/run_pipeline.py --fail-fast
  python scripts/run_pipeline.py --rebuild-all
"""

import argparse
import csv
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

_project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_project_root / "src"))
from config import ENV, INDEX_DIR, ROOT

PIPELINE_RUNS_PATH = INDEX_DIR / "pipeline_runs.csv"
LATEST_SUCCESS_JSON = INDEX_DIR / "latest_successful_run.json"
RUN_COLS = ["run_id", "started_utc", "ended_utc", "steps_run", "status", "failed_step", "env"]


def _ensure_runs_file():
    if not PIPELINE_RUNS_PATH.exists():
        PIPELINE_RUNS_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(PIPELINE_RUNS_PATH, "w", newline="") as f:
            w = csv.writer(f)
            w.writerow(RUN_COLS)


def _append_run_row(row: dict):
    _ensure_runs_file()
    with open(PIPELINE_RUNS_PATH, "a", newline="") as f:
        w = csv.DictWriter(f, fieldnames=RUN_COLS, extrasaction="ignore")
        w.writerow(row)


def _update_last_run(run_id: str, ended_utc: str, status: str, failed_step: str):
    if not PIPELINE_RUNS_PATH.exists():
        return
    with open(PIPELINE_RUNS_PATH) as f:
        rows = list(csv.DictReader(f))
    for i in range(len(rows) - 1, -1, -1):
        if rows[i].get("run_id") == run_id and rows[i].get("status") == "running":
            rows[i]["ended_utc"] = ended_utc
            rows[i]["status"] = status
            rows[i]["failed_step"] = failed_step
            break
    with open(PIPELINE_RUNS_PATH, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=RUN_COLS)
        w.writeheader()
        w.writerows(rows)


STEPS = [
    ("index", "Index check", ["python3", "-c", "import sys; from pathlib import Path; p=Path('data/index/matches.csv'); sys.exit(0 if p.exists() else 1)"]),
    ("derived", "Derived (player_appearances, incidents, match_scores)", [sys.executable, str(ROOT / "src/build_player_appearances.py"), "--csv"]),
    ("00", "00_fix_match_scores", [sys.executable, str(ROOT / "scripts/build/00_fix_match_scores.py")]),
    ("01", "01_team_season_stats", [sys.executable, str(ROOT / "scripts/build/01_build_team_season_stats.py")]),
    ("02", "02_match_summary", [sys.executable, str(ROOT / "scripts/build/02_build_match_summary.py")]),
    ("03", "03_player_season_stats", [sys.executable, str(ROOT / "scripts/build/03_build_player_season_stats.py")]),
    ("04", "04_player_career_stats", [sys.executable, str(ROOT / "scripts/build/04_build_player_career_stats.py")]),
    ("05", "05_competition_benchmarks", [sys.executable, str(ROOT / "scripts/build/05_build_competition_benchmarks.py")]),
    ("06", "06_player_percentile_ranks", [sys.executable, str(ROOT / "scripts/build/06_build_player_percentile_ranks.py")]),
    ("07", "07_player_rolling_form", [sys.executable, str(ROOT / "scripts/build/07_build_player_rolling_form.py")]),
    ("08", "08_player_scouting_profiles", [sys.executable, str(ROOT / "scripts/build/08_build_player_scouting_profiles.py")]),
    ("09", "09_player_progression", [sys.executable, str(ROOT / "scripts/build/09_build_player_progression.py")]),
    ("10", "10_player_consistency", [sys.executable, str(ROOT / "scripts/build/10_build_player_consistency.py")]),
    ("11", "11_player_opponent_context", [sys.executable, str(ROOT / "scripts/build/11_build_player_opponent_context.py")]),
    ("12", "12_substitution_impact", [sys.executable, str(ROOT / "scripts/build/12_build_substitution_impact.py")]),
    ("13", "13_match_momentum", [sys.executable, str(ROOT / "scripts/build/13_build_match_momentum.py")]),
    ("14", "14_managers", [sys.executable, str(ROOT / "scripts/build/14_build_managers.py")]),
    ("15", "15_team_tactical_profiles", [sys.executable, str(ROOT / "scripts/build/15_build_team_tactical_profiles.py")]),
    ("16", "16_player_age_curves", [sys.executable, str(ROOT / "scripts/build/16_build_player_age_curves.py")]),
    ("dq", "dq_check", [sys.executable, str(ROOT / "scripts/build/dq_check.py")]),
    ("validate", "validate_data", [sys.executable, str(ROOT / "scripts/validate_data.py")]),
]

STEP_IDS = [s[0] for s in STEPS]


def main():
    ap = argparse.ArgumentParser(description="Run pipeline steps (derived → processed → dq → validate)")
    ap.add_argument("--from-step", default=STEP_IDS[0], choices=STEP_IDS, help="First step to run (inclusive)")
    ap.add_argument("--to-step", default=STEP_IDS[-1], choices=STEP_IDS, help="Last step to run (inclusive)")
    ap.add_argument("--fail-fast", action="store_true", help="Stop on first non-zero exit")
    ap.add_argument("--rebuild-all", action="store_true", help="Run from 'derived' through 'validate' (overrides from/to)")
    args = ap.parse_args()

    from_idx = STEP_IDS.index(args.from_step)
    to_idx = STEP_IDS.index(args.to_step)
    if args.rebuild_all:
        from_idx = STEP_IDS.index("derived")
        to_idx = len(STEP_IDS) - 1
    if from_idx > to_idx:
        print("Invalid range: from-step must be before or equal to to-step", file=sys.stderr)
        sys.exit(1)

    steps_to_run = STEPS[from_idx : to_idx + 1]
    steps_run_str = ",".join(s[0] for s in steps_to_run)
    run_id = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    started_utc = run_id
    _append_run_row({
        "run_id": run_id,
        "started_utc": started_utc,
        "ended_utc": "",
        "steps_run": steps_run_str,
        "status": "running",
        "failed_step": "",
        "env": ENV,
    })

    failed_step = ""
    status = "ok"
    for step_id, label, cmd in steps_to_run:
        print(f"\n--- {step_id}: {label} ---")
        result = subprocess.run(cmd, cwd=str(ROOT))
        if result.returncode != 0:
            print(f"  FAILED exit code {result.returncode}", file=sys.stderr)
            if not failed_step:
                failed_step = step_id
            status = "fail"
            if args.fail_fast:
                _update_last_run(run_id, datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), status, failed_step)
                sys.exit(result.returncode)
    ended_utc = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    _update_last_run(run_id, ended_utc, status, failed_step)
    if status == "ok":
        INDEX_DIR.mkdir(parents=True, exist_ok=True)
        with open(LATEST_SUCCESS_JSON, "w") as f:
            json.dump({"ended_utc": ended_utc, "run_id": run_id, "steps_run": steps_run_str, "env": ENV}, f, indent=2)
    print("\nPipeline run finished.")


if __name__ == "__main__":
    main()
