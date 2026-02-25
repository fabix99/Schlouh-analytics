# Operations: scheduling and alerting

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
