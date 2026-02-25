"""Tests for enhanced filter components.

This module tests all filter UX improvements from Phase 1 Sprint 1.1:
- Debouncing (F1-001)
- Loading states (F1-002)
- Filter badges (F1-003)
- Clear all functionality (F1-004)
- Individual reset buttons (F1-005)
- Cascading filters (F1-006)
- Precision sliders (F1-007)
- No results state (F1-008)
"""

import time
import pytest
import pandas as pd
from unittest.mock import patch, MagicMock

from dashboard.utils.filter_components import (
    FilterState,
    filter_loading_state,
    EnhancedFilterConfig,
    count_active_filters,
    render_filter_badge,
    FilterDefaults,
    filter_with_clear,
    multiselect_with_clear,
    slider_with_clear,
    number_input_with_clear,
    get_available_positions_for_league,
    get_available_teams_for_league,
    analyze_filter_conflicts,
    find_relaxed_matches,
)


# =============================================================================
# FILTER STATE & DEBOUNCING TESTS (F1-001)
# =============================================================================

class TestFilterState:
    """Test FilterState debouncing functionality."""

    def test_initial_state(self):
        """Test FilterState initializes correctly."""
        state = FilterState()
        assert state.debounce_ms == 300
        assert state.pending_filters == {}
        assert state.is_loading is False

    def test_should_apply_immediately_on_first_change(self):
        """Test filter applies immediately on first change."""
        state = FilterState()
        result = state.should_apply('position', 'FWD')
        assert result is True
        assert state.last_applied_filters['position'] == 'FWD'

    def test_should_not_apply_within_debounce_period(self):
        """Test filter doesn't apply within debounce period."""
        state = FilterState()

        # First change applies
        state.should_apply('position', 'FWD')

        # Immediate second change should not apply
        result = state.should_apply('position', 'MID')
        assert result is False
        assert 'position' in state.pending_filters

    def test_should_apply_after_debounce_period(self, mock_time):
        """Test filter applies after debounce period."""
        state = FilterState()

        # First change at time 1000
        mock_time.return_value = 1000000.0
        state.should_apply('position', 'FWD')

        # Second change after debounce period
        mock_time.return_value = 1000000.5  # 500ms later (more than 300ms debounce)
        result = state.should_apply('position', 'MID')
        assert result is True

    def test_no_apply_when_value_unchanged(self):
        """Test filter doesn't apply when value hasn't changed."""
        state = FilterState()

        # First change
        state.should_apply('position', 'FWD')

        # Same value should not apply
        result = state.should_apply('position', 'FWD')
        assert result is False

    def test_get_pending_filters(self):
        """Test retrieving pending filters."""
        state = FilterState()
        state.should_apply('position', 'FWD')
        state.should_apply('position', 'MID')  # Should be pending

        pending = state.get_pending_filters()
        assert 'position' in pending
        assert pending['position'] == 'MID'

    def test_clear_pending(self):
        """Test clearing pending filters."""
        state = FilterState()
        state.should_apply('position', 'FWD')
        state.should_apply('position', 'MID')

        state.clear_pending()
        assert state.pending_filters == {}

    def test_set_loading(self):
        """Test setting loading state."""
        state = FilterState()
        state.set_loading(True)
        assert state.is_loading is True
        state.set_loading(False)
        assert state.is_loading is False

    def test_reset_all(self):
        """Test resetting all filter state."""
        state = FilterState()
        state.should_apply('position', 'FWD')
        state.set_loading(True)

        state.reset_all()
        assert state.pending_filters == {}
        assert state.last_applied_filters == {}
        assert state.is_loading is False


# =============================================================================
# FILTER CONFIG & BADGE TESTS (F1-003)
# =============================================================================

class TestFilterConfig:
    """Test FilterConfig and badge functionality."""

    def test_filter_config_active_when_value_changed(self):
        """Test filter is active when value differs from default."""
        config = EnhancedFilterConfig(
            key='position',
            label='Position',
            default_value='All',
            current_value='FWD'
        )
        assert config.is_active() is True

    def test_filter_config_inactive_when_default(self):
        """Test filter is inactive when at default."""
        config = EnhancedFilterConfig(
            key='position',
            label='Position',
            default_value='All',
            current_value='All'
        )
        assert config.is_active() is False

    def test_filter_config_with_custom_check(self):
        """Test filter with custom check function."""
        config = EnhancedFilterConfig(
            key='leagues',
            label='Leagues',
            default_value=[],
            current_value=['premier-league'],
            check_fn=lambda c, d: len(c) > 0
        )
        assert config.is_active() is True

        config_empty = EnhancedFilterConfig(
            key='leagues',
            label='Leagues',
            default_value=[],
            current_value=[],
            check_fn=lambda c, d: len(c) > 0
        )
        assert config_empty.is_active() is False


class TestCountActiveFilters:
    """Test counting active filters."""

    def test_count_zero_active(self):
        """Test counting when no filters are active."""
        configs = [
            EnhancedFilterConfig('pos', 'Position', 'All', 'All'),
            EnhancedFilterConfig('league', 'League', [], []),
        ]
        assert count_active_filters(configs) == 0

    def test_count_multiple_active(self):
        """Test counting multiple active filters."""
        configs = [
            EnhancedFilterConfig('pos', 'Position', 'All', 'FWD'),
            EnhancedFilterConfig('league', 'League', [], ['premier-league']),
            EnhancedFilterConfig('age', 'Age', [], []),
        ]
        assert count_active_filters(configs) == 2


# =============================================================================
# FILTER DEFAULTS TESTS (F1-004)
# =============================================================================

class TestFilterDefaults:
    """Test FilterDefaults functionality."""

    def test_filter_defaults_creation(self):
        """Test creating FilterDefaults."""
        defaults = FilterDefaults(values={
            'position': 'All',
            'league': [],
            'min_minutes': 450,
        })
        assert defaults.get_keys() == ['position', 'league', 'min_minutes']

    def test_reset_session_state(self, mock_session_state):
        """Test resetting session state to defaults."""
        # Set some non-default values
        mock_session_state['position'] = 'FWD'
        mock_session_state['league'] = ['premier-league']
        mock_session_state['min_minutes'] = 900

        defaults = FilterDefaults(values={
            'position': 'All',
            'league': [],
            'min_minutes': 450,
        })

        with patch('streamlit.session_state', mock_session_state):
            defaults.reset_session_state()

        assert mock_session_state['position'] == 'All'
        assert mock_session_state['league'] == []
        assert mock_session_state['min_minutes'] == 450


# =============================================================================
# CASCADING FILTER TESTS (F1-006)
# =============================================================================

class TestCascadingFilters:
    """Test cascading filter functionality."""

    def test_get_positions_for_all_leagues(self, sample_player_data):
        """Test getting positions when no league selected."""
        positions = get_available_positions_for_league(None, sample_player_data)
        assert 'All' in positions
        assert len(positions) > 1

    def test_get_positions_for_specific_league(self, sample_player_data):
        """Test getting positions for specific league."""
        positions = get_available_positions_for_league('premier-league', sample_player_data)
        assert 'All' in positions
        # Should only have positions from that league
        assert 'F' in positions or 'M' in positions

    def test_get_teams_for_all_leagues(self, sample_player_data):
        """Test getting teams when no league selected."""
        teams = get_available_teams_for_league(None, sample_player_data)
        assert len(teams) > 0
        assert 'Team A' in teams

    def test_get_teams_for_specific_league(self, sample_player_data):
        """Test getting teams for specific league."""
        teams = get_available_teams_for_league('premier-league', sample_player_data)
        assert 'Team A' in teams
        assert 'Team B' in teams
        # Should not have teams from other leagues
        assert 'Team C' not in teams  # La Liga team


# =============================================================================
# NO RESULTS ANALYSIS TESTS (F1-008)
# =============================================================================

class TestNoResultsAnalysis:
    """Test no results conflict analysis."""

    def test_no_conflicts_with_valid_filters(self, sample_player_data):
        """Test no conflicts when filters would return results."""
        filters = {
            'position': 'F',
            'league': 'premier-league',
        }
        conflicts = analyze_filter_conflicts(filters, sample_player_data)
        assert len(conflicts) == 0

    def test_conflict_position_age_mismatch(self, sample_player_data):
        """Test conflict when position and age range don't match."""
        filters = {
            'position': 'F',
            'age_range': (50, 60),  # No forwards in this age range
        }
        conflicts = analyze_filter_conflicts(filters, sample_player_data)
        assert len(conflicts) > 0

    def test_conflict_elite_regular_starters(self, sample_player_data):
        """Test conflict for rare elite regular starters."""
        filters = {
            'rating_threshold': 8.5,
            'min_minutes': 2000,
        }
        conflicts = analyze_filter_conflicts(
            filters, sample_player_data, min_players_threshold=1
        )
        # Should warn about rare combination
        assert any('rare' in c.explanation.lower() for c in conflicts)

    def test_find_relaxed_matches(self, sample_player_data):
        """Test finding relaxed matches when no results."""
        filters = {
            'position': 'Z',  # Invalid position
            'league': 'premier-league',
        }
        relaxed = find_relaxed_matches(filters, sample_player_data, limit=3)
        # Should find matches by relaxing one filter
        assert relaxed is not None
        assert len(relaxed) > 0


# =============================================================================
# INTEGRATION TESTS
# =============================================================================

@pytest.mark.slow
class TestFilterIntegration:
    """Integration tests for complete filter flow."""

    def test_full_filter_workflow(self, sample_player_data):
        """Test complete filter workflow from config to results."""
        from dashboard.utils.filters import apply_filters, FilterConfig

        config = FilterConfig(
            leagues=['premier-league'],
            seasons=[],
            positions=['F'],
            min_minutes=1000,
            age_bands=[],
            teams=[],
            min_rating=0.0,
        )

        result = apply_filters(sample_player_data, config)

        # Should only have forwards from Premier League with > 1000 minutes
        assert all(result['player_position'] == 'F')
        assert all(result['competition_slug'] == 'premier-league')
        assert all(result['total_minutes'] >= 1000)
