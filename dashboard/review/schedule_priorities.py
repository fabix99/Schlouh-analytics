"""Persist schedule priorities (To scout, importance) for Review Schedule."""

import json
import pathlib

PRIORITIES_FILE = pathlib.Path(__file__).parent / "schedule_priorities.json"


def load_schedule_priorities() -> dict:
    """Load match_id -> { to_scout: bool, importance: str } from file."""
    if not PRIORITIES_FILE.exists():
        return {}
    try:
        with open(PRIORITIES_FILE, "r") as f:
            data = json.load(f)
        return {str(k): v for k, v in data.items()}
    except Exception:
        return {}


def save_schedule_priorities(priorities: dict) -> None:
    """Save priorities to file."""
    with open(PRIORITIES_FILE, "w") as f:
        json.dump(priorities, f, indent=2)
