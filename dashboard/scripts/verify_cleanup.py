#!/usr/bin/env python3
"""Run after cleanup to verify: single compare list, no legacy refs, all nav targets exist."""

from __future__ import annotations

import re
import sys
from pathlib import Path

DASHBOARD = Path(__file__).resolve().parent.parent
PAGES_DIR = DASHBOARD / "pages"


def main() -> int:
    errors: list[str] = []
    warnings: list[str] = []

    # 1) No old compare list or state.py compare usage
    for py in DASHBOARD.rglob("*.py"):
        if "scripts" in str(py) or "__pycache__" in str(py):
            continue
        text = py.read_text(encoding="utf-8", errors="replace")
        if "compare_list_main" in text or "compare_list_main.json" in text:
            errors.append(f"{py.relative_to(DASHBOARD)}: references compare_list_main (should use scouts)")
        # Only error if utils.state import includes compare-related names (profile-only is fine)
        if "from dashboard.utils.state import" in text:
            imp = re.search(r"from dashboard\.utils\.state import\s*\(([^)]+)\)", text, re.DOTALL)
            if imp:
                imported = imp.group(1)
                if re.search(r"add_to_compare|get_compare_list|init_compare_list|display_compare_widget|clear_compare|get_compare_count|remove_from_compare|is_in_compare", imported):
                    errors.append(f"{py.relative_to(DASHBOARD)}: imports compare from utils.state (should use scouts.compare_state)")

    # 2) No legacy sidebar rendering in code (report/doc can mention it)
    for py in [DASHBOARD / "scouts" / "layout.py", DASHBOARD / "tactics" / "layout.py", DASHBOARD / "review" / "layout.py"]:
        if not py.exists():
            continue
        if py.name == "layout.py" and "scouts" in str(py):
            if "render_scouts_sidebar" in py.read_text(encoding="utf-8", errors="replace"):
                errors.append(f"{py.relative_to(DASHBOARD)}: still defines render_scouts_sidebar (should be removed)")
        if "tactics" in str(py) or "review" in str(py):
            warnings.append(f"Legacy layout exists: {py.relative_to(DASHBOARD)} (consider removing if unused)")

    # 3) Every page_link / switch_page target under dashboard/pages/ exists
    for py in DASHBOARD.rglob("*.py"):
        if "scripts" in str(py) or "__pycache__" in str(py):
            continue
        text = py.read_text(encoding="utf-8", errors="replace")
        for m in re.finditer(r'(?:page_link|switch_page)\s*\(\s*["\']([^"\']+)["\']', text):
            target = m.group(1).strip()
            if target == "app.py":
                continue
            if target.startswith("pages/") and target.endswith(".py"):
                path = DASHBOARD / target
                if not path.exists():
                    errors.append(f"{py.relative_to(DASHBOARD)}: links to missing {target}")

    # 4) Sidebar lists only existing pages
    sidebar_py = DASHBOARD / "utils" / "sidebar.py"
    if sidebar_py.exists():
        text = sidebar_py.read_text(encoding="utf-8", errors="replace")
        for m in re.finditer(r'page_link\s*\(\s*["\'](pages/[^"\']+\.py)["\']', text):
            target = m.group(1)
            if not (DASHBOARD / target).exists():
                errors.append(f"sidebar.py: links to missing {target}")

    # 5) Expected page files present
    expected = [
        "2_📋_Profile.py", "3_⚖️_Compare.py", "4_🎯_Shortlist.py", "5_📊_Explore.py",
        "6_🏆_Teams.py", "8_🔎_Discover.py", "9_🏟️_Team_Directory.py", "10_📐_Tactical_Profile.py",
        "11_⚔️_Opponent_Prep.py", "12_📊_League_Trends.py",
    ]
    for name in expected:
        if not (PAGES_DIR / name).exists():
            errors.append(f"Missing page: pages/{name}")

    for w in warnings:
        print("WARN:", w)
    for e in errors:
        print("ERROR:", e)

    if errors:
        print("\nVerification failed:", len(errors), "error(s).")
        return 1
    print("Verification passed: no legacy compare refs, all nav targets exist, expected pages present.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
