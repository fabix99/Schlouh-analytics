"""Single source of truth for project and data paths.

Use this module whenever you need the project root or data directory.
If you move the dashboard or repo layout changes, update only this file.
"""

from __future__ import annotations

import pathlib

# dashboard/utils/paths.py -> dashboard/utils -> dashboard -> project root
PROJECT_ROOT = pathlib.Path(__file__).resolve().parent.parent.parent

# Optional: uncomment and adjust if you want one place for data paths
# DATA_DIR = PROJECT_ROOT / "data"
# PROCESSED_DIR = DATA_DIR / "processed"
# DERIVED_DIR = DATA_DIR / "derived"
