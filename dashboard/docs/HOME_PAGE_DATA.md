# Home Page — How the data is calculated

This doc explains where each number on the **Home** page comes from and how it is computed. If something looks wrong, check the data source and grain below.

---

## Data sources (two different ones)

The Home page uses **two separate data sources**:

| Section | Source | File / table |
|--------|--------|----------------|
| **KPIs** (Players, Leagues, Seasons, Appearances, Goals) | Enriched player-season stats | `data/processed/03_player_season_stats.parquet` (+ team lookup from `data/derived/player_appearances.parquet`) |
| **Position breakdown** | Same enriched stats | Same as KPIs |
| **Top scorers** | Same enriched stats | Same as KPIs |
| **Data Coverage** (left column) | Extraction progress | `data/index/extraction_progress.csv` |
| **Season Availability** (grid) | Extraction progress | Same CSV |

So: the **five KPI numbers** and the **right column** (positions, top scorers) come from the **stats pipeline** (player_appearances → 03_player_season_stats). The **Data Coverage** cards and the **Season Availability** grid come from **extraction_progress.csv** (how many matches were extracted per competition/season). Those two can disagree if extraction was run for more/fewer matches than were actually used to build the stats.

---

## Grain of the stats DataFrame

`03_player_season_stats` is built by **scripts/build/03_build_player_season_stats.py** and has:

- **One row per** `(player_id, season, competition_slug)`.
- So the same player can have **several rows** in one season (e.g. Premier League + Champions League).

So:

- **Players** = unique `player_id` in that DataFrame → **distinct players** (no double-count).
- **Leagues** = unique `competition_slug` → **distinct competitions**.
- **Seasons** = unique `season` → **distinct seasons**.
- **Appearances** = **sum of** `appearances` over all rows.  
  Each row’s `appearances` = number of **matches** that player played in that (season, competition). So the total is **total player-match appearances** (one player in one match = 1 appearance). It is **not** “number of matches” and can be much larger than match count.
- **Goals logged** = **sum of** `goals` over all rows.  
  Each row’s `goals` = goals by that player in that (season, competition). So the total is **total goals** in the dataset.

---

## Position breakdown (right column)

- **Before (bug):** Counted **unique `player_id` per `player_position`** on the full DataFrame. So if a player had different positions in different rows (e.g. “M” in one comp, “F” in another), they were counted in **both** positions and the four position counts could add up to **more** than total players.
- **After (fix):** We take **one row per player** (the row where that player has the most **total_minutes**), then count by `player_position`. So each player is assigned a single “primary” position and the four counts add up to **total unique players** (ignoring any positions outside F/M/D/G).

---

## Top scorers

- **All-time top 5:** `df.groupby("player_name")["goals"].sum().nlargest(5)`.
- So we **sum goals** across all rows (all seasons and competitions) per player name. That is **total goals in the dataset** for that player.

---

## Data Coverage (left column)

- Built from **extraction_progress**: for each `competition_slug`, we show:
  - number of **seasons** with `extracted > 0`,
  - **matches** = sum of `extracted` (number of matches extracted per competition/season, then summed per competition).
- This is **independent** of the stats parquet. If extraction says “10,000 matches” but the stats file was built from a subset of matches, the KPI “Appearances” will not match the coverage “matches” number (and that’s expected: one is player-appearances, the other is match count).

---

## What to check if numbers look wrong

1. **KPIs vs expectations**  
   - Confirm what you expect: “Players” = distinct players; “Appearances” = total player-match appearances (not match count).  
   - Rebuild `03_player_season_stats` from current `player_appearances` if the parquet is stale.

2. **Position breakdown**  
   - After the fix, F + M + D + G should equal total players (only if every player has position in {F,M,D,G}).  
   - If you still see double-counting, check that the app uses the “one row per player (max total_minutes)” logic.

3. **Coverage vs stats**  
   - Data Coverage and Season Availability come from **extraction_progress.csv**, not from the stats parquet.  
   - For consistency, either: align extraction with what the stats pipeline uses, or add a note on Home that “Coverage = extracted matches; KPIs = from player-season stats.”

4. **Rebuild pipeline**  
   - To refresh everything: run the pipeline that builds `player_appearances` and then `03_build_player_season_stats.py`.  
   - Home will then reflect the latest `03_player_season_stats.parquet` and (for coverage) the latest `extraction_progress.csv`.
