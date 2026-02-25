#!/bin/bash
# Extract top 5 leagues + UCL, all 4 seasons (recent first).
# Run from project root: bash scripts/run_extraction_top5_ucl.sh

set -e
cd "$(dirname "$0")/.."
SEASONS="2025-26 2024-25 2023-24 2022-23"
COMPS="england-premier-league spain-laliga italy-serie-a germany-bundesliga france-ligue-1 uefa-champions-league"

for comp in $COMPS; do
  for season in $SEASONS; do
    echo "=== $comp $season ==="
    python3 src/extract_batch.py "$comp" "$season" --delay 0.3 --no-validate || true
  done
done
echo "=== Extraction complete ==="
