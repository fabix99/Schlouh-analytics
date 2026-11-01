#!/usr/bin/env bash
# Full production platform path (honest end-to-end):
#   pandas (except dbt-owned 03/08) → DLT → dbt core → export 03 → pandas rest
#   → DLT refresh → dbt all marts → validate → AI index
#
# Run from project root after extracts exist:
#   bash platform/scripts/run_platform_full.sh
#   bash platform/scripts/run_platform_full.sh --skip-pandas
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT"

if [[ -f .venv/bin/activate ]]; then
  # shellcheck disable=SC1091
  source .venv/bin/activate
fi

SKIP_PANDAS=0
if [[ "${1:-}" == "--skip-pandas" ]]; then
  SKIP_PANDAS=1
fi

if [[ "$SKIP_PANDAS" -eq 0 ]]; then
  echo "=== 1/7 pandas through match summary (dbt owns 03/08) ==="
  python scripts/run_pipeline.py --from-step derived --to-step 02 --fail-fast

  echo "=== 2/7 DLT load lake → DuckDB (for dbt core) ==="
  python platform/pipelines/sofascore_load.py --mode full

  echo "=== 3/7 dbt core marts (season stats / match / team / scouting) ==="
  (
    cd platform/dbt
    dbt run --profiles-dir . --select \
      mart_player_season_stats mart_match_summary mart_team_season_stats mart_player_scouting_profiles
  )

  echo "=== 4/7 export dbt season stats → processed/03 (for pandas 04+) ==="
  python platform/scripts/export_core_marts_to_parquet.py

  echo "=== 5/7 pandas remaining steps (skip 03/08) ==="
  python scripts/run_pipeline.py --from-step 04 --fail-fast --skip-steps 08
else
  echo "=== 1-5/7 skip pandas (using existing processed/) ==="
fi

echo "=== 6/7 DLT reload + dbt all serving marts ==="
python platform/pipelines/sofascore_load.py --mode full
(
  cd platform/dbt
  dbt build --profiles-dir . --vars '{"use_processed_sources": true}'
)

echo "=== 7/7 validate warehouse marts + AI index ==="
python platform/scripts/validate_warehouse_full.py
python platform/ai/build_retrieval_index.py

echo "=== platform FULL path OK ==="
