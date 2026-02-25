"""AI Scout — ask questions about football data using the Groq API (RAG over football.db)."""

import sys
import pathlib
import re
import sqlite3
from typing import Optional

_project_root = pathlib.Path(__file__).parent.parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

import streamlit as st

from dashboard.utils.sidebar import render_sidebar
from dashboard.utils.football_db import ensure_football_db, get_db_path

# ---------------------------------------------------------------------------
# Page config & sidebar
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="AI Scout | Schlouh Scouting",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="expanded",
)
render_sidebar()

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
GROQ_MODEL = "llama-3.3-70b-versatile"
MAX_CONTEXT_ROWS = 40
MAX_CONTEXT_CHARS = 6000  # ~1500 tokens; room for schema/coverage + RAG under Groq limit
SYSTEM_PROMPT = """You are a football data assistant. Answer ONLY from the database context below.

Data available: player season stats (goals, assists, avg_rating, minutes, appearances, competition, season, position, xG/xA per 90), team season stats (team_name, matches, xG for/against), and match results (home/away teams, scores). When asked about "team aspects" or "team data", describe what is in the context.

Rules:
- Use ONLY the "Database context". No external knowledge.
- When the context includes a "Top N by X" or "Top N by [stat]" list, use that list to answer "who has the most X" or "top assister/goalscorer"; do not pick a random row from elsewhere in the context.
- If the context does not contain the answer, reply with exactly: "I don't have that data in my records."
- For "what tables", "what data do you have", "what can I ask", "structure", "schema", or "limitations": describe the tables and columns from the context. Say we do NOT have: red/yellow cards, possession, shot stats, managers, coaches, injury/availability, transfers, market values.
- Give one clear, short answer. For "who has the most X" or "best Y", name the top player(s) and the number; do not list many examples unless asked.
- Round all numbers to 1 or 2 decimal places (e.g. 7.17 not 7.166666666666667).
- Do not repeat the same point; avoid long lists unless the question asks for a list.
"""


def get_connection():
    """Return a read-only SQLite connection to football.db. Uses only SELECT."""
    db_path = ensure_football_db()
    # Open in read-only mode so no writes are possible
    uri = f"file:{db_path}?mode=ro"
    return sqlite3.connect(uri, uri=True)


def extract_search_terms(question: str) -> list[str]:
    """Extract potential player/team keywords from the user question (words ≥ 2 chars)."""
    # Normalize: letters, digits, keep single spaces
    text = re.sub(r"[^\w\s]", " ", question or "")
    words = [w.strip() for w in text.split() if len(w.strip()) >= 2]
    return list(dict.fromkeys(words))  # unique, order preserved


def fetch_context_read_only(conn: sqlite3.Connection, search_terms: list[str]) -> str:
    """
    Run read-only SELECT queries to fetch rows matching search terms.
    Only SELECT is used; no INSERT/UPDATE/DELETE.
    """
    if not search_terms:
        # No keywords: return a small sample so the model knows the schema
        parts = []
        try:
            cur = conn.execute("SELECT * FROM player_season_stats LIMIT 5")
            rows = cur.fetchall()
            cols = [d[0] for d in cur.description]
            if rows:
                parts.append("player_season_stats (sample): " + str(dict(zip(cols, rows[0]))))
        except sqlite3.OperationalError:
            pass
        try:
            cur = conn.execute("SELECT * FROM team_season_stats LIMIT 3")
            rows = cur.fetchall()
            cols = [d[0] for d in cur.description]
            if rows:
                parts.append("team_season_stats (sample): " + str(dict(zip(cols, rows[0]))))
        except sqlite3.OperationalError:
            pass
        return "\n".join(parts) if parts else "No tables available."

    all_rows = []
    seen = set()
    row_limit_per_query = max(20, MAX_CONTEXT_ROWS // (len(search_terms) or 1))

    tables_columns = [
        ("player_season_stats", ["player_name"]),
        ("players_index", ["player_name", "player_shortName"]),
        ("team_season_stats", ["team_name"]),
        ("match_summary", ["home_team_name", "away_team_name"]),
        ("player_team_lookup", ["team"]),
    ]

    for table, columns in tables_columns:
        try:
            for term in search_terms:
                pattern = f"%{term}%"
                cond = " OR ".join(f"CAST({c} AS TEXT) LIKE ?" for c in columns)
                params = [pattern] * len(columns)
                sql = f"SELECT * FROM {table} WHERE {cond} LIMIT {row_limit_per_query}"
                cur = conn.execute(sql, params)
                rows = cur.fetchall()
                col_names = [d[0] for d in cur.description]
                for row in rows:
                    key = (table, tuple(row))
                    if key not in seen and len(all_rows) < MAX_CONTEXT_ROWS:
                        seen.add(key)
                        all_rows.append((table, col_names, row))
        except sqlite3.OperationalError:
            continue

    if not all_rows:
        return "No matching rows found for the given keywords."

    lines = []
    for table, col_names, row in all_rows:
        d = dict(zip(col_names, row))
        lines.append(f"{table}: {d}")
    raw_context = "\n".join(lines)
    # Cap total context size to stay under Groq token limit (~4 chars/token)
    if len(raw_context) > MAX_CONTEXT_CHARS:
        raw_context = raw_context[:MAX_CONTEXT_CHARS] + "\n...[context truncated]"
    # #region agent log
    _log_path = pathlib.Path(__file__).parent.parent.parent / ".cursor" / "debug-c8fddf.log"
    try:
        import json as _json, time as _time
        with open(_log_path, "a") as _f:
            _f.write(_json.dumps({"sessionId": "c8fddf", "timestamp": int(_time.time() * 1000), "location": "AI_Scout:context", "message": "RAG context size", "data": {"row_count": len(all_rows), "char_count": len(raw_context)}, "hypothesisId": "H1"}) + "\n")
    except Exception:
        pass
    # #endregion
    return raw_context


def _normalize_season_for_db(season_str: str) -> list[str]:
    """Return possible DB season values, e.g. '2025/2026' -> ['2025/26', '2025-26']."""
    m = re.search(r"20(\d{2})[/\-]20?(\d{2})", (season_str or "").strip())
    if not m:
        return []
    y1, y2 = m.group(1), m.group(2)
    return [f"20{y1}/{y2}", f"20{y1}-{y2}"]


def _fetch_top_aggregate(
    conn: sqlite3.Connection,
    stat_column: str,
    label: str,
    limit: int = 10,
    season_filter: Optional[str] = None,
) -> str:
    """Read-only: top players by summed stat (goals or assists). Returns formatted context."""
    try:
        if season_filter:
            cur = conn.execute(
                f"""SELECT player_name, season, competition_slug,
                           SUM({stat_column}) as total
                    FROM player_season_stats
                    WHERE season = ?
                    GROUP BY player_id
                    ORDER BY total DESC
                    LIMIT ?""",
                (season_filter, limit),
            )
        else:
            cur = conn.execute(
                f"""SELECT player_name, SUM({stat_column}) as total
                    FROM player_season_stats
                    GROUP BY player_id
                    ORDER BY total DESC
                    LIMIT ?""",
                (limit,),
            )
        rows = cur.fetchall()
        if not rows:
            return ""
        col_names = [d[0] for d in cur.description]
        lines = [f"Top {limit} by {label}:"]
        for r in rows:
            d = dict(zip(col_names, r))
            total = d.get("total")
            if total is not None:
                d["total"] = round(float(total), 1) if isinstance(total, (int, float)) else total
            lines.append(f"  {d}")
        return "\n".join(lines)
    except sqlite3.OperationalError:
        return ""


def _fetch_top_rating(conn: sqlite3.Connection, limit: int = 10) -> str:
    """Read-only: top player-seasons by avg_rating. Rounded numbers."""
    for sql in (
        """SELECT player_name, season, competition_slug,
                  ROUND(avg_rating, 2) as avg_rating, total_minutes
           FROM player_season_stats
           WHERE total_minutes >= 450
           ORDER BY avg_rating DESC
           LIMIT ?""",
        """SELECT player_name, season, competition_slug,
                  ROUND(avg_rating, 2) as avg_rating
           FROM player_season_stats
           ORDER BY avg_rating DESC
           LIMIT ?""",
    ):
        try:
            cur = conn.execute(sql, (limit,))
            rows = cur.fetchall()
            if not rows:
                continue
            col_names = [d[0] for d in cur.description]
            lines = [f"Top {limit} by average rating:"]
            for r in rows:
                lines.append(f"  {dict(zip(col_names, r))}")
            return "\n".join(lines)
        except sqlite3.OperationalError:
            continue
    return ""


# League display name (lowercase) -> competition_slug for RAG
_LEAGUE_TO_SLUG = {
    "premier league": "england-premier-league",
    "la liga": "spain-laliga",
    "laliga": "spain-laliga",
    "serie a": "italy-serie-a",
    "bundesliga": "germany-bundesliga",
    "ligue 1": "france-ligue-1",
    "champions league": "uefa-champions-league",
}


def _detect_league_slug(question: str) -> Optional[str]:
    """Return competition_slug if the question mentions a known league name."""
    q = (question or "").lower()
    for name, slug in _LEAGUE_TO_SLUG.items():
        if name in q:
            return slug
    return None


def _fetch_top_by_competition(
    conn: sqlite3.Connection,
    competition_slug: str,
    stat_column: str,
    label: str,
    limit: int = 10,
    season_filter: Optional[str] = None,
) -> str:
    """Read-only: top players by stat in a specific competition (aggregated by player across seasons)."""
    try:
        if season_filter:
            cur = conn.execute(
                f"""SELECT player_name, season, {stat_column}
                   FROM player_season_stats
                   WHERE competition_slug = ? AND season = ?
                   ORDER BY {stat_column} DESC
                   LIMIT ?""",
                (competition_slug, season_filter, limit),
            )
        else:
            cur = conn.execute(
                f"""SELECT player_name, SUM({stat_column}) as total
                   FROM player_season_stats
                   WHERE competition_slug = ?
                   GROUP BY player_id
                   ORDER BY total DESC
                   LIMIT ?""",
                (competition_slug, limit),
            )
        rows = cur.fetchall()
        if not rows:
            return ""
        col_names = [d[0] for d in cur.description]
        lines = [f"Top {limit} by {label} in this competition ({competition_slug}):"]
        for r in rows:
            lines.append(f"  {dict(zip(col_names, r))}")
        return "\n".join(lines)
    except sqlite3.OperationalError:
        return ""


def _fetch_top_rating_by_competition(conn: sqlite3.Connection, competition_slug: str, limit: int = 10) -> str:
    """Read-only: top players by avg_rating in a specific competition (min 450 min)."""
    try:
        cur = conn.execute(
            """SELECT player_name, season, ROUND(avg_rating, 2) as avg_rating, total_minutes
               FROM player_season_stats
               WHERE competition_slug = ? AND total_minutes >= 450
               ORDER BY avg_rating DESC
               LIMIT ?""",
            (competition_slug, limit),
        )
        rows = cur.fetchall()
        if not rows:
            cur = conn.execute(
                """SELECT player_name, season, ROUND(avg_rating, 2) as avg_rating
                   FROM player_season_stats
                   WHERE competition_slug = ?
                   ORDER BY avg_rating DESC
                   LIMIT ?""",
                (competition_slug, limit),
            )
            rows = cur.fetchall()
        if not rows:
            return ""
        col_names = [d[0] for d in cur.description]
        lines = [f"Top {limit} by rating in this competition ({competition_slug}):"]
        for r in rows:
            lines.append(f"  {dict(zip(col_names, r))}")
        return "\n".join(lines)
    except sqlite3.OperationalError:
        return ""


def _fetch_team_data_summary(conn: sqlite3.Connection) -> str:
    """Read-only: short description + sample so the model can say we have team data."""
    parts = [
        "Team data available: team_season_stats (team_name, season, competition_slug, matches_total, xg_for_total, xg_against_total) and match_summary (home_team_name, away_team_name, home_score, away_score, match_date_utc). Use this when asked about 'team aspects' or 'team data'."
    ]
    try:
        cur = conn.execute(
            "SELECT team_name, season, competition_slug, matches_total FROM team_season_stats LIMIT 5"
        )
        rows = cur.fetchall()
        cols = [d[0] for d in cur.description]
        if rows:
            parts.append("Sample team_season_stats: " + "; ".join(str(dict(zip(cols, r))) for r in rows))
    except sqlite3.OperationalError:
        pass
    return "\n".join(parts)


def _fetch_schema_context(conn: sqlite3.Connection) -> str:
    """Read-only: table names and column lists so the model can describe what data we have."""
    parts = ["Schema (tables and columns) in the database:"]
    for table in ("player_season_stats", "team_season_stats", "match_summary", "players_index", "player_team_lookup"):
        try:
            cur = conn.execute(f"SELECT * FROM {table} LIMIT 0")
            cols = [d[0] for d in cur.description]
            parts.append(f"  {table}: {', '.join(cols)}")
        except sqlite3.OperationalError:
            pass
    return "\n".join(parts)


def _fetch_coverage_context(conn: sqlite3.Connection) -> str:
    """Read-only: distinct competitions, seasons, and counts for 'which leagues', 'how many' questions."""
    parts = []
    try:
        cur = conn.execute(
            "SELECT DISTINCT competition_slug FROM player_season_stats ORDER BY competition_slug"
        )
        comps = [r[0] for r in cur.fetchall() if r[0]]
        if comps:
            parts.append("Competitions in database: " + ", ".join(comps[:30]) + ("..." if len(comps) > 30 else ""))
    except sqlite3.OperationalError:
        pass
    try:
        cur = conn.execute(
            "SELECT DISTINCT season FROM player_season_stats ORDER BY season DESC"
        )
        seasons = [r[0] for r in cur.fetchall() if r[0]]
        if seasons:
            parts.append("Seasons: " + ", ".join(seasons[:15]) + ("..." if len(seasons) > 15 else ""))
    except sqlite3.OperationalError:
        pass
    try:
        cur = conn.execute("SELECT COUNT(*) FROM player_season_stats")
        parts.append("Total player-season rows: " + str(cur.fetchone()[0]))
    except sqlite3.OperationalError:
        pass
    try:
        cur = conn.execute("SELECT COUNT(*) FROM match_summary")
        parts.append("Total matches: " + str(cur.fetchone()[0]))
    except sqlite3.OperationalError:
        pass
    try:
        cur = conn.execute("SELECT COUNT(DISTINCT team_name) FROM team_season_stats")
        parts.append("Distinct teams: " + str(cur.fetchone()[0]))
    except sqlite3.OperationalError:
        pass
    return "\n".join(parts) if parts else ""


def _fetch_top_by_position(conn: sqlite3.Connection, position_substr: str, limit: int = 10) -> str:
    """Read-only: top players by rating for a position (e.g. forward, goalkeeper)."""
    try:
        cur = conn.execute(
            """SELECT player_name, season, competition_slug, ROUND(avg_rating, 2) as avg_rating, total_minutes
               FROM player_season_stats
               WHERE LOWER(CAST(player_position AS TEXT)) LIKE ?
               AND total_minutes >= 450
               ORDER BY avg_rating DESC
               LIMIT ?""",
            (f"%{position_substr}%", limit),
        )
        rows = cur.fetchall()
        if not rows:
            cur = conn.execute(
                """SELECT player_name, season, competition_slug, ROUND(avg_rating, 2) as avg_rating
                   FROM player_season_stats
                   WHERE LOWER(CAST(player_position AS TEXT)) LIKE ?
                   ORDER BY avg_rating DESC
                   LIMIT ?""",
                (f"%{position_substr}%", limit),
            )
            rows = cur.fetchall()
        if not rows:
            return ""
        cols = [d[0] for d in cur.description]
        lines = [f"Top {limit} by rating (position like '{position_substr}'):"]
        for r in rows:
            lines.append(f"  {dict(zip(cols, r))}")
        return "\n".join(lines)
    except sqlite3.OperationalError:
        return ""


def _fetch_top_xg_xa(conn: sqlite3.Connection, limit: int = 10) -> str:
    """Read-only: top by expectedGoals_per90 and expectedAssists_per90 (non-null)."""
    parts = []
    for col, label in [("expectedGoals_per90", "xG per 90"), ("expectedAssists_per90", "xA per 90")]:
        try:
            cur = conn.execute(
                f"""SELECT player_name, season, competition_slug, ROUND({col}, 2) as val
                   FROM player_season_stats
                   WHERE {col} IS NOT NULL AND total_minutes >= 450
                   ORDER BY {col} DESC
                   LIMIT ?""",
                (limit,),
            )
            rows = cur.fetchall()
            if rows:
                parts.append(f"Top {limit} by {label}: " + "; ".join(f"{r[0]} ({r[3]})" for r in rows))
        except sqlite3.OperationalError:
            pass
    return "\n".join(parts) if parts else ""


def _fetch_top_minutes_appearances(conn: sqlite3.Connection, limit: int = 10) -> str:
    """Read-only: top by total_minutes or appearances."""
    parts = []
    for col, label in [("total_minutes", "minutes"), ("appearances", "appearances")]:
        try:
            cur = conn.execute(
                f"""SELECT player_name, season, competition_slug, {col}
                   FROM player_season_stats
                   ORDER BY {col} DESC
                   LIMIT ?""",
                (limit,),
            )
            rows = cur.fetchall()
            if rows:
                col_names = [d[0] for d in cur.description]
                parts.append(f"Top {limit} by {label}: " + str([dict(zip(col_names, r)) for r in rows]))
        except sqlite3.OperationalError:
            pass
    return "\n".join(parts) if parts else ""


def _asks_about_current_season(question: str) -> bool:
    """True if the question refers to current/latest/this season."""
    q = (question or "").lower()
    return any(
        phrase in q
        for phrase in (
            "current season",
            "this season",
            "latest season",
            "this year",
            "right now",
        )
    )


def _fetch_latest_season_context(conn: sqlite3.Connection) -> str:
    """Return a short context block: latest season label + top goalscorers for that season (read-only)."""
    parts = []
    try:
        cur = conn.execute(
            "SELECT season FROM player_season_stats ORDER BY season DESC LIMIT 1"
        )
        row = cur.fetchone()
        if row:
            latest_season = row[0]
            parts.append(
                f"Data scope: The latest season in the database is '{latest_season}'. "
                "When the user asks for 'current season', 'this season', or 'right now', use this season."
            )
            cur = conn.execute(
                """SELECT player_name, season, competition_slug, goals, appearances
                   FROM player_season_stats
                   WHERE season = ?
                   ORDER BY goals DESC
                   LIMIT 15""",
                (latest_season,),
            )
            rows = cur.fetchall()
            col_names = [d[0] for d in cur.description]
            if rows:
                parts.append(f"Top goalscorers in {latest_season}:")
                for r in rows:
                    parts.append(f"  {dict(zip(col_names, r))}")
    except sqlite3.OperationalError:
        pass
    return "\n".join(parts) if parts else ""


def _asks_schema_or_discovery(question: str) -> bool:
    """True if the question is about what data/tables/schema we have."""
    q = (question or "").lower()
    return any(
        phrase in q
        for phrase in (
            "what table", "what data", "what can i ask", "what can you", "what questions",
            "structure", "schema", "limitation", "competition_slug", "meaning",
            "types of data", "do you have data on", "list all competition",
        )
    )


def _build_priority_context(conn: sqlite3.Connection, question: str) -> str:
    """Build context blocks for clear intents: top N by stat, team data, specific season. Read-only."""
    q = (question or "").lower()
    parts = []

    # Schema / discovery: always add schema + coverage so we can answer "what data", "which leagues"
    if _asks_schema_or_discovery(question):
        schema_block = _fetch_schema_context(conn)
        if schema_block:
            parts.append(schema_block)
        coverage = _fetch_coverage_context(conn)
        if coverage:
            parts.append(coverage)

    # Leagues / competitions / seasons
    if "league" in q or "competition" in q or "season" in q:
        if "which" in q or "what" in q or "list" in q or "have" in q:
            cov = _fetch_coverage_context(conn)
            if cov and cov not in "\n\n".join(parts):
                parts.append(cov)

    # How many matches / players
    if ("how many" in q and ("match" in q or "player" in q)) or "most matches" in q:
        cov = _fetch_coverage_context(conn)
        if cov:
            parts.append(cov)

    # Specific season (e.g. 2023/24, 2024/25, 2025/2026) — try both / and - formats
    season_variants = _normalize_season_for_db(question)
    for season_val in season_variants[:2]:
        try:
            cur = conn.execute(
                "SELECT 1 FROM player_season_stats WHERE season = ? LIMIT 1", (season_val,)
            )
            if cur.fetchone():
                top_goals = _fetch_top_aggregate(conn, "goals", "goals", limit=10, season_filter=season_val)
                if top_goals:
                    parts.append(f"Season {season_val} (requested as 2023/24 etc.):\n{top_goals}")
                if "assist" in q:
                    top_assists = _fetch_top_aggregate(conn, "assists", "assists", limit=10, season_filter=season_val)
                    if top_assists:
                        parts.append(top_assists)
                break
        except sqlite3.OperationalError:
            pass

    # League-scoped: when question mentions Premier League, La Liga, etc., add top stats for that league
    league_slug = _detect_league_slug(question)
    if league_slug:
        if ("goal" in q and ("most" in q or "top" in q)) or "goalscorer" in q or "striker" in q:
            block = _fetch_top_by_competition(conn, league_slug, "goals", "goals", limit=10)
            if block:
                parts.append(block)
        if "assist" in q and ("most" in q or "top" in q):
            block = _fetch_top_by_competition(conn, league_slug, "assists", "assists", limit=10)
            if block:
                parts.append(block)
        if "rating" in q or "rated" in q or "best" in q:
            block = _fetch_top_rating_by_competition(conn, league_slug, limit=10)
            if block:
                parts.append(block)

    # "Most assists" / "top assists" (global)
    if "assist" in q and ("most" in q or "top" in q):
        block = _fetch_top_aggregate(conn, "assists", "assists", limit=10)
        if block:
            parts.append(block)

    # "Most goals" / "top goals" / "goalscorer" (global)
    if ("goal" in q and ("most" in q or "top" in q)) or "goalscorer" in q or "striker" in q:
        block = _fetch_top_aggregate(conn, "goals", "goals", limit=10)
        if block:
            parts.append(block)

    # "Best rating" / "highest rating" / "average rating"
    if "rating" in q and ("best" in q or "highest" in q or "top" in q or "average" in q):
        block = _fetch_top_rating(conn, limit=10)
        if block:
            parts.append(block)

    # Position-specific: forwards, strikers, goalkeepers, defenders, midfielders
    if "forward" in q or "striker" in q or ("best" in q and "perform" in q):
        for pos in ("forward", "striker", "attacker", "attacking"):
            block = _fetch_top_by_position(conn, pos, limit=10)
            if block:
                parts.append(block)
                break
    if "goalkeeper" in q or "keeper" in q:
        block = _fetch_top_by_position(conn, "goalkeeper", limit=10)
        if block:
            parts.append(block)
    if "defender" in q:
        block = _fetch_top_by_position(conn, "defender", limit=10)
        if block:
            parts.append(block)
    if "midfielder" in q:
        block = _fetch_top_by_position(conn, "midfielder", limit=10)
        if block:
            parts.append(block)

    # xG / xA / expected goals or assists
    if "xg" in q or "xa" in q or "expected" in q:
        block = _fetch_top_xg_xa(conn, limit=10)
        if block:
            parts.append(block)

    # Minutes / appearances
    if "minute" in q and ("most" in q or "top" in q):
        block = _fetch_top_minutes_appearances(conn, limit=10)
        if block:
            parts.append(block)
    if "appearance" in q and ("most" in q or "top" in q or "at least" in q):
        block = _fetch_top_minutes_appearances(conn, limit=10)
        if block:
            parts.append(block)

    # "Team aspects" / "team data" / "team xG"
    if "team" in q and ("aspect" in q or "data" in q or "info" in q or "stat" in q or "xg" in q):
        block = _fetch_team_data_summary(conn)
        if block:
            parts.append(block)

    return "\n\n".join(parts) if parts else ""


def fetch_context(conn: sqlite3.Connection, question: str) -> str:
    """RAG: get context string for the user question using read-only SELECTs."""
    priority = _build_priority_context(conn, question)
    terms = extract_search_terms(question)
    base = fetch_context_read_only(conn, terms)

    if priority:
        base = priority + "\n\n" + base

    # When no specific keywords, add coverage (leagues, seasons, counts) so we can answer generic questions
    if not terms and "competition" not in base and "Season" not in base:
        coverage = _fetch_coverage_context(conn)
        if coverage:
            base = coverage + "\n\n" + base

    if _asks_about_current_season(question):
        latest_block = _fetch_latest_season_context(conn)
        if latest_block:
            base = latest_block + "\n\n" + base

    if len(base) > MAX_CONTEXT_CHARS:
        base = base[:MAX_CONTEXT_CHARS] + "\n...[context truncated]"
    return base


def ask_groq(question: str, context: str, api_key: str) -> str:
    """Send question + context to Groq (llama-3.3-70b-versatile), temperature=0."""
    try:
        from groq import Groq
    except ImportError:
        return "Error: Install the groq package: pip install groq"

    user_content = f"""Database context:
{context}

User question: {question}"""

    try:
        client = Groq(api_key=api_key)
        response = client.chat.completions.create(
            model=GROQ_MODEL,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_content},
            ],
            temperature=0.0,
        )
        return response.choices[0].message.content or "I don't have that data in my records."
    except Exception as e:
        err = str(e).lower()
        if "429" in err or "rate limit" in err:
            return "Rate limit exceeded. Please wait a few minutes and try again, or use a smaller batch of questions."
        raise


# ---------------------------------------------------------------------------
# Session state: chat history
# ---------------------------------------------------------------------------
if "ai_scout_messages" not in st.session_state:
    st.session_state.ai_scout_messages = []

# ---------------------------------------------------------------------------
# UI
# ---------------------------------------------------------------------------
st.markdown(
    """
    <div class="page-hero">
        <div class="page-hero-title">🤖 AI Scout</div>
        <div class="page-hero-sub">
            Ask questions about players, teams, and matches. Answers are based only on our football database.
        </div>
    </div>
    """,
    unsafe_allow_html=True,
)

# Check for API key (st.secrets)
try:
    api_key = st.secrets.get("GROQ_API_KEY") or st.secrets.get("groq", {}).get("GROQ_API_KEY")
except Exception:
    api_key = None

if not api_key:
    st.warning(
        "**GROQ_API_KEY** not set. Add it in `.streamlit/secrets.toml` (e.g. `GROQ_API_KEY = \"your-key\"`) or in Streamlit Cloud secrets."
    )

# Ensure DB exists (may create from parquet on first run)
try:
    ensure_football_db()
except Exception as e:
    st.error(f"Could not prepare database: {e}")
    st.stop()

# Chat history
for msg in st.session_state.ai_scout_messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

# Input
if prompt := st.chat_input("Ask about players, teams, or matches…"):
    if not api_key:
        with st.chat_message("assistant"):
            st.markdown("Please set **GROQ_API_KEY** in secrets to use the AI Scout.")
        st.stop()

    # Append user message and show it
    st.session_state.ai_scout_messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    # RAG: fetch context from DB (read-only), then Groq
    with st.chat_message("assistant"):
        with st.spinner("Searching database and asking AI…"):
            try:
                conn = get_connection()
                try:
                    context = fetch_context(conn, prompt)
                    answer = ask_groq(prompt, context, api_key)
                finally:
                    conn.close()
                st.markdown(answer)
            except Exception as e:
                st.markdown(f"Error: {e}")
                answer = str(e)

    st.session_state.ai_scout_messages.append({"role": "assistant", "content": answer})

if st.session_state.ai_scout_messages:
    if st.button("Clear chat", key="ai_scout_clear"):
        st.session_state.ai_scout_messages = []
        st.rerun()
