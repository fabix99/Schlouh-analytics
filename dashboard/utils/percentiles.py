"""Lightweight percentile helpers (z-score → CDF). No dependency on dashboard.utils.data."""

from __future__ import annotations

import pandas as pd


def get_percentile_zscore(value: float, series: pd.Series) -> float:
    """
    Percentile (0–100) of value within series using z-score → normal CDF.
    More actionable than rank: distance from average maps to percentile spread
    (e.g. 1.0 vs 0.5 xG/90 will differ more than 100 vs 99 rank percentile).
    Returns NaN when value or series is invalid; 50 when std=0 (constant series).
    """
    from scipy.stats import norm
    if pd.isna(value) or series is None:
        return float("nan")
    clean = series.dropna()
    if len(clean) == 0:
        return float("nan")
    mean = clean.mean()
    std = clean.std()
    if pd.isna(std) or std < 1e-10:
        return 50.0
    z = (float(value) - mean) / std
    return float(norm.cdf(z) * 100)
