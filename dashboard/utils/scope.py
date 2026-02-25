"""Default scope helpers: current season, leagues + UEFA only (no cups, no national teams)."""

from __future__ import annotations

import pandas as pd

try:
    from dashboard.utils.constants import CURRENT_SEASON, DEFAULT_COMPETITION_SLUGS
except ImportError:
    CURRENT_SEASON = "2025-26"
    DEFAULT_COMPETITION_SLUGS = [
        "england-premier-league", "spain-laliga", "italy-serie-a", "france-ligue-1",
        "germany-bundesliga", "portugal-primeira-liga", "belgium-pro-league",
        "netherlands-eredivisie", "turkey-super-lig", "saudi-pro-league", "brazil-serie-a",
        "uefa-champions-league", "uefa-europa-league", "uefa-conference-league",
    ]


def filter_to_default_scope(df: pd.DataFrame) -> pd.DataFrame:
    """
    Filter DataFrame to default scope: current season and leagues + UEFA only.
    Requires columns 'season' and 'competition_slug'.
    """
    if df.empty:
        return df
    if "season" not in df.columns or "competition_slug" not in df.columns:
        return df
    mask = (df["season"] == CURRENT_SEASON) & (
        df["competition_slug"].isin(DEFAULT_COMPETITION_SLUGS)
    )
    return df[mask].copy()


def is_in_default_scope(competition_slug: str) -> bool:
    """Return True if competition is in default scope (leagues + UEFA)."""
    return competition_slug in DEFAULT_COMPETITION_SLUGS


def get_default_season() -> str:
    """Return the current season used as default across dashboards."""
    return CURRENT_SEASON
