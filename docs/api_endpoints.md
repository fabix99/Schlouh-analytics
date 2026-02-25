# Sofascore API endpoints (from HAR)

Base: `https://api.sofascore.com/api/v1` or `https://www.sofascore.com/api/v1` (same). Use browser-like headers (User-Agent, Referer).

## Extracted by `src/extract_match_lineups.py`

| Endpoint | Output | Description |
|----------|--------|-------------|
| `GET /event/{id}` | (used for team names) | Match info, teams, venue, round, etc. |
| `GET /event/{id}/lineups` | `lineups_{id}.csv` | One row per player, all stats |
| `GET /event/{id}/statistics` | `team_statistics_{id}.csv` | Team stats by period (possession, xG, shots, etc.) |
| `GET /event/{id}/incidents` | `incidents_{id}.csv` | Goals, cards, substitutions |
| `GET /event/{id}/managers` | `managers_{id}.json` | Manager info |
| `GET /event/{id}/graph` | `graph_{id}.json` | Momentum / graph data |

## Available in HAR but not yet extracted

- **Per player (need player IDs from lineups):**
  - `GET /event/{id}/player/{playerId}/statistics` – single-player stats (overlap with lineups)
  - `GET /event/{id}/player/{playerId}/heatmap` – heatmap coordinates `{x,y}`
  - `GET /event/{id}/player/{playerId}/rating-breakdown` – rating breakdown
  - `GET /event/{id}/shotmap/player/{playerId}` – shot positions
- **Match-level:**
  - `GET /event/{id}/best-players/summary`
  - `GET /event/{id}/ai-insights-postmatch/en`
  - `GET /event/{id}/pregame-form`
  - `GET /event/{id}/h2h` – head to head
  - `GET /event/{id}/graph/win-probability`
  - `GET /event/{id}/highlights`, `votes`, `odds/1/featured`, `odds/1/all`, etc.
- **Discovery:**
  - `GET /sport/football/scheduled-events/{date}` – matches by date
- **Team:**
  - `GET /team/{teamId}/team-statistics/seasons`
  - `GET /team/{teamId}/unique-tournament/{tid}/season/{sid}/statistics/overall`

To add heatmap/shotmap per player, loop over `player_id` from `lineups_{id}.csv` and call the endpoints above; save to e.g. `data/raw/heatmap_{id}_{playerId}.json`.

## 403 challenge workaround

Sofascore sometimes returns `403` with `{"error": {"code": 403, "reason": "challenge"}}`, which blocks automated discovery.

- **Retries:** `discover_matches.py` retries 403 with backoff (5s, 15s, 45s) and then exits with a clear message.
- **Different network:** Try again later or from another network/VPN.
- **Browser season IDs:** Run `python src/fetch_seasons_browser.py 42 --out config/germany_bundesliga_seasons.json` (after `pip install playwright && playwright install chromium`). If the browser gets 200, discovery will use the cached IDs and skip the `/seasons` call. If the browser also gets 403, use a different network or manually copy season IDs from DevTools and create `config/germany_bundesliga_seasons.json`.
