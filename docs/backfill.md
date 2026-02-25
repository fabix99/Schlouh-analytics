# Backfill and re-run procedures

## Re-run pipeline from a given step

To reprocess from derived data through validation:

```bash
python scripts/run_pipeline.py --from-step derived --to-step validate
```

To only rebuild processed steps 00–02 and then run DQ + validate:

```bash
python scripts/run_pipeline.py --from-step 00 --to-step 02
python scripts/run_pipeline.py --from-step dq --to-step validate
```

Or in one go (steps 00 through validate):

```bash
python scripts/run_pipeline.py --from-step 00 --to-step validate
```

## Re-extract a competition/season

If raw data was lost or you need to re-fetch (e.g. after API fixes):

1. Ensure the match index includes the competition/season:
   ```bash
   python src/discover_matches.py <competition> --seasons <season>
   ```
2. Re-extract with force to overwrite existing raw files:
   ```bash
   python src/extract_batch.py <competition> <season> --force
   ```
3. Run the full pipeline so derived and processed are rebuilt:
   ```bash
   python scripts/run_pipeline.py
   ```

Example:

```bash
python src/discover_matches.py spain-laliga --seasons 2025-26
python src/extract_batch.py spain-laliga 2025-26 --force
python scripts/run_pipeline.py
```

## Re-run from “date X” (conceptual)

Sofascore discovery is per competition/season, not by date. To effectively “re-run from date X”:

1. Re-run discovery for the competitions/seasons you care about (so the index has all events).
2. Run extract **without** `--force` so only matches that don’t yet have `lineups.csv` are fetched (incremental).
3. Run the pipeline so new matches are included in derived and processed.

If you want to reprocess everything (e.g. after a code change that affects derived or processed):

1. Option A: Delete `data/derived/*` and `data/processed/*`, then run `python scripts/run_pipeline.py`.
2. Option B: Keep raw and index; run `python scripts/run_pipeline.py --rebuild-all` (runs from derived through validate).

## Sync team names (15 vs 01) DQ

If DQ reports that some team names in `15_team_tactical_profiles` are not in `01_team_season_stats`, run the pipeline from step 01 through 15 so both are built from the same source:

```bash
python scripts/run_pipeline.py --from-step 01 --to-step 15
```

Then re-run DQ and validate:

```bash
python scripts/run_pipeline.py --from-step dq --to-step validate
```

## Match index sync (all_matches_csv_ids_present)

If validation or DQ fails because processed artifacts reference match IDs not in the index (or the opposite), sync the index and then rebuild from step 00:

```bash
python scripts/run_pipeline.py --from-step 00 --to-step 02
python scripts/run_pipeline.py
```

See `docs/fixing_validation_failures.md` for more detail.
