# Chart data export (Python → JSON)

Python computes metrics and writes **structured JSON** to `web/public/data/`, which the web app serves.

## Layout

- `scripts/` – export scripts (use `viz.data_utils`); they write to `web/public/data/`:
  - `player/{slug}/` – per-player (e.g. `form.json`, `percentiles.json`)
  - `compare/` – comparison (e.g. `mbappe_vs_lewandowski_radar.json`)
  - `league/` – league-level (e.g. archetype)
  - `ranking/` – rankings if generated

## Data contracts

See `web/src/types/` for TypeScript types. Python output must match those shapes.

## Regenerate

```bash
python export/scripts/export_form.py
# or
python export/scripts/export_all.py
```
