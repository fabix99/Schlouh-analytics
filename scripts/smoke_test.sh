#!/usr/bin/env bash
# Smoke test: config load + API contract. Optional: run pipeline if index exists.
# Used by .github/workflows/ci.yml. Run from repo root.
set -e

echo "=== Smoke test: config ==="
python3 -c "
from pathlib import Path
import sys
sys.path.insert(0, str(Path('src').resolve()))
from config import ROOT, INDEX_PATH
assert ROOT.exists(), 'Project root missing'
print('Config OK')
"

echo "=== Smoke test: API contract ==="
python3 scripts/check_api_contract.py

echo "=== Smoke test done ==="
