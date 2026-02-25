# Data retention and what can be recreated

## What we keep

| Location | Content | Retention |
|----------|---------|-----------|
| `data/raw/{season}/{realm}/{competition_slug}/{match_id}/` | Raw scraped files per match (lineups.csv, incidents.csv, statistics, managers, graph) | Keep for as long as you need to reprocess. Raw is the source of truth. |
| `data/index/matches.csv` | Central match index (discovered event IDs, season, competition, round, match_date) | Keep; can be recreated by re-running discovery. |
| `data/index/extraction_progress.csv` | Extraction progress per competition/season | Keep; append-only runs in `extraction_progress_runs.csv`. |
| `data/index/extraction_batch_errors.csv` | Per-match extraction failures | Optional; useful for debugging. |
| `data/index/pipeline_runs.csv` | Pipeline run history | Optional; useful for ops. |
| `data/derived/` | player_appearances, player_incidents, match_scores; players.csv | **Recreatable** from raw + index. Safe to delete and re-run `build_player_appearances.py`. |
| `data/processed/` | All build steps 00–16 (parquet files) | **Recreatable** from derived + raw. Safe to delete and re-run pipeline from derived. |

## What can be recreated

- **Derived**: Run `python src/build_player_appearances.py` (or pipeline step `derived`) with existing `data/raw/` and `data/index/matches.csv`.
- **Processed (00–16)**: Run `python scripts/run_pipeline.py` from step `derived` (or from step `00` if derived is already present).
- **Index**: Run `python src/discover_matches.py <competition> --seasons <seasons>` to repopulate or extend `data/index/matches.csv` (merge behaviour is append/upsert depending on implementation).

## Recommendations

- **Raw**: Retain for all seasons you care about; only delete if you are sure you will never need to re-run the pipeline for that data.
- **Index**: Retain; small size. Re-run discovery when new matches are available.
- **Derived / processed**: Can be recreated on demand; consider keeping at least one full set for production use and optionally archiving or pruning old seasons if disk is a concern.
- **Logs and runs**: `data/logs/`, `data/index/pipeline_runs.csv`, `pipeline_failures.log` — retain for a defined period (e.g. 90 days) then archive or rotate.

## Optional: golden snapshot

After a successful pipeline run you can copy `data/derived/` and `data/processed/` to a timestamped directory (e.g. `data/snapshots/2025-02-21T12-00-00Z/`) for point-in-time rollback or A/B. This is not automated; add a post-run step in your scheduler or run script if needed.

## Known DQ exception

- **15_team_tactical_profiles / team_names_all_in_01**: If step 15 was run with an older step 01, some team names in 15 may not appear in the current 01. Re-run the pipeline from step `01` through `15` (or full pipeline) to sync. The DQ check may report this as WARN with remediation.
