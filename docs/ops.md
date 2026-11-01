# Operations: scheduling and alerting

## After a matchday (weekly sync)

1. **Discover** (if needed):  
   `python src/discover_matches.py <competition> --seasons 2025-26`
2. **Extract** new matches (skip existing; never wipe raw):  
   `python src/extract_batch.py <competition> 2025-26 --extract-player-maps`
3. **One product refresh:**  
   `bash platform/scripts/run_platform_full.sh`

Heatmap-only backfill (when lineups already exist):  
`python scripts/run_player_maps_season_all.py --season 2025-26`  
then run `run_platform_full.sh` (or at least the maps-related build + warehouse refresh).

## Scheduling

Prefer **Airflow** (see `PLAN.md` Phase 1 / Phase 4) over cron.

Until Airflow is the daily driver, run `run_platform_full.sh` manually after matchdays.

## Success / failure signals

- Warehouse validation: `python platform/scripts/validate_warehouse_full.py`
- Pipeline run metadata under `data/index/` when produced by the refresh scripts
- Sofascore 403 on extract is expected sometimes — do **not** delete data; refresh warehouse from the lake anyway

## Data safety

See the hard rule in `PLAN.md`: never delete `data/raw` / index to “fix” API issues.
