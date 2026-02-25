"""
Shared utilities for the processed analytics build scripts.
Paths and constants; parse_ratio, parse_pct, position_group, per90.

Paths prefer src.config when importable so SOFASCORE_* env overrides apply in CI/prod.
"""

import re
import sys
from pathlib import Path

import pandas as pd
import numpy as np

ROOT = Path(__file__).resolve().parent.parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

try:
    from src.config import RAW_BASE, DERIVED_DIR as _DERIVED, PROCESSED_DIR as _PROCESSED, INDEX_DIR as _INDEX
    RAW_DIR = RAW_BASE
    DERIVED_DIR = _DERIVED
    PROCESSED_DIR = _PROCESSED
    INDEX_DIR = _INDEX
except ImportError:
    RAW_DIR = ROOT / "data" / "raw"
    DERIVED_DIR = ROOT / "data" / "derived"
    PROCESSED_DIR = ROOT / "data" / "processed"
    INDEX_DIR = ROOT / "data" / "index"

MIN_MINUTES_SEASON = 450
MIN_MINUTES_CAREER = 900

# All stat_* columns from player_appearances.parquet (used for aggregation)
STAT_COLS = [
    "stat_totalPass",
    "stat_accuratePass",
    "stat_totalLongBalls",
    "stat_accurateLongBalls",
    "stat_accurateOwnHalfPasses",
    "stat_totalOwnHalfPasses",
    "stat_accurateOppositionHalfPasses",
    "stat_totalOppositionHalfPasses",
    "stat_ballRecovery",
    "stat_goodHighClaim",
    "stat_savedShotsFromInsideTheBox",
    "stat_saves",
    "stat_minutesPlayed",
    "stat_touches",
    "stat_rating",
    "stat_possessionLostCtrl",
    "stat_totalShots",
    "stat_aerialLost",
    "stat_aerialWon",
    "stat_duelLost",
    "stat_duelWon",
    "stat_totalContest",
    "stat_blockedScoringAttempt",
    "stat_totalClearance",
    "stat_outfielderBlock",
    "stat_totalTackle",
    "stat_wonTackle",
    "stat_challengeLost",
    "stat_interceptionWon",
    "stat_wasFouled",
    "stat_fouls",
    "stat_wonContest",
    "stat_totalCross",
    "stat_shotOffTarget",
    "stat_onTargetScoringAttempt",
    "stat_unsuccessfulTouch",
    "stat_keyPass",
    "stat_dispossessed",
    "stat_accurateCross",
    "stat_totalOffside",
    "stat_punches",
    "stat_totalKeeperSweeper",
    "stat_accurateKeeperSweeper",
    "stat_bigChanceCreated",
    "stat_bigChanceMissed",
    "stat_goals",
    "stat_goalAssist",
    "stat_hitWoodwork",
    "stat_penaltyFaced",
    "stat_penaltyConceded",
    "stat_errorLeadToAGoal",
    "stat_clearanceOffLine",
    "stat_penaltyWon",
    "stat_errorLeadToAShot",
    "stat_crossNotClaimed",
    "stat_penaltyMiss",
    "stat_penaltySave",
    "stat_lastManTackle",
    "stat_ownGoals",
    "stat_expectedGoals",
    "stat_expectedGoalsOnTarget",
    "stat_expectedAssists",
    "stat_goalsPrevented",
    "stat_totalBallCarriesDistance",
    "stat_ballCarriesCount",
    "stat_totalProgression",
    "stat_bestBallCarryProgression",
    "stat_totalProgressiveBallCarriesDistance",
    "stat_progressiveBallCarriesCount",
    "stat_keeperSaveValue",
    "stat_passValueNormalized",
    "stat_defensiveValueNormalized",
    "stat_dribbleValueNormalized",
    "stat_shotValueNormalized",
    "stat_goalkeeperValueNormalized",
    "stat_metersCoveredWalkingKm",
    "stat_metersCoveredJoggingKm",
    "stat_metersCoveredRunningKm",
    "stat_metersCoveredHighSpeedRunningKm",
    "stat_metersCoveredSprintingKm",
]


def parse_ratio(s) -> tuple:
    """Parse '23/56 (41%)' -> (23, 56, 0.41) or (None, None, None)."""
    if pd.isna(s) or not isinstance(s, str):
        return (None, None, None)
    s = s.strip()
    # Match "23/56 (41%)" or "3/16 (19%)"
    m = re.match(r"(\d+)\s*/\s*(\d+)\s*\(\s*(\d+(?:\.\d+)?)\s*%\)", s)
    if m:
        return (int(m.group(1)), int(m.group(2)), float(m.group(3)) / 100.0)
    return (None, None, None)


def parse_pct(s):
    """Parse '52%' -> 0.52. Returns None if not parseable."""
    if pd.isna(s):
        return None
    if isinstance(s, (int, float)):
        if 0 <= s <= 100:
            return float(s) / 100.0
        if 0 <= s <= 1:
            return float(s)
        return None
    s = str(s).strip().rstrip("%")
    try:
        v = float(s)
        if v > 1:
            return v / 100.0
        return v
    except ValueError:
        return None


def position_group(pos) -> str:
    """Map G/D/M/F to GK/DEF/MID/FWD."""
    if pd.isna(pos):
        return "UNK"
    p = str(pos).strip().upper()
    return {"G": "GK", "D": "DEF", "M": "MID", "F": "FWD"}.get(p, "UNK")


def per90(series: pd.Series, minutes: pd.Series) -> pd.Series:
    """Vectorized (stat / minutes) * 90; NaN if minutes < 1."""
    minutes = minutes.astype(float)
    mask = minutes >= 1
    out = pd.Series(np.nan, index=series.index, dtype=float)
    out.loc[mask] = (series.loc[mask].astype(float) / minutes.loc[mask]) * 90
    return out
