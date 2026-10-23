#!/usr/bin/env bash
# Full platform slice: init warehouse → DLT load → dbt build → validate.
# Run from project root: bash platform/scripts/run_platform.sh
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT"

if [[ -f .venv/bin/activate ]]; then
  # shellcheck disable=SC1091
  source .venv/bin/activate
fi

echo "=== 1/5 init warehouse ==="
python platform/scripts/init_warehouse.py

echo "=== 2/5 DLT load ==="
python platform/pipelines/sofascore_load.py --source platform/fixtures

echo "=== 3/5 dbt build ==="
(
  cd platform/dbt
  dbt build --profiles-dir .
)

echo "=== 4/5 validate ==="
python platform/scripts/validate_platform.py

echo "=== 5/5 AI retrieval index ==="
python platform/ai/build_retrieval_index.py

echo "=== platform pipeline OK ==="
