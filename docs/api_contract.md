# Sofascore API response shape (contract)

Minimum expected keys so that discovery and extraction can run. If the API changes and these are missing, discovery or extract will fail or behave incorrectly.

Base URL: `https://api.sofascore.com/api/v1` (or override via `SOFASCORE_API_BASE`).

---

## GET /event/{id}

Used by: `extract_match_lineups.py`, discovery (event identity).

**Required (at least one path):**

- `event` (object) — wrapper; or root is the event.
- `event.tournament` (object) with `slug` (string) or equivalent for identity.
- `event.season` (object) with `id` (number) for season identity.
- `event.startTimestamp` (number) — Unix timestamp (seconds or milliseconds).
- `event.homeTeam` and `event.awayTeam` (objects) with `name` or `shortName` for team names.

**Optional:** `event.round`, `event.status`, etc.

---

## GET /event/{id}/lineups

Used by: `extract_match_lineups.py` (builds lineups CSV).

**Required:**

- Root has `home` and/or `away` (objects), each with:
  - `team` (object) with `name` or `shortName`, and
  - `players` (array of player objects); or
- Root has `homeTeam` / `awayTeam` with `players` or `lineup` (array).

Player objects: at least `id` (or equivalent) for player_id; other stat keys are optional but expected for analytics.

---

## GET /event/{id}/statistics

Used by: `extract_match_lineups.py` (team statistics CSV).

**Required:**

- `statistics` (array). Each element can have `period`, `groups`; each group has `statisticsItems` or `items` with name/home/away (or homeValue/awayValue).

---

## GET /event/{id}/incidents

Used by: `extract_match_lineups.py` (incidents CSV), match score derivation.

**Required:**

- `incidents` (array). Can be empty. Elements are objects; optional keys include `incidentType`, `time`, `player`, `homeScore`, `awayScore`.

---

## GET /event/{id}/managers

**Required:** Root is an object (can be empty). No strict key requirements; saved as JSON.

---

## GET /event/{id}/graph

**Required:** Root is an object (can be empty). No strict key requirements; saved as JSON.

---

## Discovery: GET /unique-tournament/{id}/season/{sid}/events (or tournament variant)

**Required:**

- Response has a list of events (array). Each event has `id`, and ideally `tournament`, `season`, `startTimestamp` for identity checks.

---

If any required shape changes, update this doc and the contract test (`scripts/check_api_contract.py`). The extract and discover code assumes these shapes.
