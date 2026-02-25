# Football Visualization Catalog

Standalone scripts to generate test visuals from real player data. Outputs are saved to `viz/output/`.

## Setup

```bash
pip install -r viz/requirements.txt
```

Ensure `data/derived/player_appearances.parquet` exists (run `python src/build_player_appearances.py` first).

## Run All

From project root:

```bash
python viz/scripts/run_all.py
```

## Run Individual Scripts

From project root, e.g.:

```bash
python viz/scripts/01_match_dashboard.py [player_slug] [match_id]
python viz/scripts/04_rolling_form.py [player_slug]
python viz/scripts/12_radar_compare.py [player1_slug] [player2_slug]
```

Default test players: `kylian-mbappe`, `robert-lewandowski`. Default match: `14083729` (El Clasico 2025-10-26).

## Catalog

| ID | Script | Description |
|----|--------|-------------|
| 1.1 | 01_match_dashboard | KPI panel for one match |
| 1.2 | 02_match_card | Match stats vs season average |
| 1.3 | 03_match_radar | Single-match radar vs season |
| 2.1 | 04_rolling_form | Rolling 5-game form (rating, xG, goals) |
| 2.2 | 05_form_score | Recency-weighted momentum |
| 2.3 | 06_consistency | Coefficient of variation (xG, rating) |
| 2.4 | 07_distribution | Histogram of rating and xG |
| 3.1 | 08_radar_profile | Season radar (position-specific) |
| 3.2 | 09_value_breakdown | Pass/dribble/defend/shot value |
| 3.3 | 10_archetype_scatter | xG/90 vs key passes/90 (all players) |
| 3.4 | 11_pass_zones | Own vs opposition half passes |
| 4.1 | 12_radar_compare | Side-by-side radar (2 players) |
| 4.2 | 13_bar_compare | Comparison bar chart |
| 4.3 | 14_matrix_compare | Head-to-head matrix |
| 4.4 | 15_scatter_compare | xG vs xA scatter |
| 5.1 | 16_goal_timeline | Goals and assists per match |
| 5.2 | 17_penalty_profile | Penalty conversion |
| 5.3 | 18_card_risk | Cards per 90, fouls vs cards |
| 6.1 | 19_percentile | Percentiles vs league peers |

Mark keep/drop as you review outputs.
