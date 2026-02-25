#!/usr/bin/env python3
"""
Run the AI Scout test suite in the browser and capture every question–answer pair.

Usage:
  1. Start the dashboard: streamlit run dashboard/app.py --server.port 8080
  2. Run this script: python dashboard/pages/run_ai_scout_tests.py

Output: dashboard/pages/AI_Scout_test_results.md
"""

import re
import sys
from pathlib import Path

# Project root
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

QUESTIONS_PATH = Path(__file__).parent / "AI_Scout_test_questions.md"
RESULTS_PATH = Path(__file__).parent / "AI_Scout_test_results.md"
BASE_URL = "http://localhost:8080"
CLEAR_CHAT_EVERY_N = 20
WAIT_REPLY_TIMEOUT_MS = 30_000


def parse_questions(md_path: Path) -> list[tuple[int, str, str]]:
    """Extract (number, question_text, category) from AI_Scout_test_questions.md."""
    text = md_path.read_text(encoding="utf-8")
    questions = []
    current_category = ""
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#") or line.startswith("*") or line == "---":
            if line.startswith("## ") and not re.match(r"^## \d+\.", line):
                current_category = line.replace("##", "").strip()
            continue
        m = re.match(r"^(\d+)\.\s+(.+)$", line)
        if m:
            num, q = int(m.group(1)), m.group(2).strip()
            questions.append((num, q, current_category))
    return questions


def run_tests(
    questions: list[tuple[int, str, str]],
    base_url: str = BASE_URL,
    results_path: Path = RESULTS_PATH,
    clear_every_n: int = CLEAR_CHAT_EVERY_N,
    headless: bool = False,
    delay_after_answer_sec: float = 0,
) -> tuple[list[tuple[int, str, str, str]], list[int], str]:
    """
    Use Playwright to run each question in the AI Scout chat and capture answers.
    Returns (results, failed_indices, summary).
    """
    from playwright.sync_api import sync_playwright

    results = []
    failed = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=headless)
        context = browser.new_context()
        page = context.new_page()

        try:
            page.goto(base_url, wait_until="networkidle", timeout=15_000)
        except Exception as e:
            browser.close()
            return (
                [],
                list(range(1, len(questions) + 1)),
                f"Could not reach dashboard at {base_url}. Start it with: streamlit run dashboard/app.py --server.port 8080. Error: {e}",
            )

        # Open AI Scout page: direct URL then fallback to sidebar click
        base = base_url.rstrip("/")
        for attempt, url in enumerate([
            f"{base}/5_🤖_AI_Scout",
            f"{base}/5_%F0%9F%A4%96_AI_Scout",
        ]):
            try:
                page.goto(url, wait_until="domcontentloaded", timeout=12_000)
                page.wait_for_timeout(3500)
                if page.locator("textarea").count() > 0 or page.get_by_placeholder("Ask about").count() > 0:
                    break
            except Exception:
                pass
        else:
            try:
                page.goto(base_url, wait_until="networkidle", timeout=12_000)
                page.get_by_role("link", name=re.compile(r"AI Scout", re.I)).first.click()
                page.wait_for_load_state("networkidle")
                page.wait_for_timeout(4000)
            except Exception as e:
                browser.close()
                return (
                    [],
                    list(range(1, len(questions) + 1)),
                    f"Could not open AI Scout page: {e}",
                )

        # Chat input: try exact placeholder then ASCII ellipsis, then any textarea
        chat_input = None
        for placeholder in ["Ask about players, teams, or matches…", "Ask about players, teams, or matches..."]:
            loc = page.get_by_placeholder(placeholder)
            if loc.count() > 0:
                chat_input = loc.first
                break
        if chat_input is None and page.locator("textarea").count() > 0:
            chat_input = page.locator("textarea").last
        if chat_input is None:
            browser.close()
            return (
                [],
                list(range(1, len(questions) + 1)),
                "Could not find AI Scout chat input. Is the AI Scout page visible?",
            )
        try:
            chat_input.wait_for(state="visible", timeout=10_000)
        except Exception:
            browser.close()
            return (
                [],
                list(range(1, len(questions) + 1)),
                "Chat input did not become visible in time.",
            )

        for i, (num, question, category) in enumerate(questions):
            try:
                chat_input.fill(question)
                page.keyboard.press("Enter")

                # Wait for spinner to disappear
                try:
                    page.get_by_text("Searching database and asking AI…").wait_for(
                        state="hidden", timeout=WAIT_REPLY_TIMEOUT_MS
                    )
                except Exception:
                    pass
                # Wait for actual reply: last message must not be the spinner text (Streamlit replaces it)
                spinner_text = "Searching database and asking AI…"
                for _ in range(25):  # up to ~12.5s
                    page.wait_for_timeout(500)
                    last_msg = ""
                    for selector in [
                        '[data-testid="stChatMessage"]',
                        'div[class*="stChatMessage"]',
                        'section[data-testid="stChatMessage"]',
                    ]:
                        loc = page.locator(selector)
                        if loc.count() > 0:
                            last_msg = (loc.last.inner_text() or "").strip()
                            break
                    if last_msg and last_msg != spinner_text and len(last_msg) >= 10:
                        break
                page.wait_for_timeout(800)

                # Last assistant message
                last_msg = ""
                for selector in [
                    '[data-testid="stChatMessage"]',
                    'div[class*="stChatMessage"]',
                    'section[data-testid="stChatMessage"]',
                ]:
                    loc = page.locator(selector)
                    if loc.count() > 0:
                        last_msg = (loc.last.inner_text() or "").strip()
                        break
                if not last_msg:
                    # Fallback: last block in main that looks like a message (skip "user" label)
                    blocks = page.locator('[data-testid="stVerticalBlock"]').all()
                    for b in reversed(blocks):
                        t = b.inner_text()
                        if len(t) > 20 and "Ask about" not in t and question[:30] not in t:
                            last_msg = t
                            break
                if not last_msg:
                    last_msg = "[Could not capture reply]"
                    failed.append(num)

                results.append((num, question, last_msg, category))

            except Exception as e:
                results.append((num, question, f"[Error: {e}]", category))
                failed.append(num)

            # Clear chat periodically to avoid context overflow
            if clear_every_n and (i + 1) % clear_every_n == 0 and (i + 1) < len(questions):
                try:
                    page.get_by_role("button", name="Clear chat").click()
                    page.wait_for_timeout(800)
                except Exception:
                    pass

            # Delay after each answer to stay under API rate limits
            if delay_after_answer_sec > 0 and (i + 1) < len(questions):
                page.wait_for_timeout(int(delay_after_answer_sec * 1000))

        browser.close()

    summary = (
        f"Ran {len(results)}/{len(questions)} questions. "
        f"Failed to capture or error: {len(failed)} (indices: {failed[:20]}{'…' if len(failed) > 20 else ''})."
    )
    return results, failed, summary


def write_results(
    results: list[tuple[int, str, str, str]],
    results_path: Path,
    failed: list[int],
    summary: str,
) -> None:
    """Write AI_Scout_test_results.md."""
    from datetime import date

    lines = [
        "# AI Scout test results – " + date.today().isoformat(),
        "",
        summary,
        "",
        "---",
        "",
    ]
    for num, question, answer, category in results:
        lines.append(f"## {num}. {question}")
        if category:
            lines.append(f"*Category:* {category}")
        lines.append("")
        lines.append("**Answer:**")
        lines.append("")
        # Indent multi-line answers for readability
        for a in answer.splitlines():
            lines.append("    " + a if a.strip() else "")
        lines.append("")
    results_path.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    import argparse
    parser = argparse.ArgumentParser(description="Run AI Scout test suite in browser")
    parser.add_argument("--url", default=BASE_URL, help="Dashboard base URL")
    parser.add_argument("--questions", type=Path, default=QUESTIONS_PATH, help="Questions markdown file")
    parser.add_argument("--out", type=Path, default=None, help="Output markdown file (default: same dir as questions, AI_Scout_test_results.md or _v2)")
    parser.add_argument("--clear-every", type=int, default=CLEAR_CHAT_EVERY_N, help="Clear chat every N questions")
    parser.add_argument("--delay", type=float, default=0, help="Seconds to wait after each answer before next question (for API rate limits)")
    parser.add_argument("--headed", action="store_true", help="Show browser window")
    parser.add_argument("--dry-run", action="store_true", help="Only parse questions, do not run browser")
    args = parser.parse_args()

    questions_path = args.questions
    if not questions_path.is_absolute():
        questions_path = (PROJECT_ROOT / questions_path).resolve()
    if not questions_path.exists():
        print(f"Questions file not found: {questions_path}")
        sys.exit(1)

    if args.out is None:
        args.out = questions_path.parent / (
            "AI_Scout_test_results_v2.md" if "v2" in questions_path.name else "AI_Scout_test_results.md"
        )

    questions = parse_questions(questions_path)
    print(f"Parsed {len(questions)} questions from {questions_path}")

    if args.dry_run:
        for num, q, cat in questions[:5]:
            print(f"  {num}. [{cat}] {q[:60]}…")
        if len(questions) > 5:
            print("  ...")
        sys.exit(0)

    if args.delay > 0:
        print(f"Running tests with {args.delay}s delay after each answer (API rate limit)...")
    else:
        print("Running tests in browser (use --headed to watch)...")
    results, failed, summary = run_tests(
        questions,
        base_url=args.url,
        results_path=args.out,
        clear_every_n=args.clear_every,
        headless=not args.headed,
        delay_after_answer_sec=args.delay,
    )
    if not results and failed:
        print(summary)
        sys.exit(1)
    write_results(results, args.out, failed, summary)
    print(f"Results written to {args.out.resolve()}")
    print(summary)
    if failed:
        print("Failed question numbers:", failed)


if __name__ == "__main__":
    main()
