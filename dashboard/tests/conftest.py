"""Pytest configuration and fixtures for dashboard tests.

This module provides:
- Shared fixtures for data loading
- Mock session state for Streamlit
- Browser testing setup with Playwright

Usage:
    pytest dashboard/tests/
"""

import pytest
import pandas as pd
import numpy as np
from typing import Dict, Any, Generator
from unittest.mock import MagicMock, patch

# Add project root to path
import sys
import pathlib
_project_root = pathlib.Path(__file__).parent.parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))


# =============================================================================
# MOCK STREAMLIT SESSION STATE
# =============================================================================

class MockSessionState:
    """Mock Streamlit session state for testing."""

    def __init__(self):
        self._state: Dict[str, Any] = {}

    def __getitem__(self, key: str) -> Any:
        return self._state[key]

    def __setitem__(self, key: str, value: Any) -> None:
        self._state[key] = value

    def __contains__(self, key: str) -> bool:
        return key in self._state

    def get(self, key: str, default: Any = None) -> Any:
        return self._state.get(key, default)

    def clear(self) -> None:
        self._state.clear()


@pytest.fixture
def mock_session_state() -> MockSessionState:
    """Provide a mock session state."""
    return MockSessionState()


@pytest.fixture(autouse=True)
def patch_streamlit_session_state(mock_session_state):
    """Automatically patch st.session_state in all tests."""
    with patch('streamlit.session_state', mock_session_state):
        yield mock_session_state


# =============================================================================
# SAMPLE DATA FIXTURES
# =============================================================================

@pytest.fixture
def sample_player_data() -> pd.DataFrame:
    """Create sample player data for testing."""
    return pd.DataFrame({
        'player_id': [1, 2, 3, 4, 5],
        'player_name': ['John Doe', 'Jane Smith', 'Bob Johnson', 'Alice Brown', 'Charlie Wilson'],
        'player_position': ['F', 'M', 'D', 'G', 'F'],
        'team': ['Team A', 'Team B', 'Team C', 'Team D', 'Team E'],
        'competition_slug': ['premier-league', 'premier-league', 'la-liga', 'la-liga', 'bundesliga'],
        'league_name': ['Premier League', 'Premier League', 'La Liga', 'La Liga', 'Bundesliga'],
        'season': ['2023-24', '2023-24', '2023-24', '2023-24', '2023-24'],
        'total_minutes': [1800, 2000, 1500, 1900, 2200],
        'appearances': [20, 22, 18, 21, 24],
        'avg_rating': [7.2, 7.5, 6.8, 7.0, 7.8],
        'goals': [10, 5, 2, 0, 15],
        'assists': [5, 8, 1, 0, 6],
        'age_at_season_start': [25.0, 28.0, 30.0, 27.0, 23.0],
        'nationality': ['ENG', 'ESP', 'GER', 'FRA', 'BRA'],
    })


@pytest.fixture
def sample_match_data() -> pd.DataFrame:
    """Create sample match data for testing."""
    return pd.DataFrame({
        'match_id': [1, 2, 3, 4, 5],
        'home_team': ['Team A', 'Team C', 'Team E', 'Team A', 'Team C'],
        'away_team': ['Team B', 'Team D', 'Team A', 'Team C', 'Team B'],
        'competition_slug': ['premier-league', 'la-liga', 'bundesliga', 'premier-league', 'la-liga'],
        'season': ['2023-24'] * 5,
        'match_date': pd.date_range('2024-01-01', periods=5),
        'home_goals': [2, 1, 3, 0, 2],
        'away_goals': [1, 1, 1, 0, 0],
    })


@pytest.fixture
def empty_player_data() -> pd.DataFrame:
    """Create empty player DataFrame with correct columns."""
    return pd.DataFrame({
        'player_id': pd.Series(dtype='int64'),
        'player_name': pd.Series(dtype='object'),
        'player_position': pd.Series(dtype='object'),
        'team': pd.Series(dtype='object'),
        'competition_slug': pd.Series(dtype='object'),
        'season': pd.Series(dtype='object'),
        'total_minutes': pd.Series(dtype='float64'),
        'avg_rating': pd.Series(dtype='float64'),
    })


# =============================================================================
# FILTER FIXTURES
# =============================================================================

@pytest.fixture
def filter_defaults() -> Dict[str, Any]:
    """Default filter configuration."""
    return {
        'leagues': [],
        'seasons': [],
        'positions': [],
        'min_minutes': 450,
        'age_bands': [],
        'teams': [],
        'min_rating': 0.0,
    }


@pytest.fixture
def active_filter_config() -> Dict[str, Any]:
    """Active filter configuration with values set."""
    return {
        'leagues': ['premier-league'],
        'seasons': ['2023-24'],
        'positions': ['F'],
        'min_minutes': 900,
        'age_bands': ['23-27'],
        'teams': ['Team A'],
        'min_rating': 7.0,
    }


# =============================================================================
# BROWSER TESTING FIXTURES (Optional - requires Playwright)
# =============================================================================

@pytest.fixture(scope="session")
def browser() -> Generator:
    """Provide a Playwright browser instance for integration tests.

    This fixture is skipped if Playwright is not installed.
    """
    try:
        from playwright.sync_api import sync_playwright

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            yield browser
            browser.close()
    except ImportError:
        pytest.skip("Playwright not installed")
        yield None


@pytest.fixture
def page(browser) -> Generator:
    """Provide a new browser page for each test."""
    if browser is None:
        pytest.skip("Browser not available")

    page = browser.new_page()
    page.set_viewport_size({"width": 1280, "height": 720})
    yield page
    page.close()


@pytest.fixture
def dashboard_url() -> str:
    """URL for the dashboard under test."""
    return "http://localhost:8501"


# =============================================================================
# MARKERS AND CONFIGURATION
# =============================================================================

def pytest_configure(config):
    """Configure pytest markers."""
    config.addinivalue_line(
        "markers", "slow: marks tests as slow (deselect with '-m \"not slow\"')"
    )
    config.addinivalue_line(
        "markers", "integration: marks tests as integration tests (require services)"
    )
    config.addinivalue_line(
        "markers", "ui: marks tests as UI tests (require browser)"
    )


# =============================================================================
# UTILITIES
# =============================================================================

@pytest.fixture
def mock_time() -> Generator:
    """Mock time.time() for consistent timing tests."""
    with patch('time.time') as mock:
        mock.return_value = 1234567890.0
        yield mock
