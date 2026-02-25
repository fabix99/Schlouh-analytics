# Derived data (player-level)

Generated from raw match data. Rebuild with:

```bash
python src/build_player_appearances.py
python src/build_player_appearances.py --csv   # also write player_appearances.csv
```

## Files

| File | Description |
|------|-------------|
| **player_appearances.parquet** | One row per player per match. All lineup stats + match context (date, round, opponents). Use for player viz: filter by `player_id` or `player_name`. |
| **player_appearances.csv** | Same as above (optional, created with `--csv`). |
| **player_incidents.parquet** | One row per incident that has a player (goals, cards, etc.). Columns include `match_id`, `player_id`, `player_name`, `incidentType`, `incidentClass`, `time`, `season`, `competition_slug`, `match_date_utc`. |
| **players/** | Per-player export: by default **one file** `{slug}.csv` (e.g. `kylian-mbappe.csv`) with one row per match, all appearance stats + incident counts. Use `--min-games 5` with `--all` to only export players with ≥5 games (saves space). Use `--cleanup-min-games 5` to delete existing files for players with &lt;5 games. Use `--two-files` to get separate `_appearances.csv` and `_incidents.csv`. Created by `python src/export_player.py "Player Name"` or `--all --competition spain-laliga`. |

## player_appearances columns (summary)

- **Identity:** `player_id`, `player_name`, `player_slug`, `player_shortName`, `player_position`, `player_jerseyNumber`, `player_sofascoreId`, `player_dateOfBirthTimestamp`, …
- **Match context:** `match_id`, `season`, `realm`, `competition_slug`, `match_date` (Unix), `match_date_utc` (datetime), `round`, `home_team_name`, `away_team_name`, `team` (player’s team), `side` (home/away).
- **Stats (stat_*):** `stat_minutesPlayed`, `stat_rating`, `stat_goals`, `stat_expectedGoals`, `stat_expectedAssists`, `stat_totalPass`, `stat_accuratePass`, `stat_touches`, `stat_keyPass`, `stat_totalTackle`, `stat_duelWon`, … (all columns from raw lineups.csv).

## Example: plot one player

```python
import pandas as pd
df = pd.read_parquet("data/derived/player_appearances.parquet")
mbappe = df[df["player_name"].str.contains("Mbappé", na=False)]
# or by id: mbappe = df[df["player_id"] == 12345]
mbappe.plot(x="match_date_utc", y="stat_rating", kind="line")
```

## Example: export one player to CSV

```bash
python src/export_player.py "Robert Lewandowski"
# -> data/derived/players/robert-lewandowski.csv  (one file: appearances + incident counts per match)

python src/export_player.py "Robert Lewandowski" --two-files
# -> data/derived/players/robert-lewandowski_appearances.csv
# -> data/derived/players/robert-lewandowski_incidents.csv
```

## Index

**data/index/players.csv** – One row per player: `player_id`, `player_name`, `player_slug`, `player_shortName`, `n_matches`, `first_match_id`, `last_match_id`, `competitions`, `seasons`. Use to resolve a name to `player_id` or to list all players.
