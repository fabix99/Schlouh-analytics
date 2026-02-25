"""Scouts dashboard compare list persistence (SM.4).

Stores player_ids and optionally season/competition per player for full fidelity.
"""

import json
import pathlib
from typing import List, Dict, Any, Optional

_SCOUTS_DIR = pathlib.Path(__file__).parent
_COMPARE_LIST_SCOUTS_FILE = _SCOUTS_DIR / "compare_list_scouts.json"
MAX_PLAYERS = 5


def load_scouts_compare_list() -> List[int]:
    """Load compare list (player IDs) from JSON file. Returns [] on missing or error."""
    if not _COMPARE_LIST_SCOUTS_FILE.exists():
        return []
    try:
        with open(_COMPARE_LIST_SCOUTS_FILE, "r") as f:
            data = json.load(f)
        if isinstance(data, list):
            return [int(x) for x in data if isinstance(x, (int, float))][:MAX_PLAYERS]
        ids = data.get("player_ids", data.get("entries", []))
        if not ids:
            return []
        if isinstance(ids[0], dict):
            return [int(e["player_id"]) for e in ids if isinstance(e.get("player_id"), (int, float))][:MAX_PLAYERS]
        return [int(x) for x in ids if isinstance(x, (int, float))][:MAX_PLAYERS]
    except Exception:
        return []


def load_scouts_compare_entries() -> List[Dict[str, Any]]:
    """Load compare list as list of {player_id, season, competition_slug}. Fills defaults for missing."""
    if not _COMPARE_LIST_SCOUTS_FILE.exists():
        return []
    try:
        with open(_COMPARE_LIST_SCOUTS_FILE, "r") as f:
            data = json.load(f)
        entries = data.get("entries", [])
        if entries:
            return [
                {
                    "player_id": int(e.get("player_id", e) if isinstance(e, dict) else e),
                    "season": e.get("season", ""),
                    "competition_slug": e.get("competition_slug", ""),
                }
                for e in entries[:MAX_PLAYERS]
            ]
        ids = data.get("player_ids", data if isinstance(data, list) else [])
        return [{"player_id": int(x), "season": "", "competition_slug": ""} for x in ids if isinstance(x, (int, float))][:MAX_PLAYERS]
    except Exception:
        return []


def save_scouts_compare_list(ids: List[int], seasons_by_id: Optional[Dict[int, Dict[str, str]]] = None) -> None:
    """Persist compare list. If seasons_by_id is provided, save as entries with season/competition_slug."""
    try:
        _SCOUTS_DIR.mkdir(parents=True, exist_ok=True)
        ids = ids[:MAX_PLAYERS]
        if seasons_by_id:
            entries = [
                {
                    "player_id": pid,
                    "season": seasons_by_id.get(pid, {}).get("season", ""),
                    "competition_slug": seasons_by_id.get(pid, {}).get("competition", ""),
                }
                for pid in ids
            ]
            with open(_COMPARE_LIST_SCOUTS_FILE, "w") as f:
                json.dump({"player_ids": ids, "entries": entries}, f, indent=0)
        else:
            with open(_COMPARE_LIST_SCOUTS_FILE, "w") as f:
                json.dump({"player_ids": ids}, f, indent=0)
    except Exception:
        pass
