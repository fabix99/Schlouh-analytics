# Schlouh Charts (web)

React + Vite app for world-class chart visuals. Data is exported from Python to `public/data/`.

## Setup

```bash
cd web
npm install
```

## Data

From project root, export **all** chart data (writes to `web/public/data`):

```bash
python export/scripts/export_all.py
# optional: python export/scripts/export_all.py kylian-mbappe robert-lewandowski
```

Or export only form: `python export/scripts/export_form.py`

## Dev

```bash
npm run dev
```

Open the URL shown (e.g. http://localhost:5173). You should see **all charts** in a grid: Form over time, Momentum, Consistency, Distribution, Value breakdown, Radar profile, Goal timeline, Pass zones, Percentiles, and Compare bar (Mbappé vs Lewandowski).

## Build

```bash
npm run build
npm run preview   # optional: preview prod build
```

## Structure

- `src/design/tokens.css` — Schlouh design tokens (dark + gold)
- `src/types/` — Data contracts (TypeScript)
- `src/components/charts/` — Chart components (e.g. FormOverTime)
- `public/data/` — JSON from Python (served as static files)
