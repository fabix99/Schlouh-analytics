"""
Configuration for football visualization scripts.
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# Data paths
DATA_DERIVED = ROOT / "data" / "derived"
PLAYERS_DIR = DATA_DERIVED / "players"
APPEARANCES_PATH = DATA_DERIVED / "player_appearances.parquet"
INCIDENTS_PATH = DATA_DERIVED / "player_incidents.parquet"
PLAYERS_INDEX_PATH = ROOT / "data" / "index" / "players.csv"

# Output
OUTPUT_DIR = Path(__file__).resolve().parent / "output"
OUTPUT_CATEGORIES = [
    "01_single_game",
    "02_form",
    "03_profile",
    "04_comparison",
    "05_incidents",
    "06_percentile",
]

# Default test players (for scripts that need fixed examples)
DEFAULT_PLAYER_SLUG = "kylian-mbappe"
DEFAULT_PLAYER_SLUG_2 = "robert-lewandowski"

# Default test match (El Clasico 2025-10-26, Mbappé hat-trick)
DEFAULT_MATCH_ID = "14083729"

# Output format
OUTPUT_FORMAT = "png"  # "png" or "svg"
DPI = 150

# Global footnote for charts (data source)
DATA_SOURCE_FOOTNOTE = "Data: Sofascore. Stats normalized per 90 where stated."
