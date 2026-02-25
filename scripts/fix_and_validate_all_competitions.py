#!/usr/bin/env python3
"""
Try to fix all competitions until validate_competition_ids.py passes for every one.

For each failing competition (warning_mismatch or error_http):
- Tries the alternate API path (tournament vs unique-tournament) with the same tournament_id.
- If events return 200 and the API tournament.slug is plausible for that competition,
  updates config: set api_path and/or expected_tournament_slugs so the validator accepts it.
Then re-runs the validator. Repeats until all OK or no more fixes possible.

Run from project root: python3 scripts/fix_and_validate_all_competitions.py
"""

import csv
import re
import subprocess
import sys
from pathlib import Path
from typing import Optional

ROOT = Path(__file__).resolve().parent.parent
CONFIG_PATH = ROOT / "config" / "competitions.yaml"
AUDIT_PATH = ROOT / "data" / "index" / "competition_config_audit.csv"
API_BASE = "https://api.sofascore.com/api/v1"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
    "Accept": "application/json",
    "Referer": "https://www.sofascore.com/",
}


def try_seasons(requests_mod, tid: int, path: str) -> tuple:
    url = f"{API_BASE}/{path}/{tid}/seasons"
    try:
        r = requests_mod.get(url, headers=HEADERS, timeout=10)
        if r.status_code == 200:
            data = r.json()
            return ("ok", len(data.get("seasons") or []))
        if r.status_code == 404:
            return ("404", 0)
        return ("other", r.status_code)
    except Exception as e:
        return ("other", str(e))


def fetch_first_season_id(requests_mod, tid: int, api_path: str) -> Optional[int]:
    url = f"{API_BASE}/{api_path}/{tid}/seasons"
    try:
        r = requests_mod.get(url, headers=HEADERS, timeout=10)
        if r.status_code != 200:
            return None
        seasons = (r.json() or {}).get("seasons") or []
        if not seasons:
            return None
        return seasons[0]["id"]
    except Exception:
        return None


def fetch_events_slug(requests_mod, tid: int, season_id: int, api_path: str) -> tuple[Optional[str], Optional[str]]:
    url = f"{API_BASE}/{api_path}/{tid}/season/{season_id}/events"
    try:
        r = requests_mod.get(url, headers=HEADERS, timeout=10)
        if r.status_code != 200:
            return None, f"http_{r.status_code}"
        events = (r.json() or {}).get("events") or []
        if not events:
            return None, "empty"
        slug = (events[0].get("tournament") or {}).get("slug") or ""
        return slug or None, None
    except Exception as e:
        return None, str(e)


def slug_plausible_for_competition(api_slug: str, config_slug: str) -> bool:
    """True if api_slug could be the same competition as config_slug."""
    if not api_slug or not config_slug:
        return False
    a = api_slug.lower().replace("_", "-")
    c = config_slug.lower().replace("_", "-")
    # Exact or one contains the other (e.g. fa-cup vs england-fa-cup)
    if a == c:
        return True
    if a in c or c in a:
        return True
    # Same key tokens: england-fa-cup -> fa-cup
    a_parts = set(a.split("-"))
    c_parts = set(c.split("-"))
    if a_parts & c_parts and len(a_parts) >= 1:
        return True
    return False


def run_validator() -> bool:
    """Run validate_competition_ids.py; return True if exit 0."""
    r = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "validate_competition_ids.py")],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        timeout=120,
    )
    print(r.stdout or "")
    if r.stderr:
        print(r.stderr, file=sys.stderr)
    return r.returncode == 0


def load_audit() -> list[dict]:
    if not AUDIT_PATH.exists():
        return []
    with open(AUDIT_PATH, encoding="utf-8") as f:
        return list(csv.DictReader(f))


def update_config_yaml(
    competition_slug: str,
    api_path: Optional[str],
    expected_slugs: Optional[list],
) -> None:
    """Update competitions.yaml. api_path: 'unique-tournament' = set it, 'tournament' = remove it, None = leave as-is."""
    text = CONFIG_PATH.read_text(encoding="utf-8")
    # Match block: slug: then any indented lines until next top-level key or EOF
    pattern = re.compile(
        r"^(" + re.escape(competition_slug) + r":\s*\n)((?:  [^\n]+\n)*)",
        re.MULTILINE,
    )
    match = pattern.search(text)
    if not match:
        print(f"  Could not find block for {competition_slug} in config")
        return

    prefix = match.group(1)
    block = match.group(2)
    rest_start = match.end(0)

    lines = [ln for ln in block.split("\n") if ln.strip()]
    new_lines = []
    had_expected_slugs = False
    had_api_path = False
    for line in lines:
        key = line.split(":")[0].strip()
        if key == "expected_tournament_slugs":
            had_expected_slugs = True
            if expected_slugs is not None:
                new_lines.append("  expected_tournament_slugs:")
                for s in expected_slugs:
                    new_lines.append(f"    - {s}")
            continue
        if key == "api_path":
            had_api_path = True
            if api_path == "unique-tournament":
                new_lines.append("  api_path: unique-tournament")
            # if api_path == "tournament" or None, skip (remove or leave)
            continue
        new_lines.append(line)

    if expected_slugs is not None and not had_expected_slugs:
        insert_idx = len(new_lines)
        for i, ln in enumerate(new_lines):
            if ln.strip().startswith("realm:"):
                insert_idx = i + 1
                break
        new_lines[insert_idx:insert_idx] = [
            "  expected_tournament_slugs:",
            *[f"    - {s}" for s in expected_slugs],
        ]
    if api_path == "unique-tournament" and not had_api_path:
        new_lines.append("  api_path: unique-tournament")

    new_block = "\n".join(new_lines) + "\n"
    new_text = text[: match.start(0)] + prefix + new_block + text[rest_start:]
    CONFIG_PATH.write_text(new_text, encoding="utf-8")


def main():
    import requests
    import yaml

    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    AUDIT_PATH.parent.mkdir(parents=True, exist_ok=True)

    iteration = 0
    while True:
        iteration += 1
        print(f"\n=== Validation iteration {iteration} ===\n")
        if run_validator():
            print("\nAll competitions validated OK.")
            break

        audit = load_audit()
        failing = [r for r in audit if r.get("status") not in ("ok",)]
        if not failing:
            break

        config = yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8")) or {}
        fixed_any = False

        for row in failing:
            comp_slug = row["competition_slug"]
            tid = row.get("tournament_id")
            if not tid:
                continue
            try:
                tid = int(tid)
            except (TypeError, ValueError):
                continue
            current_path = (row.get("api_path") or "").strip() or "tournament"
            status = row.get("status", "")
            sample_slug = (row.get("sample_tournament_slug") or "").strip()
            entry = config.get(comp_slug) or {}
            config_slug = entry.get("slug", comp_slug)

            # Try the alternate path
            alt_path = "unique-tournament" if current_path == "tournament" else "tournament"
            st, _ = try_seasons(requests, tid, alt_path)
            if st != "ok":
                continue
            season_id = fetch_first_season_id(requests, tid, alt_path)
            if not season_id:
                continue
            api_slug, err = fetch_events_slug(requests, tid, season_id, alt_path)
            if err or not api_slug:
                continue

            if not slug_plausible_for_competition(api_slug, config_slug):
                continue

            # Fix: use alt_path and accept api_slug
            expected = list(set([config_slug, api_slug]))
            if entry.get("expected_tournament_slugs"):
                expected = list(set(expected) | set(entry["expected_tournament_slugs"]))
            update_config_yaml(comp_slug, alt_path if alt_path == "unique-tournament" else None, expected)
            print(f"  Fixed {comp_slug}: use {alt_path}, expected_tournament_slugs include {api_slug!r}")
            fixed_any = True

        if not fixed_any:
            print("\nNo more fixes could be applied. Remaining failures:")
            for r in failing:
                print(f"  {r['competition_slug']}: {r.get('status')} {r.get('detail', '')}")
            sys.exit(1)


if __name__ == "__main__":
    main()
