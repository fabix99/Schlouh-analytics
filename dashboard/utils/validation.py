"""Safe calculations and validation for dashboard visuals and metrics.

Use these helpers everywhere we divide, compute percentiles, or display
aggregates so that missing data and division-by-zero never break the UI.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from typing import Optional, Union


def safe_divide(
    num: Union[float, int, np.floating],
    denom: Union[float, int, np.floating],
    default: float = 0.0,
    *,
    allow_nan_denom: bool = True,
) -> float:
    """Return num/denom, or default if denom is 0 or invalid.

    Args:
        num: Numerator.
        denom: Denominator.
        default: Value to return when division is invalid.
        allow_nan_denom: If True, treat NaN denominator as invalid and return default.

    Returns:
        num/denom when denom is finite and non-zero, else default.
    """
    if denom is None or (isinstance(denom, float) and np.isnan(denom)):
        return default
    if num is None or (isinstance(num, float) and np.isnan(num)):
        return default
    try:
        d = float(denom)
        n = float(num)
    except (TypeError, ValueError):
        return default
    if d == 0 or (allow_nan_denom and not np.isfinite(d)):
        return default
    if not np.isfinite(n):
        return default
    return n / d


def safe_percentile_midpoint(
    value: float,
    series: pd.Series,
    default: float = 50.0,
) -> float:
    """Percentile rank (0–100) using midpoint formula: (below + 0.5 * tied) / n * 100.

    Handles empty series, NaN value, and avoids division by zero.
    """
    if value is None or (isinstance(value, float) and np.isnan(value)):
        return default
    clean = series.dropna()
    n = len(clean)
    if n == 0:
        return default
    try:
        below = (clean < value).sum()
        equal = (clean == value).sum()
        return float((below + 0.5 * equal) / n * 100)
    except Exception:
        return default


def clamp(value: float, low: float, high: float) -> float:
    """Clamp value to [low, high]. Handles NaN by returning low."""
    if value is None or (isinstance(value, float) and np.isnan(value)):
        return low
    try:
        v = float(value)
        return max(low, min(high, v))
    except (TypeError, ValueError):
        return low


def safe_float(value: Optional[Union[float, int, str]], default: float = 0.0) -> float:
    """Convert to float; return default if None, NaN, or invalid."""
    if value is None:
        return default
    if isinstance(value, float) and np.isnan(value):
        return default
    try:
        v = float(value)
        return v if np.isfinite(v) else default
    except (TypeError, ValueError):
        return default


def validate_columns(df: Optional[pd.DataFrame], required: list[str]) -> list[str]:
    """Return list of required column names missing from df. Empty list if all present."""
    if df is None or df.empty:
        return list(required)
    missing = [c for c in required if c not in df.columns]
    return missing
