# Fixing validation failures

If `python scripts/validate_data.py` or `python scripts/build/dq_check.py` reports failures, use these steps.

## 0. Processed artifacts out of sync with index (match-id mismatch)

**Symptom:** `dq_check.py` fails with `all_matches_csv_ids_present — missing=N, extra=M` (for 00_match_scores_full or 02_match_summary).

**Fix:** Rebuild processed artifacts from the current index so match-level outputs match `data/index/matches.csv`:

```bash
python scripts/run_pipeline.py --from-step 00 --to-step 02
```

Then rerun quality gates:

```bash
python scripts/build/dq_check.py
python scripts/validate_data.py
```

To run the full pipeline (derived + processed + dq + validate):

```bash
python scripts/run_pipeline.py
# Or from a specific step: python scripts/run_pipeline.py --from-step derived --fail-fast
```

## 1. Duplicate rows in `data/index/extraction_progress.csv`

**Symptom:** `no_duplicate_competition_season — N duplicate rows on ['competition_slug', 'season']`

**Fix:** Deduplicate, keeping the latest row per (competition_slug, season):

```bash
python scripts/fix_extraction_progress.py
# Preview first: python scripts/fix_extraction_progress.py --dry-run
```

## 2. `data/derived/player_appearances.csv` row count does not match parquet

**Symptom:** CSV has fewer rows than `player_appearances.parquet`.

**Fix:** Regenerate the CSV from the parquet (and refresh the players index and incident-only players):

```bash
python src/build_player_appearances.py --csv
```

## 3. Player IDs in `data/derived/player_incidents.parquet` not in `data/index/players.csv`

**Symptom:** `player_id_in_players_index — N player_ids not found in players.csv`

**Fix:** Rebuild the players index so it includes players that appear only in incidents (e.g. sent off before appearing in a lineup):

```bash
python src/build_player_appearances.py
```

The build already merges in incident-only players; no separate script needed.

## 4. Issues in `data/derived/players/*.csv`

**Symptom:** `all_files_valid` fails (wrong `player_id` vs index, or slug/filename mismatch).

**Fix:** Regenerate per-player CSVs from the current parquet and index so each `{slug}.csv` has the correct `player_id`:

```bash
python scripts/build_derived_player_csvs.py
# Preview: python scripts/build_derived_player_csvs.py --dry-run
```

Files named `{slug}_appearances.csv` and `{slug}_incidents.csv` are validated with relaxed rules (different schema / duplicate match_id allowed). You can leave them as-is or remove them if you only use `{slug}.csv`.
