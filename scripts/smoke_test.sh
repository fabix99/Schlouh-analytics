#!/usr/bin/env bash
# Smoke test: config load only. No live API calls (extraction runs separately; dashboard uses local data).
# Used by .github/workflows/ci.yml. Run from repo root.
# To verify Sofascore API contract locally: python scripts/check_api_contract.py
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

echo "=== Smoke test done ==="
