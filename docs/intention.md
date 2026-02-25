# Sofascore scraping – intention

## Goal

Obtain structured data from Sofascore to support football analytics at match and player level, at scale.

---

## What we want to capture

### Match level
- Match identity (teams, competition, round, date, venue).
- Score and result.
- Referee, managers, attendance.
- Incidents (goals, cards, substitutions with minute and player references).
- Team-level statistics (possession, xG, shots, corners, fouls, etc.), including by half where available.

### Line-up and players (per match)
- For each player (starters and substitutes): identity (name, id, position, jersey number), profile (nationality, age, height, market value), and full in-match performance (rating, minutes, passes, tackles, duels, shots, etc.).
- Any shot or graph data tied to the match (e.g. shot positions, momentum).

### Player-level visuals and detailed stats
- Per player, for a given match: pass map, dribble map, and defense map (or equivalent visualisations).
- Heatmaps and shot maps where available, in a form suitable for storage or later analysis.

---

## Scale and organisation

- Support scraping **many matches** (multiple leagues, seasons, or custom lists).
- Organise outputs so raw and processed data are clearly separated and easy to find.
- Keep outputs structured and ready for analytics (e.g. tables, consistent identifiers, one place per data type).

---

## Scope: what we plan to cover (and what is API-ready)

**Full scope** is defined in **`config/scope.yaml`**. It includes:

- **European leagues** (e.g. La Liga, Premier League, Serie A, Bundesliga, Ligue 1, Primeira Liga, Pro League, Eredivisie, Süper Lig).
- **Domestic cups and super cups** (FA Cup, Copa del Rey, Coppa Italia, DFB-Pokal, Coupe de France, etc.).
- **UEFA club competitions** (Champions League, Europa League, Conference League, Super Cup).
- **National teams**: World Cup, UEFA Euro, Nations League, continental qualifiers (UEFA, CONMEBOL, CONCACAF, AFC, CAF), Copa América, Africa Cup of Nations, Gold Cup, Asian Cup, friendlies.
- **Leagues and cups outside Europe**: USA (MLS, Open Cup, Leagues Cup), Brazil Série A, Argentina Primera, Saudi Pro League and cups, Copa Libertadores.

To **get data through the Sofascore API**, each competition must have:

1. A **tournament ID** (and, where the API requires it, **season IDs**) so we can call the events endpoint and discover matches.
2. An entry in **`config/competitions.yaml`** with `tournament_id`, `realm` (club or national), and `slug`.

**Current status:** Only the **nine European leagues** listed above have their IDs found and validated in `config/competitions.yaml`. Discovery and extraction are wired only for these. All other items in `config/scope.yaml` (cups, UEFA tournaments, national competitions, USA/Brazil/Argentina/Saudi, etc.) **do not yet have API IDs configured** — their Sofascore tournament (and season) IDs still need to be identified and added to `config/competitions.yaml` before we can discover and scrape their data.

---

## Quality and robustness

- Handle consent, ads, and overlays so that target content is captured and not obscured.
- When the desired content is not fully visible (e.g. below the fold), ensure it is brought into view before capture.
- Prefer capturing only the relevant content (e.g. pitch maps) rather than full-page screens when possible.
