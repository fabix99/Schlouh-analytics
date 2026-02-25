"""Enhanced search components with debouncing, history, and improved UX.

This module provides advanced search UI components for the dashboard.

Key Features:
- Debounced search input (300ms)
- Recent search history with persistence
- Loading indicators with skeleton UI
- Name disambiguation for common names
- Smart empty states with suggestions
"""

import time
from typing import Optional, Callable, List, Dict, Any, Tuple
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from threading import Timer
from difflib import get_close_matches

import pandas as pd
import streamlit as st


# =============================================================================
# SEARCH DEBOUNCER (TASK S1-001: Search Debouncing 300ms)
# =============================================================================

@dataclass
class SearchDebouncer:
    """Debouncer for search input with delayed execution.

    Usage:
        if 'search_debouncer' not in st.session_state:
            st.session_state.search_debouncer = SearchDebouncer(delay_ms=300)

        def on_search_input_change():
            query = st.session_state.search_input
            debouncer = st.session_state.search_debouncer
            st.session_state.search_loading = True
            debouncer.debounce(query, perform_search)
    """

    delay_ms: int = 300
    _timer: Optional[Timer] = field(default=None, repr=False)
    last_query: str = ""

    def debounce(self, query: str, callback: Callable[[str], None]) -> None:
        """Execute callback after delay if query unchanged.

        Args:
            query: Current search query
            callback: Function to call after debounce period
        """
        # Cancel pending timer
        if self._timer:
            self._timer.cancel()

        self.last_query = query

        # Set new timer
        def delayed_search():
            if query == self.last_query:  # Query hasn't changed
                callback(query)

        self._timer = Timer(self.delay_ms / 1000, delayed_search)
        self._timer.start()

    def cancel(self) -> None:
        """Cancel any pending search."""
        if self._timer:
            self._timer.cancel()
            self._timer = None


class SearchState:
    """Manages search state including loading and results."""

    def __init__(self, key_prefix: str = "search"):
        self.key_prefix = key_prefix
        self._init_state()

    def _init_state(self) -> None:
        """Initialize search state in session state."""
        prefix = self.key_prefix
        defaults = {
            f"{prefix}_query": "",
            f"{prefix}_loading": False,
            f"{prefix}_results": None,
            f"{prefix}_results_count": 0,
            f"{prefix}_error": None,
            f"{prefix}_debouncer": SearchDebouncer(delay_ms=300),
        }
        for key, value in defaults.items():
            if key not in st.session_state:
                st.session_state[key] = value

    @property
    def query(self) -> str:
        return st.session_state.get(f"{self.key_prefix}_query", "")

    @query.setter
    def query(self, value: str) -> None:
        st.session_state[f"{self.key_prefix}_query"] = value

    @property
    def loading(self) -> bool:
        return st.session_state.get(f"{self.key_prefix}_loading", False)

    @loading.setter
    def loading(self, value: bool) -> None:
        st.session_state[f"{self.key_prefix}_loading"] = value

    @property
    def results(self) -> Optional[Any]:
        return st.session_state.get(f"{self.key_prefix}_results")

    @results.setter
    def results(self, value: Any) -> None:
        st.session_state[f"{self.key_prefix}_results"] = value

    @property
    def results_count(self) -> int:
        return st.session_state.get(f"{self.key_prefix}_results_count", 0)

    @results_count.setter
    def results_count(self, value: int) -> None:
        st.session_state[f"{self.key_prefix}_results_count"] = value

    def debounce_search(self, query: str, callback: Callable[[str], None]) -> None:
        """Debounced search execution."""
        debouncer = st.session_state.get(f"{self.key_prefix}_debouncer")
        if debouncer:
            debouncer.debounce(query, callback)

    def reset(self) -> None:
        """Reset search state."""
        self.query = ""
        self.loading = False
        self.results = None
        self.results_count = 0


# =============================================================================
# RECENT SEARCHES (TASK S1-002: Recent Searches Dropdown)
# =============================================================================

MAX_SEARCH_HISTORY = 50
HISTORY_CUTOFF_DAYS = 30


def get_recent_searches(limit: int = 5) -> List[str]:
    """Get recent searches from session state.

    Args:
        limit: Maximum number of recent searches to return

    Returns:
        List of recent search queries (most recent first)
    """
    if 'search_history' not in st.session_state:
        st.session_state.search_history = []

    # Clean old entries (older than 30 days)
    cutoff = datetime.now() - timedelta(days=HISTORY_CUTOFF_DAYS)
    history = st.session_state.search_history

    # Filter out old entries
    valid_history = [
        entry for entry in history
        if isinstance(entry, dict) and datetime.fromisoformat(entry.get('timestamp', '2000-01-01')) > cutoff
    ]

    # Return recent queries (most recent first)
    recent = [entry['query'] for entry in valid_history[-limit:][::-1]]
    return list(dict.fromkeys(recent))  # Remove duplicates, preserve order


def add_to_search_history(query: str, results_count: int = 0) -> None:
    """Add search query to history.

    Args:
        query: Search query string
        results_count: Number of results found
    """
    if not query or len(query.strip()) < 2:
        return

    if 'search_history' not in st.session_state:
        st.session_state.search_history = []

    query = query.strip()

    # Don't add duplicates at the top
    history = st.session_state.search_history
    if history and history[-1].get('query') == query:
        return

    history.append({
        'query': query,
        'timestamp': datetime.now().isoformat(),
        'results_count': results_count
    })

    # Keep only last MAX_SEARCH_HISTORY searches
    st.session_state.search_history = history[-MAX_SEARCH_HISTORY:]


def render_recent_searches_pills(
    on_select: Callable[[str], None],
    limit: int = 5
) -> None:
    """Render recent searches as clickable pills.

    Args:
        on_select: Callback when a recent search is clicked
        limit: Maximum number of pills to show
    """
    recent = get_recent_searches(limit)

    if not recent:
        return

    st.caption("Recent searches:")

    # Create clickable pills using columns
    cols = st.columns(min(len(recent), 5))

    for i, query in enumerate(recent[:5]):
        with cols[i]:
            if st.button(
                f"🔍 {query[:20]}{'...' if len(query) > 20 else ''}",
                key=f"recent_{i}",
                use_container_width=True,
                type="tertiary"
            ):
                on_select(query)


def render_recent_searches_dropdown(
    on_select: Callable[[str], None],
    key: str = "recent_dropdown"
) -> None:
    """Render recent searches as a dropdown.

    Args:
        on_select: Callback when a recent search is selected
        key: Widget key
    """
    recent = get_recent_searches(8)

    if not recent:
        return

    selected = st.selectbox(
        "Recent searches",
        [""] + recent,
        key=key,
        label_visibility="collapsed"
    )

    if selected:
        on_select(selected)


def clear_search_history() -> None:
    """Clear all search history."""
    st.session_state.search_history = []


# =============================================================================
# SEARCH LOADING INDICATORS (TASK S1-003: Search Loading Indicator)
# =============================================================================

def render_search_loading_skeleton(n_skeletons: int = 3) -> None:
    """Render loading skeleton for search results.

    Args:
        n_skeletons: Number of skeleton rows to show
    """
    st.markdown("""
        <div style="padding: 16px; background: #161B22; border-radius: 8px; margin-bottom: 12px;">
            <div style="display: flex; align-items: center; gap: 12px; margin-bottom: 16px;">
                <div style="
                    width: 20px;
                    height: 20px;
                    border: 2px solid rgba(0,212,170,0.3);
                    border-top-color: #00D4AA;
                    border-radius: 50%;
                    animation: search-spin 1s linear infinite;
                "></div>
                <span style="color: #8B949E; font-size: 14px;">Searching for players...</span>
            </div>
        </div>
        <style>
            @keyframes search-spin {
                to { transform: rotate(360deg); }
            }
        </style>
    """, unsafe_allow_html=True)

    # Show skeleton cards with shimmer
    for i in range(n_skeletons):
        st.markdown(f"""
            <div style="
                height: 60px;
                background: linear-gradient(90deg, #21262D 25%, #30363D 50%, #21262D 75%);
                background-size: 200% 100%;
                animation: shimmer 1.5s infinite;
                border-radius: 6px;
                margin: 8px 0;
            "></div>
            <style>
                @keyframes shimmer {{
                    0% {{ background-position: 200% 0; }}
                    100% {{ background-position: -200% 0; }}
                }}
            </style>
        """, unsafe_allow_html=True)


def render_search_results_header(
    results_count: int,
    query: str,
    loading: bool = False
) -> None:
    """Render search results header with count.

    Args:
        results_count: Number of results
        query: Search query
        loading: Whether search is still loading
    """
    if loading:
        render_search_loading_skeleton()
        return

    if results_count == 0:
        return  # Let empty state handle this

    # Success message with count
    st.success(f"Found {results_count} player{'s' if results_count > 1 else ''} for '{query}'")


# =============================================================================
# NAME DISAMBIGUATION (TASK S1-004: Name Disambiguation UI)
# =============================================================================

# Common names that often have multiple players
COMMON_NAMES = [
    'Silva', 'Santos', 'Gomez', 'Rodriguez', 'Gonzalez',
    'Hernandez', 'Fernandez', 'Lopez', 'Martinez', 'Garcia',
    'Smith', 'Johnson', 'Williams', 'Brown', 'Jones',
    'Davis', 'Miller', 'Wilson', 'Moore', 'Taylor'
]


@dataclass
class DisambiguatedPlayer:
    """Player data with disambiguation context."""

    player_id: int
    name: str
    team: str
    position: str
    league: str
    age: Optional[float] = None
    nationality: Optional[str] = None
    rating: Optional[float] = None
    disambiguation: Optional[Dict] = None


def search_with_disambiguation(
    query: str,
    df: pd.DataFrame,
    name_col: str = "player_name",
    team_col: str = "team",
    position_col: str = "player_position",
    league_col: str = "league_name"
) -> List[DisambiguatedPlayer]:
    """Search with team/position context for disambiguation.

    Args:
        query: Search query
        df: Player DataFrame
        name_col: Column containing player names
        team_col: Column containing team names
        position_col: Column containing positions
        league_col: Column containing league names

    Returns:
        List of DisambiguatedPlayer objects
    """
    if not query or len(query) < 2:
        return []

    # Fuzzy match names (case-insensitive partial match)
    query_lower = query.lower()
    matches = df[df[name_col].str.lower().str.contains(query_lower, na=False)]

    if matches.empty:
        return []

    # Group by name for disambiguation
    name_groups = matches.groupby(name_col)

    results = []
    for name, group in name_groups:
        n_players = len(group)

        for _, player in group.iterrows():
            # Build disambiguation context for common names
            disc = None
            if n_players > 1 or name.split()[-1] in COMMON_NAMES:
                disc = {
                    'context': f"{player.get(team_col, 'Unknown')} • {player.get(position_col, 'Unknown')} • {player.get(league_col, 'Unknown')}",
                    'similar_names_count': n_players,
                    'age': player.get('age_at_season_start'),
                    'nationality': player.get('nationality'),
                }

            results.append(DisambiguatedPlayer(
                player_id=int(player.get('player_id', 0)),
                name=name,
                team=player.get(team_col, 'Unknown'),
                position=player.get(position_col, 'Unknown'),
                league=player.get(league_col, 'Unknown'),
                age=player.get('age_at_season_start'),
                nationality=player.get('nationality'),
                rating=player.get('avg_rating'),
                disambiguation=disc
            ))

    # Sort by rating (best first)
    results.sort(key=lambda x: x.rating or 0, reverse=True)

    return results


def render_disambiguated_result(
    player: DisambiguatedPlayer,
    on_select: Optional[Callable[[int, str], None]] = None,
    key_suffix: str = ""
) -> None:
    """Render a player card with disambiguation context.

    Args:
        player: DisambiguatedPlayer to render
        on_select: Callback when player is selected
        key_suffix: Unique suffix for widget keys
    """
    with st.container():
        col1, col2 = st.columns([1, 4])

        with col1:
            # Avatar placeholder or photo
            st.markdown(f"""
                <div style="
                    width: 60px;
                    height: 60px;
                    background: linear-gradient(135deg, #0068c9, #00D4AA);
                    border-radius: 50%;
                    display: flex;
                    align-items: center;
                    justify-content: center;
                    color: white;
                    font-weight: bold;
                    font-size: 20px;
                ">{player.name[0].upper()}</div>
            """, unsafe_allow_html=True)

        with col2:
            # Name with disambiguation badge if needed
            name_display = f"**{player.name}**"

            if player.disambiguation:
                disc = player.disambiguation
                count = disc['similar_names_count']

                # Show disambiguation context
                st.markdown(f"""
                    {name_display}
                    <span style="
                        background: #ff4b4b;
                        color: white;
                        padding: 2px 8px;
                        border-radius: 4px;
                        font-size: 11px;
                        margin-left: 8px;
                    ">{count} players with this name</span>
                """, unsafe_allow_html=True)

                # Context line
                context_parts = [f"🏟️ {disc['context']}"]
                if disc.get('age'):
                    context_parts.append(f"🎂 Age: {disc['age']:.0f}")
                if disc.get('nationality'):
                    context_parts.append(f"🌍 {disc['nationality']}")

                st.caption(" | ".join(context_parts))
            else:
                st.markdown(name_display)
                st.caption(f"🏟️ {player.team} • {player.position}")

            # Key stats row
            stats_cols = st.columns(4)
            stats = [
                ('⭐', f"{player.rating:.2f}" if player.rating else 'N/A', 'Rating'),
                ('⚽', 'View', 'Profile'),
                ('🎯', player.position, 'Position'),
                ('⏱️', player.team[:15], 'Team'),
            ]

            for col, (icon, value, label) in zip(stats_cols, stats):
                with col:
                    if label == 'Profile' and on_select:
                        if st.button(
                            f"{icon} {value}",
                            key=f"view_{player.player_id}_{key_suffix}",
                            use_container_width=True,
                            type="primary" if label == 'Profile' else "secondary"
                        ):
                            on_select(player.player_id, player.name)
                    else:
                        st.metric(f"{icon} {label}", value)

        st.divider()


def handle_common_name_search(
    query: str,
    df: pd.DataFrame,
    on_select: Optional[Callable[[int, str], None]] = None
) -> List[DisambiguatedPlayer]:
    """Enhanced search for common names with quick filters.

    Args:
        query: Search query
        df: Player DataFrame
        on_select: Callback when player is selected

    Returns:
        List of DisambiguatedPlayer results
    """
    results = search_with_disambiguation(query, df)

    # If common name and many results, show filtering UI
    last_name = query.split()[-1] if query else ""
    if last_name in COMMON_NAMES and len(results) > 5:
        st.warning(f"⚠️ '{query}' is a common name with {len(results)} matches. Use filters below to narrow down.")

        # Quick filters for common names
        filter_cols = st.columns(3)

        with filter_cols[0]:
            leagues = ['All'] + sorted(list(set(r.league for r in results)))
            league_filter = st.selectbox("Filter by League", leagues, key="common_name_league")

        with filter_cols[1]:
            teams = ['All'] + sorted(list(set(r.team for r in results)))
            team_filter = st.selectbox("Filter by Team", teams, key="common_name_team")

        with filter_cols[2]:
            positions = ['All'] + sorted(list(set(r.position for r in results)))
            position_filter = st.selectbox("Filter by Position", positions, key="common_name_position")

        # Apply quick filters
        filtered = results
        if league_filter != "All":
            filtered = [r for r in filtered if r.league == league_filter]
        if team_filter != "All":
            filtered = [r for r in filtered if r.team == team_filter]
        if position_filter != "All":
            filtered = [r for r in filtered if r.position == position_filter]

        return filtered

    return results


# =============================================================================
# EMPTY STATE WITH SUGGESTIONS (TASK S1-005: Enhance Empty State)
# =============================================================================

# Common misspellings mapping
COMMON_MISSPELLINGS = {
    'halland': 'Erling Haaland',
    'mbape': 'Kylian Mbappé',
    'mbappe': 'Kylian Mbappé',
    'odegard': 'Martin Ødegaard',
    'salah': 'Mohamed Salah',
    'kane': 'Harry Kane',
    'bellingham': 'Jude Bellingham',
    'saka': 'Bukayo Saka',
    'vinicius': 'Vinícius Júnior',
    'rodrygo': 'Rodrygo',
    'foden': 'Phil Foden',
    'palmer': 'Cole Palmer',
}


def get_trending_searches() -> List[str]:
    """Get trending/popular player searches."""
    return [
        "Erling Haaland",
        "Kylian Mbappé",
        "Jude Bellingham",
        "Vinícius Júnior",
        "Bukayo Saka",
        "Phil Foden",
        "Martin Ødegaard",
        "Cole Palmer",
    ]


def get_search_suggestions(
    query: str,
    player_names: List[str],
    limit: int = 5
) -> List[str]:
    """Generate search suggestions based on similarity.

    Args:
        query: Search query
        player_names: List of all available player names
        limit: Maximum suggestions

    Returns:
        List of suggested player names
    """
    if not query or len(query) < 2:
        return []

    suggestions = []

    # Check for common misspellings first
    query_lower = query.lower()
    if query_lower in COMMON_MISSPELLINGS:
        suggestions.append(COMMON_MISSPELLINGS[query_lower])

    # Find close matches using difflib
    close_matches = get_close_matches(
        query_lower,
        [name.lower() for name in player_names],
        n=limit,
        cutoff=0.6
    )

    # Get original case versions
    for match in close_matches:
        original = next(
            (name for name in player_names if name.lower() == match),
            match.title()
        )
        if original not in suggestions:
            suggestions.append(original)

    return suggestions[:limit]


def render_empty_search_state(
    query: str,
    player_names: List[str],
    on_search: Callable[[str], None],
    on_show_trending: Optional[Callable[[str], None]] = None
) -> None:
    """Render enhanced empty state with suggestions.

    Args:
        query: Search query that returned no results
        player_names: List of all available player names
        on_search: Callback to perform a new search
        on_show_trending: Optional callback for trending searches
    """
    st.info(f"🔍 **No results for '{query}'**")

    # Suggestions
    suggestions = get_search_suggestions(query, player_names)

    if suggestions:
        st.write("**Did you mean:**")

        sug_cols = st.columns(min(len(suggestions), 5))
        for i, sug in enumerate(suggestions):
            with sug_cols[i]:
                if st.button(
                    f"💡 {sug}",
                    key=f"sug_{i}",
                    use_container_width=True,
                    type="tertiary"
                ):
                    on_search(sug)

    # Trending searches
    st.divider()
    st.write("**Trending searches:**")

    trending = get_trending_searches()
    trend_cols = st.columns(len(trending[:5]))

    for i, player in enumerate(trending[:5]):
        with trend_cols[i]:
            last_name = player.split()[-1]
            if st.button(
                f"🔥 {last_name}",
                key=f"trend_{i}",
                use_container_width=True,
                type="tertiary"
            ):
                if on_show_trending:
                    on_show_trending(player)
                else:
                    on_search(player)

    # Search tips
    with st.expander("💡 Search Tips"):
        st.markdown("""
            - **Partial names work**: Try "Haal" for Haaland
            - **Team names**: Search "Manchester" for United/City players
            - **Positions**: "Best GK" for top goalkeepers
            - **No accents needed**: "Mbappe" finds Mbappé
            - **Use filters**: Narrow by league, age, rating
        """)

    # Discover section with random players
    st.divider()
    st.write("**Discover players:**")

    import random
    if player_names:
        random_players = random.sample(player_names, min(3, len(player_names)))
        for player in random_players:
            with st.container():
                col1, col2 = st.columns([1, 4])
                with col1:
                    st.markdown(f"""
                        <div style="
                            width: 40px;
                            height: 40px;
                            background: linear-gradient(135deg, #0068c9, #00D4AA);
                            border-radius: 50%;
                            display: flex;
                            align-items: center;
                            justify-content: center;
                            color: white;
                            font-weight: bold;
                            font-size: 16px;
                        ">{player[0].upper()}</div>
                    """, unsafe_allow_html=True)
                with col2:
                    st.write(f"**{player}**")
                    if st.button("Search", key=f"disc_{player[:20]}", type="tertiary"):
                        on_search(player)


# =============================================================================
# COMPOSITE SEARCH COMPONENT
# =============================================================================

class EnhancedSearch:
    """Complete enhanced search component with all UX improvements."""

    def __init__(
        self,
        df: pd.DataFrame,
        key_prefix: str = "search",
        placeholder: str = "Search players...",
        on_result_select: Optional[Callable[[int, str], None]] = None
    ):
        self.df = df
        self.key_prefix = key_prefix
        self.placeholder = placeholder
        self.on_result_select = on_result_select
        self.state = SearchState(key_prefix)

        # Get all player names for suggestions
        self.player_names = df["player_name"].unique().tolist() if "player_name" in df.columns else []

    def render_input(self) -> str:
        """Render search input with recent searches."""
        # Search input with debouncing
        search_col, recent_col = st.columns([3, 1])

        with search_col:
            query = st.text_input(
                "Search",
                value=self.state.query,
                placeholder=self.placeholder,
                key=f"{self.key_prefix}_input",
                label_visibility="collapsed"
            )

        with recent_col:
            # Recent searches dropdown
            def on_recent_select(selected: str) -> None:
                st.session_state[f"{self.key_prefix}_input"] = selected
                self._perform_search(selected)

            render_recent_searches_dropdown(on_recent_select, key=f"{self.key_prefix}_recent")

        # Recent searches pills below
        def on_pill_select(selected: str) -> None:
            st.session_state[f"{self.key_prefix}_input"] = selected
            self._perform_search(selected)

        render_recent_searches_pills(on_pill_select, limit=5)

        return query

    def _perform_search(self, query: str) -> None:
        """Execute search with loading state."""
        self.state.loading = True
        self.state.query = query

        # Debounce the actual search
        def execute_search(q: str) -> None:
            results = search_with_disambiguation(q, self.df)
            self.state.results = results
            self.state.results_count = len(results)
            self.state.loading = False

            # Add to history if we got results
            if results:
                add_to_search_history(q, len(results))

            st.rerun()

        self.state.debounce_search(query, execute_search)

    def render_results(self) -> None:
        """Render search results or empty state."""
        query = self.state.query
        loading = self.state.loading
        results = self.state.results

        # Show loading or results header
        render_search_results_header(self.state.results_count, query, loading)

        if loading:
            return

        # Show empty state if no results
        if not results and query:
            def on_suggestion_search(suggested: str) -> None:
                st.session_state[f"{self.key_prefix}_input"] = suggested
                self._perform_search(suggested)
                st.rerun()

            render_empty_search_state(
                query,
                self.player_names,
                on_suggestion_search
            )
            return

        # Render results with disambiguation
        if results:
            for i, player in enumerate(results[:10]):  # Limit to top 10
                render_disambiguated_result(
                    player,
                    on_select=self.on_result_select,
                    key_suffix=f"{self.key_prefix}_{i}"
                )

    def render(self) -> None:
        """Render complete search component."""
        query = self.render_input()

        # Check if query changed
        if query != self.state.query:
            self._perform_search(query)

        self.render_results()
