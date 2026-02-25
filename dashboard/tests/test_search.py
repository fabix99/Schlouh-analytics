"""Tests for enhanced search components.

This module tests all search UX improvements from Phase 1 Sprint 1.2:
- Search debouncing (S1-001)
- Recent searches (S1-002)
- Loading indicators (S1-003)
- Name disambiguation (S1-004)
- Empty state suggestions (S1-005)
"""

import time
import pytest
from unittest.mock import patch, MagicMock, call
from datetime import datetime, timedelta

from dashboard.utils.search_components import (
    SearchDebouncer,
    SearchState,
    get_recent_searches,
    add_to_search_history,
    clear_search_history,
    search_with_disambiguation,
    DisambiguatedPlayer,
    COMMON_NAMES,
    get_trending_searches,
    get_search_suggestions,
)


# =============================================================================
# SEARCH DEBOUNCER TESTS (S1-001)
# =============================================================================

class TestSearchDebouncer:
    """Test SearchDebouncer functionality."""

    def test_debouncer_initialization(self):
        """Test debouncer initializes correctly."""
        debouncer = SearchDebouncer(delay_ms=300)
        assert debouncer.delay_ms == 300
        assert debouncer.last_query == ""

    def test_debounce_delays_execution(self):
        """Test that debounce delays callback execution."""
        debouncer = SearchDebouncer(delay_ms=100)
        callback = MagicMock()

        # Start debounce
        debouncer.debounce("haaland", callback)

        # Callback should not be called immediately
        assert not callback.called

        # Wait for debounce period
        time.sleep(0.15)

        # Callback should now be called
        callback.assert_called_once_with("haaland")

    def test_debounce_cancels_previous_timer(self):
        """Test that new debounce cancels previous timer."""
        debouncer = SearchDebouncer(delay_ms=100)
        callback = MagicMock()

        # First debounce
        debouncer.debounce("haa", callback)

        # Second debounce (should cancel first)
        debouncer.debounce("haaland", callback)

        time.sleep(0.15)

        # Only second query should be executed
        callback.assert_called_once_with("haaland")

    def test_debounce_only_executes_if_unchanged(self):
        """Test callback only executes if query unchanged after delay."""
        debouncer = SearchDebouncer(delay_ms=50)
        callback = MagicMock()

        # Start debounce
        debouncer.debounce("haaland", callback)

        # Change query before delay completes
        time.sleep(0.03)
        debouncer.debounce("haaland new", callback)

        time.sleep(0.1)

        # Only the last query should execute
        assert callback.call_count == 1
        callback.assert_called_with("haaland new")

    def test_cancel_debounce(self):
        """Test canceling pending debounce."""
        debouncer = SearchDebouncer(delay_ms=100)
        callback = MagicMock()

        debouncer.debounce("test", callback)
        debouncer.cancel()

        time.sleep(0.15)

        # Callback should not be called
        assert not callback.called


# =============================================================================
# SEARCH STATE TESTS (S1-001)
# =============================================================================

class TestSearchState:
    """Test SearchState functionality."""

    def test_search_state_initialization(self, mock_session_state):
        """Test SearchState initializes session state."""
        with patch('streamlit.session_state', mock_session_state):
            state = SearchState(key_prefix="test")

            assert mock_session_state.get('test_query') == ""
            assert mock_session_state.get('test_loading') is False
            assert mock_session_state.get('test_results') is None

    def test_search_query_property(self, mock_session_state):
        """Test search query getter/setter."""
        with patch('streamlit.session_state', mock_session_state):
            state = SearchState(key_prefix="test")

            state.query = "haaland"
            assert state.query == "haaland"
            assert mock_session_state['test_query'] == "haaland"

    def test_search_loading_property(self, mock_session_state):
        """Test search loading getter/setter."""
        with patch('streamlit.session_state', mock_session_state):
            state = SearchState(key_prefix="test")

            state.loading = True
            assert state.loading is True
            assert mock_session_state['test_loading'] is True

    def test_search_results_property(self, mock_session_state):
        """Test search results getter/setter."""
        with patch('streamlit.session_state', mock_session_state):
            state = SearchState(key_prefix="test")

            results = [{'name': 'Player 1'}, {'name': 'Player 2'}]
            state.results = results
            assert state.results == results
            assert mock_session_state['test_results'] == results

    def test_reset_search_state(self, mock_session_state):
        """Test resetting search state."""
        with patch('streamlit.session_state', mock_session_state):
            state = SearchState(key_prefix="test")
            state.query = "haaland"
            state.loading = True
            state.results = [{'name': 'Player'}]

            state.reset()

            assert state.query == ""
            assert state.loading is False
            assert state.results is None


# =============================================================================
# SEARCH HISTORY TESTS (S1-002)
# =============================================================================

class TestSearchHistory:
    """Test search history functionality."""

    def test_add_to_history(self, mock_session_state):
        """Test adding search to history."""
        with patch('streamlit.session_state', mock_session_state):
            add_to_search_history("haaland", results_count=5)

            history = mock_session_state.get('search_history', [])
            assert len(history) == 1
            assert history[0]['query'] == "haaland"
            assert history[0]['results_count'] == 5

    def test_add_duplicate_not_added(self, mock_session_state):
        """Test duplicate query not added to history."""
        with patch('streamlit.session_state', mock_session_state):
            add_to_search_history("haaland")
            add_to_search_history("haaland")

            history = mock_session_state.get('search_history', [])
            assert len(history) == 1  # Should only have one entry

    def test_get_recent_searches(self, mock_session_state):
        """Test getting recent searches."""
        with patch('streamlit.session_state', mock_session_state):
            add_to_search_history("haaland")
            add_to_search_history("mbappe")
            add_to_search_history("bellingham")

            recent = get_recent_searches(limit=2)
            assert len(recent) == 2
            assert recent[0] == "bellingham"  # Most recent first
            assert recent[1] == "mbappe"

    def test_clear_history(self, mock_session_state):
        """Test clearing search history."""
        with patch('streamlit.session_state', mock_session_state):
            add_to_search_history("haaland")
            add_to_search_history("mbappe")

            clear_search_history()

            history = mock_session_state.get('search_history', [])
            assert len(history) == 0

    def test_short_query_not_added(self, mock_session_state):
        """Test short queries not added to history."""
        with patch('streamlit.session_state', mock_session_state):
            add_to_search_history("h")  # Too short

            history = mock_session_state.get('search_history', [])
            assert len(history) == 0

    def test_empty_query_not_added(self, mock_session_state):
        """Test empty queries not added to history."""
        with patch('streamlit.session_state', mock_session_state):
            add_to_search_history("")
            add_to_search_history("   ")

            history = mock_session_state.get('search_history', [])
            assert len(history) == 0


# =============================================================================
# SEARCH DISAMBIGUATION TESTS (S1-004)
# =============================================================================

class TestSearchDisambiguation:
    """Test name disambiguation functionality."""

    def test_search_with_disambiguation_basic(self, sample_player_data):
        """Test basic search with disambiguation."""
        results = search_with_disambiguation("John", sample_player_data)

        assert len(results) > 0
        assert all(isinstance(r, DisambiguatedPlayer) for r in results)

    def test_common_name_gets_disambiguation(self, sample_player_data):
        """Test common names get disambiguation context."""
        # Add another John to make it a common name situation
        results = search_with_disambiguation("John", sample_player_data)

        # Should have disambiguation for common names
        johns = [r for r in results if 'John' in r.name]
        if len(johns) > 1:
            assert any(j.disambiguation is not None for j in johns)

    def test_unique_name_no_disambiguation(self, sample_player_data):
        """Test unique names don't get unnecessary disambiguation."""
        results = search_with_disambiguation("Charlie", sample_player_data)

        charlies = [r for r in results if r.name == 'Charlie Wilson']
        if len(charlies) == 1:
            # Single match should not have disambiguation
            assert charlies[0].disambiguation is None

    def test_empty_search_returns_empty(self, sample_player_data):
        """Test empty query returns empty list."""
        results = search_with_disambiguation("", sample_player_data)
        assert results == []

    def test_short_search_returns_empty(self, sample_player_data):
        """Test short query returns empty list."""
        results = search_with_disambiguation("a", sample_player_data)
        assert results == []

    def test_no_match_returns_empty(self, sample_player_data):
        """Test query with no matches returns empty list."""
        results = search_with_disambiguation("xyz123nonexistent", sample_player_data)
        assert results == []

    def test_results_sorted_by_rating(self, sample_player_data):
        """Test results are sorted by rating descending."""
        results = search_with_disambiguation("Team", sample_player_data)

        if len(results) > 1:
            ratings = [r.rating for r in results if r.rating is not None]
            assert ratings == sorted(ratings, reverse=True)


# =============================================================================
# SEARCH SUGGESTIONS TESTS (S1-005)
# =============================================================================

class TestSearchSuggestions:
    """Test search suggestion functionality."""

    def test_get_trending_searches(self):
        """Test getting trending searches."""
        trending = get_trending_searches()

        assert len(trending) > 0
        assert all(isinstance(t, str) for t in trending)
        # Should contain popular players
        assert any('Haaland' in t or 'Mbappé' in t for t in trending)

    def test_get_suggestions_fuzzy_match(self):
        """Test fuzzy matching for suggestions."""
        player_names = [
            'Erling Haaland',
            'Kylian Mbappé',
            'Jude Bellingham',
            'Bukayo Saka'
        ]

        suggestions = get_search_suggestions("haalnd", player_names)
        assert 'Erling Haaland' in suggestions

    def test_get_suggestions_misspelling_correction(self):
        """Test misspelling corrections."""
        player_names = ['Erling Haaland', 'Other Player']

        suggestions = get_search_suggestions("halland", player_names)
        # Should suggest correct spelling
        assert 'Erling Haaland' in suggestions

    def test_get_suggestions_no_suggestions_for_short_query(self):
        """Test no suggestions for short queries."""
        player_names = ['Player One', 'Player Two']

        suggestions = get_search_suggestions("p", player_names)
        assert suggestions == []

    def test_get_suggestions_limit_respected(self):
        """Test suggestion limit is respected."""
        player_names = [
            'Player One', 'Player Two', 'Player Three',
            'Player Four', 'Player Five', 'Player Six'
        ]

        suggestions = get_search_suggestions("player", player_names, limit=3)
        assert len(suggestions) <= 3


# =============================================================================
# COMMON NAMES TESTS
# =============================================================================

class TestCommonNames:
    """Test common names functionality."""

    def test_common_names_list_exists(self):
        """Test common names list is defined."""
        assert len(COMMON_NAMES) > 0
        assert isinstance(COMMON_NAMES, list)
        assert all(isinstance(n, str) for n in COMMON_NAMES)

    def test_common_names_contains_expected(self):
        """Test common names contains expected surnames."""
        assert 'Silva' in COMMON_NAMES
        assert 'Gomez' in COMMON_NAMES
        assert 'Rodriguez' in COMMON_NAMES


# =============================================================================
# INTEGRATION TESTS
# =============================================================================

@pytest.mark.slow
class TestSearchIntegration:
    """Integration tests for complete search flow."""

    def test_full_search_workflow(self, mock_session_state, sample_player_data):
        """Test complete search workflow."""
        with patch('streamlit.session_state', mock_session_state):
            # Initialize search state
            state = SearchState()

            # Perform search
            query = "John"
            results = search_with_disambiguation(query, sample_player_data)

            # Update state
            state.query = query
            state.results = results
            state.results_count = len(results)
            state.loading = False

            # Add to history
            if results:
                add_to_search_history(query, len(results))

            # Verify workflow
            assert state.query == query
            assert state.results is not None
            assert len(state.results) > 0
            assert len(mock_session_state.get('search_history', [])) > 0
