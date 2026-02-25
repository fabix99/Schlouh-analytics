#!/usr/bin/env python3
"""
Validate Sofascore tournament IDs in config/competitions.yaml by calling the API.
Tries both /tournament/{id}/seasons and /unique-tournament/{id}/seasons (website uses
e.g. .../uefa-champions-league/7#id:76953 → 7 = competition, 76953 = season).
For each OK config, samples events and verifies tournament.slug matches expectations.
Outputs: data/index/competition_config_audit.csv (machine-readable report).
Requires: requests, pyyaml. Run from project root.
"""
import csv
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CONFIG_PATH = ROOT / "config" / "competitions.yaml"
INDEX_DIR = ROOT / "data" / "index"
AUDIT_PATH = INDEX_DIR / "competition_config_audit.csv"
API_BASE = "https://api.sofascore.com/api/v1"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
    "Accept": "application/json",
    "Referer": "https://www.sofascore.com/",
}


def try_seasons(requests_mod, tid: int, path: str) -> tuple:
    """Return (status, n_seasons). status in ('ok', '403', '404', 'other')."""
    url = f"{API_BASE}/{path}/{tid}/seasons"
    try:
        r = requests_mod.get(url, headers=HEADERS, timeout=10)
        if r.status_code == 200:
            data = r.json()
            n = len(data.get("seasons") or [])
            return ("ok", n)
        if r.status_code == 403:
            return ("403", 0)
        if r.status_code == 404:
            return ("404", 0)
        return ("other", r.status_code)
    except Exception as e:
        return ("other", str(e))


def get_api_path(entry: dict, status_t: str, status_u: str) -> str:
    """Return 'tournament' or 'unique-tournament' based on which path succeeded."""
    if status_t == "ok":
        return "tournament"
    if status_u == "ok":
        return "unique-tournament"
    return ""


def fetch_first_season_id(requests_mod, tid: int, api_path: str):
    """Return first season id from /seasons response, or None."""
    url = f"{API_BASE}/{api_path}/{tid}/seasons"
    try:
        r = requests_mod.get(url, headers=HEADERS, timeout=10)
        if r.status_code != 200:
            return None
        data = r.json()
        seasons = data.get("seasons") or []
        if not seasons:
            return None
        return seasons[0]["id"]
    except Exception:
        return None


def fetch_events_sample(requests_mod, tid: int, season_id: int, api_path: str):
    """Fetch events for one season. Returns (events_list, None) or (None, error_msg)."""
    url = f"{API_BASE}/{api_path}/{tid}/season/{season_id}/events"
    try:
        r = requests_mod.get(url, headers=HEADERS, timeout=10)
        if r.status_code != 200:
            return None, f"http_{r.status_code}"
        data = r.json()
        events = data.get("events") or []
        return events, None
    except Exception as e:
        return None, str(e)


def expected_slugs_for_entry(entry: dict, slug: str) -> set:
    """Set of allowed tournament.slug values from config."""
    allowed = entry.get("expected_tournament_slugs")
    if allowed is not None:
        return set(s for s in allowed if s)
    return {entry.get("slug", slug)}


def main():
    try:
        import yaml
        import requests
    except ImportError as e:
        print(f"Need: pip install pyyaml requests\n{e}")
        sys.exit(1)

    if not CONFIG_PATH.exists():
        print(f"Not found: {CONFIG_PATH}")
        sys.exit(1)

    with open(CONFIG_PATH, encoding="utf-8") as f:
        config = yaml.safe_load(f)

    if not config:
        print("Empty config")
        sys.exit(0)

    print("Validating: try /tournament/{id}/seasons, then /unique-tournament/{id}/seasons if 404")
    print("Then sampling events to verify tournament.slug matches config.")
    print("-" * 75)

    ok_tournament = []
    ok_unique = []
    fail_403 = []
    fail_both_404 = []
    other = []

    audit_rows = []

    for slug, entry in config.items():
        if not isinstance(entry, dict):
            continue
        tid = entry.get("tournament_id")
        if tid is None:
            continue

        status_t, n_t = try_seasons(requests, tid, "tournament")
        status_u, n_u = try_seasons(requests, tid, "unique-tournament")
        config_prefers_unique = entry.get("api_path") == "unique-tournament"

        if config_prefers_unique and status_u == "ok":
            ok_unique.append((slug, tid, n_u))
            api_path = "unique-tournament"
            n_seasons = n_u
        elif status_t == "ok":
            ok_tournament.append((slug, tid, n_t))
            api_path = "tournament"
            n_seasons = n_t
        elif status_t == "404" and status_u == "ok":
            ok_unique.append((slug, tid, n_u))
            api_path = "unique-tournament"
            n_seasons = n_u
        elif status_t == "403" or status_u == "403":
            fail_403.append((slug, tid))
            audit_rows.append({
                "competition_slug": slug,
                "tournament_id": tid,
                "api_path": "",
                "status": "error_http",
                "n_seasons": 0,
                "sample_tournament_slug": "",
                "expected_slugs": "",
                "detail": "403",
            })
            continue
        elif status_t == "404" and status_u == "404":
            fail_both_404.append((slug, tid))
            audit_rows.append({
                "competition_slug": slug,
                "tournament_id": tid,
                "api_path": "",
                "status": "error_http",
                "n_seasons": 0,
                "sample_tournament_slug": "",
                "expected_slugs": "",
                "detail": "404_both",
            })
            continue
        else:
            other.append((slug, tid, f"tournament: {status_t} {n_t}"))
            audit_rows.append({
                "competition_slug": slug,
                "tournament_id": tid,
                "api_path": "",
                "status": "error_http",
                "n_seasons": 0,
                "sample_tournament_slug": "",
                "expected_slugs": "",
                "detail": f"tournament={status_t} unique={status_u}",
            })
            continue

        # For OK entries: sample events and verify tournament.slug
        expected = expected_slugs_for_entry(entry, slug)
        season_id = fetch_first_season_id(requests, tid, api_path)
        if not season_id:
            audit_rows.append({
                "competition_slug": slug,
                "tournament_id": tid,
                "api_path": api_path,
                "status": "error_no_events",
                "n_seasons": n_seasons,
                "sample_tournament_slug": "",
                "expected_slugs": ",".join(sorted(expected)),
                "detail": "no_season_id",
            })
            continue

        events, err = fetch_events_sample(requests, tid, season_id, api_path)
        if err:
            if err == "http_404" and api_path == "unique-tournament":
                # Events 404 is common for unique-tournament; discovery can use scheduled-events fallback
                audit_rows.append({
                    "competition_slug": slug,
                    "tournament_id": tid,
                    "api_path": api_path,
                    "status": "ok",
                    "n_seasons": n_seasons,
                    "sample_tournament_slug": "",
                    "expected_slugs": ",".join(sorted(expected)),
                    "detail": "events_404_use_scheduled_discovery",
                })
            else:
                audit_rows.append({
                    "competition_slug": slug,
                    "tournament_id": tid,
                    "api_path": api_path,
                    "status": "error_http",
                    "n_seasons": n_seasons,
                    "sample_tournament_slug": "",
                    "expected_slugs": ",".join(sorted(expected)),
                    "detail": err,
                })
            continue
        if not events:
            audit_rows.append({
                "competition_slug": slug,
                "tournament_id": tid,
                "api_path": api_path,
                "status": "error_no_events",
                "n_seasons": n_seasons,
                "sample_tournament_slug": "",
                "expected_slugs": ",".join(sorted(expected)),
                "detail": "empty_events",
            })
            continue

        sample_slug = (events[0].get("tournament") or {}).get("slug") or ""
        if sample_slug in expected:
            status = "ok"
        else:
            status = "warning_mismatch"
        audit_rows.append({
            "competition_slug": slug,
            "tournament_id": tid,
            "api_path": api_path,
            "status": status,
            "n_seasons": n_seasons,
            "sample_tournament_slug": sample_slug,
            "expected_slugs": ",".join(sorted(expected)),
            "detail": "" if status == "ok" else f"api_slug={sample_slug}",
        })
    # End for slug, entry

    for slug, tid, n in ok_tournament:
        row = next((r for r in audit_rows if r["competition_slug"] == slug and r["api_path"] == "tournament"), None)
        st = row["status"] if row else "ok"
        print(f"  {st.upper():12} [tournament]     {slug:<38} id={tid:<6} seasons={n}")
    for slug, tid, n in ok_unique:
        row = next((r for r in audit_rows if r["competition_slug"] == slug and r["api_path"] == "unique-tournament"), None)
        st = row["status"] if row else "ok"
        print(f"  {st.upper():12} [unique-tourn.]  {slug:<38} id={tid:<6} seasons={n}")
    for slug, tid in fail_403:
        print(f"  403           {slug:<55} id={tid}")
    for slug, tid in fail_both_404:
        print(f"  404           {slug:<55} id={tid} (both paths)")
    for slug, tid, msg in other:
        print(f"  ERR           {slug:<55} id={tid} {msg}")

    print("-" * 75)
    total_ok = len(ok_tournament) + len(ok_unique)
    n_warn = sum(1 for r in audit_rows if r["status"] == "warning_mismatch")
    print(f"OK (tournament): {len(ok_tournament)} | OK (unique-tournament): {len(ok_unique)} | 403: {len(fail_403)} | 404 both: {len(fail_both_404)} | Other: {len(other)}")
    if n_warn:
        print(f"  Slug mismatch (warning_mismatch): {n_warn} — check competition_config_audit.csv")
    if ok_unique:
        print("\nFor OK (unique-tournament), add to competitions.yaml:  api_path: unique-tournament")

    INDEX_DIR.mkdir(parents=True, exist_ok=True)
    if audit_rows:
        with open(AUDIT_PATH, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=["competition_slug", "tournament_id", "api_path", "status", "n_seasons", "sample_tournament_slug", "expected_slugs", "detail"])
            w.writeheader()
            w.writerows(audit_rows)
        print(f"\nWrote {AUDIT_PATH}")

    if fail_both_404 or other:
        sys.exit(1)
    if n_warn > 0:
        sys.exit(1)


if __name__ == "__main__":
    main()
