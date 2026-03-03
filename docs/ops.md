# Operations: scheduling and alerting

## After a matchday (weekly sync)

When new games have been played (e.g. after the weekend):

1. **Discover** (if you added new competitions or seasons):  
   `python src/discover_matches.py <competition> --seasons 2025-26`
2. **Extract** new matches for each competition you care about. Include **player maps** so Scouts heatmaps stay up to date:  
   `python src/extract_batch.py <competition> 2025-26 --extract-player-maps`  
   (Omit `--extract-player-maps` for a faster run if you don’t need heatmaps.)
3. **Pipeline** (rebuilds derived + processed, including heatmap parquet at step 18):  
   `python scripts/run_pipeline.py`

If you only need to backfill heatmaps for matches that already have lineups (e.g. after a one-off run without `--extract-player-maps`):  
`python scripts/run_player_maps_season_all.py --season 2025-26`  
then run the pipeline (or at least step 18).

## Recommended schedule

Run the full pipeline after match days so derived and processed data stay up to date.

- **Cron example (daily at 06:00 UTC):**
  ```cron
  0 6 * * * /path/to/Sofascore-Scrapping/scripts/run_scheduled_pipeline.sh >> /path/to/logs/pipeline.log 2>&1
  ```
- Adjust the hour to match your timezone and when Sofascore data is typically final.

## Wrapper script for cron

Use **`scripts/run_scheduled_pipeline.sh`** so that:

- Working directory and Python path are set correctly.
- Stdout/stderr are logged to `data/logs/` (or `SOFASCORE_LOG_DIR`).
- On failure, an entry is appended to **`data/index/pipeline_failures.log`** (timestamp + last lines of stderr).
- On success, **`data/index/last_successful_run.txt`** is updated with the ISO timestamp.

Run it manually to test:

```bash
./scripts/run_scheduled_pipeline.sh
```

## Failure notification

- **Simple (default):** Failures are appended to `data/index/pipeline_failures.log`. Monitor this file or tail it in your alerting (e.g. cron job that checks exit code and sends email/Slack).
- **Optional:** In `run_scheduled_pipeline.sh` you can add a call to a webhook (e.g. Slack) when `$?` is non-zero; see the script’s comments.

## Success heartbeat

- After a successful run, the script writes the current ISO timestamp to **`data/index/last_successful_run.txt`**.
- You can check data freshness by comparing that timestamp to now (e.g. alert if older than 25 hours).
