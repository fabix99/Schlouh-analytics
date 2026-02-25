"""Type definitions and TypedDict classes for the dashboard."""

from typing import TypedDict, Optional, Literal
import pandas as pd


class PlayerStats(TypedDict, total=False):
    """TypedDict for player season statistics."""
    player_id: int
    player_name: str
    player_position: Literal["G", "D", "M", "F"]
    team: str
    season: str
    competition_slug: str
    league_name: str
    position_name: str
    appearances: int
    total_minutes: float
    avg_rating: float
    goals: int
    assists: int
    goals_per90: float
    expectedGoals_per90: float
    expectedAssists_per90: float
    keyPass_per90: float
    bigChanceCreated_per90: float
    totalTackle_per90: float
    interceptionWon_per90: float
    duelWon_per90: float
    aerialWon_per90: float
    ballRecovery_per90: float
    totalPass_per90: float
    pass_accuracy_pct: float
    age_at_season_start: float
    age_band: str


class TeamStats(TypedDict, total=False):
    """TypedDict for team season statistics."""
    team_name: str
    season: str
    competition_slug: str
    goals_for: int
    goals_against: int
    xg_for_total: float
    xg_against_total: float
    possession_avg: float
    pass_accuracy_avg: float
    shots_total: int
    big_chances_total: int
    goal_diff: int
    matches_total: int


class TacticalProfile(TypedDict, total=False):
    """TypedDict for team tactical profile."""
    team_name: str
    season: str
    competition_slug: str
    possession_index: float
    directness_index: float
    pressing_index: float
    aerial_index: float
    crossing_index: float
    chance_creation_index: float
    defensive_solidity: float
    home_away_consistency: float
    second_half_intensity: float


class FilterConfig(TypedDict, total=False):
    """Configuration for filtering player data."""
    leagues: list[str]
    seasons: list[str]
    positions: list[str]
    min_minutes: int
    age_min: int
    age_max: int
    teams: list[str]
    min_rating: float
    stat_filters: list  # [{"stat": str, "min": float|None, "max": float|None}, ...]
    percentile_filters: list  # [{"stat": str, "min_pct": float|None, "max_pct": float|None}, ...]


class RadarData(TypedDict):
    """Data structure for radar chart."""
    player_name: str
    stat: str
    pct: float
    raw: float


class SimilarPlayer(TypedDict, total=False):
    """Similar player recommendation data."""
    player_id: int
    player_name: str
    team: str
    avg_rating: float
    expectedGoals_per90: float
    expectedAssists_per90: float
    similarity_dist: float


def safe_get_player_name(df: pd.DataFrame, player_id: int) -> str:
    """Safely get player name from DataFrame."""
    player_rows = df[df["player_id"] == player_id]
    if player_rows.empty:
        return str(player_id)
    return str(player_rows.iloc[0].get("player_name", player_id))
