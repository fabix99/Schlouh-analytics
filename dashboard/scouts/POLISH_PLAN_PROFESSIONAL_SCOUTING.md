# Scouts Dashboard — Professional Polish Plan

**Goal:** Make the scouting dashboard look and feel like a premium, professional recruitment tool (e.g. Wyscout, Scout7, Opta-style interfaces) while keeping the existing Schlouh brand (dark + gold).

---

## 1. Brand & Visual Identity

### 1.1 Streamlit theme alignment
- **Current:** `config.toml` uses `primaryColor = "#00D4AA"` (teal) while CSS uses gold `#C9A840`. Streamlit-native elements (links, focus rings, some buttons) can show teal.
- **Action:** Set `primaryColor = "#C9A840"` in `.streamlit/config.toml` so all native UI (focus, selected tab, link underlines) matches the injected CSS gold.
- **Action:** Add `secondaryBackgroundColor = "#161B22"` and `backgroundColor = "#0D1117"` if not already exact match to `styles.py` tokens.

### 1.2 Sidebar branding
- **Current:** Footer says "Schlouh Scouts · Internal Use" and "Data sourced from SofaScore". No logo or app name block at top.
- **Action:** Add a compact **sidebar header block** (e.g. "SCOUTS" in gold, small tagline) using existing `.sb-brand` / `.sb-brand-name` classes so the sidebar has a clear product identity on every page.
- **Action:** Optionally add a small logo or icon above the nav; ensure it’s high-contrast and doesn’t clutter the nav.

### 1.3 Favicon and page titles
- **Action:** Ensure `page_icon` is consistent (🔎 for Discover, 📋 Profile, etc.) and consider a custom favicon (e.g. gold “S” or shield) in `config.toml` or via `st.set_page_config(..., favicon="path")` for a more product-like feel.

---

## 2. Typography & Spacing

### 2.1 Font stack
- **Current:** DM Sans (body), Oswald (headings) from Google Fonts. Good choice.
- **Action:** Ensure fallbacks are explicit everywhere: `'DM Sans', -apple-system, BlinkMacSystemFont, 'Segoe UI', system-ui, sans-serif` and that numeric columns use `font-variant-numeric: tabular-nums` (already on metrics; extend to dataframes where appropriate).

### 2.2 Section hierarchy
- **Current:** `.section-header` (Oswald, gold, uppercase, letter-spacing). Used well.
- **Action:** Introduce a **sub-section** class (e.g. `.section-sub`) for "Filter by statistics", "Quick Actions", etc.: same font, smaller size (0.72rem), muted color (#8B949E), no bottom border, margin below 0.5rem. Use consistently so the page has a clear visual hierarchy (hero → section → sub-section → content).

### 2.3 Block spacing
- **Action:** Standardise vertical rhythm: 1.25rem between major sections, 0.75rem between a section header and its content, 0.5rem between related controls (e.g. stat filter rows). Add a small spacing utility in CSS (e.g. `.mt-1` / `.mb-1`) or rely on consistent margins in existing classes.
- **Action:** Ensure `.block-container` padding is consistent on mobile (e.g. reduce horizontal padding on small viewports via a media query).

---

## 3. Component Consistency

### 3.1 Buttons
- **Current:** Primary = gold, secondary = dark with border. Good.
- **Action:** Use **primary** only for one main CTA per block (e.g. "Add to Shortlist", "Start Search"). Use secondary/default for "View Profile", "Add to Compare", "Clear filters" so the hierarchy is clear.
- **Action:** Add `help="..."` tooltips to every non-obvious button (e.g. "Add stat filter", "Clear stat filters", "Save Current Filter", "Reset to current season only", column template selector).

### 3.2 Cards (home, shortlist, profile)
- **Current:** Inline styles for cards (e.g. `background:#161B22; border:1px solid #30363D`). Some use `.info-card`, `.sim-card`, etc.
- **Action:** Replace repeated inline card styles with **single class** (e.g. `.scout-card`) and use it on Home cards, Shortlist player cards, Compare candidate cards. Ensures identical border-radius, padding, hover, and shadow.

### 3.3 Metrics (KPIs)
- **Current:** `st.metric()` styled via CSS. Looks good.
- **Action:** Where you show multiple metrics in a row (e.g. Discover footer: Players, Leagues, Seasons, Appearances), add the existing `.kpi-accent` div below the first row so the gold line reinforces the "dashboard" feel.
- **Action:** Ensure delta (if ever shown) uses success/warning/danger from TOKENS so it’s consistent.

### 3.4 Forms and inputs
- **Current:** Selects and number inputs styled in CSS.
- **Action:** Add **placeholder** text to every text input (e.g. "Filter name", "Search by player name") and **help** to every number input (e.g. "e.g. 0.3 for xG/90", "Minutes played this season").
- **Action:** For stat filter Min/Max, add a small hint under the first row: "Use decimals (e.g. 0.35 for xG/90, 85 for Pass %)."

### 3.5 Tables (dataframes)
- **Current:** Styled headers (gold, uppercase), striped rows, hover. Good.
- **Action:** Ensure **column header tooltips** where helpful: e.g. "Goals per 90 minutes", "Percentile vs same position in filtered pool". Use `column_config` in `st.dataframe` with `help` where supported (Streamlit 1.28+).
- **Action:** Consider **sticky header** for long tables (CSS: `thead th { position: sticky; top: 0; z-index: 1; }`) so when scrolling, headers stay visible.

### 3.6 Expanders
- **Current:** Styled in CSS. Used for Filters, "Also filter by percentile", Compare filters.
- **Action:** Use consistent expander titles: start with icon + short label (e.g. "⚙️ Filters", "📊 Also filter by percentile"). Avoid long sentences in the title; put explanation in `st.caption` inside the expander.

---

## 4. Copy & Microcopy

### 4.1 Page heroes
- **Current:** Title + one-line subtitle. Good.
- **Action:** Make subtitles **action-oriented** and consistent in tone:
  - **Discover:** "Set your criteria, filter by stats, and browse the table. Save presets for quick access."
  - **Profile:** "Full scouting report: radar, form, badges, and match context. Select a player below or from Find Players."
  - **Compare:** "Select 2–5 players for side-by-side stats, radars, and tactical fit. Cross-league stats are adjusted for fairness."
  - **Shortlist:** "Track targets with status and notes. Add from Find Players or Profile; compare and schedule observations from here."

### 4.2 Section labels
- **Action:** Use sentence case for section headers where it reads better (e.g. "Filter by statistics" not "FILTER BY STATISTICS" if you introduce a sub-section style that isn’t all-caps). Keep main `.section-header` as uppercase for consistency.
- **Action:** Replace generic "Results" with "Player list" or "Search results" on Discover so it’s clear what the table is.

### 4.3 Empty states
- **Action:** Every empty state should: (1) explain why it’s empty, (2) suggest the next action. Examples:
  - Shortlist empty: "Your shortlist is empty. **Find Players** to search by position and stats, then add candidates here."
  - Compare &lt; 2 players: "Add at least 2 players to compare. Use the search above or add from your **Shortlist**."
  - No search results (Discover): "No players match your filters. Try widening league/season, lowering min. minutes, or relaxing stat filters."
  - Profile no player: "Select a player from the list below or open one from **Find Players**."

### 4.4 Captions and hints
- **Action:** Add one-line captions under every major control block (filters, stat filters, table, export): what the data is, what "one row" means, and what scope (e.g. "Current season, default leagues. One row per player per season.").
- **Action:** Tooltips for jargon: "xG/90 = expected goals per 90 minutes", "Percentile = rank vs other players in same position in this pool."

### 4.5 Buttons and links
- **Action:** Use consistent verbs: "View profile" not "Profile", "Add to shortlist" not "Shortlist", "Add to compare" not "Compare". Primary action first (e.g. "Add to Shortlist" then "View Profile").
- **Action:** Nav labels already good (Find Players, Profile, Compare, Shortlist). Keep them.

---

## 5. Empty, Loading & Error States

### 5.1 Loading
- **Current:** `st.spinner("Loading ...")` on data load. Good.
- **Action:** Use **specific** messages per page: "Loading scouting data…", "Loading player profile…", "Loading comparison data…", "Loading shortlist…". Avoid generic "Loading…".
- **Action:** For slow operations (e.g. first load of full season stats), consider a **skeleton** or a short message: "Preparing player pool…" so the user knows the app is working.

### 5.2 Empty data
- **Action:** Replace bare `st.info("No data loaded.")` with a short **empty-state block**: icon, title, one sentence, one CTA button (e.g. "Go to Find Players"). Use the same pattern on every page (e.g. `.empty-state` class with centered content and a primary button).
- **Action:** Discover: if filters return 0 rows, show "No players match your criteria" + "Reset filters" or "Clear stat filters" so the user can recover without guessing.

### 5.3 Errors
- **Current:** Some `st.error()` with message; Retry button on Discover data failure. Good.
- **Action:** Standardise: **title** ("Data unavailable"), **short reason** ("Could not load player pool."), **suggested action** ("Check your connection and retry, or contact support.") and one **Retry** button that clears cache and reruns.
- **Action:** Never expose raw stack traces; log them server-side if needed.

### 5.4 Edge cases
- **Action:** Profile: player_id in URL but not in DB → clear message "Player not found" + link to Find Players.
- **Action:** Compare: URL `?compare=id1,id2` but one id not in data → show which player(s) are missing and offer "Remove from comparison" or "Open Find Players".
- **Action:** Shortlist: players not in current dataset (transferred out) → already noted in caption; add a small **warning banner** at top of shortlist if any are missing: "X player(s) on your shortlist are not in the current data (e.g. moved leagues). They’re still listed but stats may be outdated."

---

## 6. Navigation & Wayfinding

### 6.1 Breadcrumbs / context
- **Action:** On Profile and Compare, add a **one-line context** under the hero: e.g. "Comparing 3 players · 2025-26 · Premier League" or "Profile · [Player name] · [Team] · [League]". Helps scouts know scope at a glance.

### 6.2 Back / primary action
- **Current:** "← Back to Discover" etc. on Compare and Shortlist. Good.
- **Action:** Keep these. Ensure they’re visually secondary (not primary button) and placed in a consistent position (e.g. top of page or just below hero).

### 6.3 Shortlist and Compare counts in sidebar
- **Action:** In the sidebar, show **Shortlist (N)** and **Compare (N)** in the nav labels or in a small widget under the links so users always see how many are in the basket without opening the page.

### 6.4 Deep links
- **Current:** `?player_id=`, `?compare=id1,id2`, `?seasons=`, `?leagues=`. Good.
- **Action:** Document in a short "Share & bookmark" note (e.g. in Discover caption): "You can share this search by copying the URL (filters and stat filters are in the link)."

---

## 7. Data Presentation

### 7.1 Tables
- **Action:** Ensure **sorting** is obvious (e.g. caption: "Sort by clicking column headers."). Consider default sort label (e.g. "Sorted by rating (desc)" in caption when default).
- **Action:** **Pagination:** keep "Showing X–Y of Z · Page N of M" and Prev/Next. Ensure disabled state is clear (greyed out, not clickable).
- **Action:** **Export:** keep "Export full filtered table (CSV)". Add a tooltip: "Includes all rows in the current filtered list, not only the current page."

### 7.2 Numbers
- **Action:** Consistently round: 2 decimals for rates (xG/90, %), 0 for integers (goals, apps, age). Use existing formatting helpers everywhere.
- **Action:** Percentiles: show as integer + "th" (e.g. 87th) via `format_percentile`; ensure no "NaN" or "—" in table for percentile when value exists.

### 7.3 Charts (radar, form)
- **Current:** Plotly with dark theme. Good.
- **Action:** Ensure every chart has a **title or caption** (e.g. "Performance vs position (percentiles)") and legend when multiple series. Use PLOTLY_LAYOUT_TACTICS (or scouts-specific layout) everywhere.
- **Action:** Radar: if a stat is missing, show "N/A" or hide the axis label rather than a broken segment.

### 7.4 Metrics and KPIs
- **Action:** Use `st.metric(label, value)` with clear labels: "Players", "Leagues", "Seasons", "Appearances". No delta unless it adds meaning (e.g. "vs last week" for a live dashboard).

---

## 8. Accessibility

### 8.1 Existing
- **Current:** `accessibility.py` with ARIA, contrast helpers, focus styles in CSS. Good.
- **Action:** Ensure `inject_accessibility_css()` is always called (e.g. from `inject_css()` in layout). No exceptions.

### 8.2 Focus and keyboard
- **Action:** Verify focus outline (gold 2px) on all interactive elements: buttons, links, inputs, selectboxes. No `outline: none` without a visible replacement.
- **Action:** Where possible, ensure logical tab order (filters → table → actions). Streamlit order is DOM order; avoid breaking it with hidden elements that are focusable.

### 8.3 Labels
- **Action:** Every input and control must have an associated label (visible or `label_visibility="collapsed"` with `help`). Use `st.number_input(..., label="Min value", ...)` etc.; avoid unlabeled inputs.

### 8.4 Contrast
- **Action:** Run contrast check on gold on dark (#C9A840 on #0D1117, #161B22). If below 4.5:1 for small text, consider a slightly lighter gold for body text and keep current gold for headings and accents only.

---

## 9. Performance & Perceived Performance

### 9.1 Caching
- **Current:** `@st.cache_data(ttl=3600)` on data loaders and Discover aggregate. Good.
- **Action:** Ensure no heavy computation runs outside cache (e.g. percentiles only in cached function). Profile one full Discover flow (load → filter → stat filter) and fix any N+1 or redundant work.

### 9.2 Reruns
- **Action:** Avoid rerun on every keystroke: use forms for "Save filter", "Add to shortlist" where appropriate. Stat filters already update on rerun; that’s acceptable if response is fast.
- **Action:** If dataframe render is slow with 5k+ rows, consider **virtualisation** or cap display to 500 rows with "Showing first 500; export CSV for full list."

### 9.3 First load
- **Action:** Show hero and nav immediately; data below spinner. Consider a small "Data source: SofaScore · Updated [date]" in footer so users know data is batch-updated, not live.

---

## 10. Onboarding & Help

### 10.1 First-time hints
- **Action:** Optional: a **dismissible banner** on first visit (cookie/session): "Tip: Save your favourite filters in Find Players to load them in one click." Dismiss = set session state and hide for the session.

### 10.2 Inline help
- **Action:** Add `help` to: league selector ("Default: top leagues + UEFA. Add cups or other competitions to expand."), season selector, min minutes, stat filter Min/Max, percentile expander, column template selector, "Save Current Filter", "Share this search".

### 10.3 Documentation
- **Action:** Add a **Scouts user guide** (e.g. `docs/SCOUTS_USER_GUIDE.md` or a "Help" expander on Home): workflow (Find → Profile → Compare → Shortlist), what percentiles mean, what "cross-league adjusted" means, how to save and share filters. Link from sidebar footer: "How to use · Data source: SofaScore".

---

## 11. Config & Deployment Polish

### 11.1 Streamlit config
- **Action:** Set `primaryColor = "#C9A840"` and align all theme colours with `styles.py`.
- **Action:** Consider `[theme] font = "DM Sans"` if Streamlit supports custom font (or leave default and rely on CSS override).
- **Action:** `[browser] gatherUsageStats = false` already set. Keep it.

### 11.2 Environment
- **Action:** Document required env vars (e.g. `REVIEW_APP_URL` for Shortlist links) in README or `.env.example`. No hardcoded localhost in code for production.

### 11.3 Error tracking
- **Action:** If Sentry or similar is used elsewhere, add the scouts app so client errors (e.g. failed load) are logged. Don’t show Sentry details to the user.

---

## 12. Page-by-Page Checklist

### Home (app.py)
- [ ] Hero subtitle action-oriented and consistent.
- [ ] All three cards use same class (e.g. `.scout-card`); no inline card styles.
- [ ] Buttons: primary only for main CTA if desired; secondary for "View Profile".
- [ ] Top performers: empty state has CTA "Find Players".
- [ ] Coverage metrics: add `.kpi-accent` under first metric row.
- [ ] Sidebar: add header block "SCOUTS" (or logo) + footer "How to use · SofaScore".

### Discover (1_🔎_Discover.py)
- [ ] Hero subtitle as in section 4.1.
- [ ] Filter panel: all inputs have `help`; sub-section label for "Filter by statistics".
- [ ] Stat filters: hint "Use decimals (e.g. 0.35 for xG/90)." under first row.
- [ ] "Results" → "Player list" or "Search results"; caption explains sorting and scope.
- [ ] Table: column_config with `help` for key columns; sticky header if possible.
- [ ] Empty result: message + "Reset filters" / "Clear stat filters".
- [ ] Export button tooltip: "Full filtered list (all pages)."
- [ ] Share URL caption: "Copy URL to share this search (includes filters)."

### Profile (2_📋_Profile.py)
- [ ] Hero when no player: subtitle and CTA as in 4.3.
- [ ] When player selected: one-line context under hero (name, team, league).
- [ ] All sections have clear sub-headers/captions (percentile context, radar, form).
- [ ] Empty states for badges, match log, similar players: message + suggestion.
- [ ] Back to Discover / Shortlist / Compare links consistent and secondary style.

### Compare (3_⚖️_Compare.py)
- [ ] Hero subtitle as in 4.1.
- [ ] "Select 2–5 players" and "Add at least N more" messages consistent.
- [ ] Cross-league notice: one clear info box with short explanation.
- [ ] Table and radars: titles/captions; no raw stat names without explanation.
- [ ] Empty state: "Add players from search or Shortlist" with link.

### Shortlist (4_🎯_Shortlist.py)
- [ ] Hero subtitle as in 4.1.
- [ ] Empty state: message + "Find Players" button (primary).
- [ ] Warning banner when any shortlisted player not in dataset.
- [ ] Status cards and player cards use shared card class.
- [ ] Next steps (Schedule, Notebook): links clear; open in new tab if external app.

---

## 13. Priority Order (Suggested)

**Phase 1 — Quick wins (1–2 days)**  
1. Theme: set `primaryColor = "#C9A840"` in config.  
2. Copy: update all page hero subtitles and empty-state messages.  
3. Tooltips: add `help` to every filter, stat filter, and main button.  
4. One shared card class and use it on Home + Shortlist (and Compare cards if applicable).

**Phase 2 — Consistency (2–3 days)**  
5. Sub-section typography and spacing (CSS + usage).  
6. Standardise empty/error pattern (message + CTA).  
7. Table: captions, column_config help, sticky header.  
8. KPI accent line under first metric row where relevant.

**Phase 3 — Depth (2–3 days)**  
9. Sidebar header (brand block).  
10. Context line on Profile and Compare (player/compare scope).  
11. Short guide (markdown) + link in footer.  
12. Dismissible first-time tip (optional).  
13. Contrast and a11y pass (focus, labels, contrast ratio).

**Phase 4 — Polish (1–2 days)**  
14. Skeleton or clearer loading message on first load.  
15. Deep-link documentation in Discover caption.  
16. Final pass: button hierarchy (primary vs secondary), no inline card styles, all placeholders and hints in place.

---

## 14. Success Criteria

- **Visual:** No teal in UI; gold and dark only. All cards and buttons from design system.  
- **Copy:** Every page has a clear hero, every empty state has a CTA, every control has a tooltip or caption where needed.  
- **Behaviour:** No unhandled errors visible to user; empty and error states are consistent and helpful.  
- **Perception:** A new user can complete "find a player → open profile → add to shortlist → compare two" without guessing; labels and hints explain scope and actions.

---

*Document version: 1.0. Use this as a living checklist; tick items as implemented and add new ones as the product evolves.*
