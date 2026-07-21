# Starling — QA & Polish Pass Report

**Date:** 2026-07-20 · **Scope:** `Github-Trending/site/` only · **Data:** `site/data/latest.json` (as_of 2026-07-18, 3 windows × 50 repos) — restored byte-for-byte after simulations, see [Data safety](#data-safety).

## Summary

Overall the site is in very good shape. All core behavior — window switching, link building, escaping, the map's bubble↔leaderboard sync, heatmap drill-downs and metric toggle, compare pinning with color-matched overlay, loading/error/empty states — worked correctly on first test with real data, and the shared-helper architecture (`Starling.esc` / `repoUrl` / dynamic axes) held up under adversarial checks, including an in-memory XSS injection test that rendered inertly as text.

**14 issues found → 13 fixed, 1 partially fixed** (heatmap sub-label contrast: floor raised from 2.69:1 to 3.59:1; full 4.5:1 AA needs a palette-ramp change, which is out of bounds for this pass). The two most user-visible defects were a **site-wide horizontal scrollbar** at every viewport width (ticker negative margin) and a **broken heatmap layout on mobile** (cells lost their Today/Week/Month mapping). Ten structural/design items are cataloged under [Proposed but not done](#proposed-but-not-done) for the owner to decide.

Final state: zero console errors on all five pages (favicon 404 included — a favicon was added), zero horizontal overflow at 390 / 768 / 1280 px, all failure and empty states verified, `prefers-reduced-motion` verified, keyboard pass verified.

> **Update:** the owner approved all ten proposals; nine were implemented in a second pass — see [Round 2 — proposals implemented](#round-2--proposals-implemented-2026-07-20) at the end of this report.

A read-only sub-agent ran an independent static audit in parallel with the browser sweep; its findings were reconciled into the lists below (it independently re-discovered the contrast and focus-loss bugs, and contributed the About-page link, dead-code, and mobile-heatmap items).

---

## Findings (severity-ranked)

### 1. HIGH — Site-wide horizontal page overflow (Fixed)
**Pages:** Board, Map, Heatmap, Compare (all pages with a ticker) · **File:** `site/assets/theme.css:37`
**Repro (pre-fix):** open any page at any width → horizontal scrollbar; `document.documentElement.scrollWidth` (1256) > viewport (1249); ticker box measured `left:-22, right:+22` past the viewport.
**Cause:** `.ticker{margin:0 -22px}` assumes the ticker sits *inside* the padded `.wrap`, but every page places it *outside* as a full-width sibling, so the negative margin pushes it 22px past both edges.
**Fix:** removed the negative margin. Visual result is identical (full-bleed strip); verified `scrollWidth == clientWidth` on all five pages at 390, 768, and 1280 px. (about.html never overflowed — it has no ticker — which corroborated the diagnosis.)

### 2. MEDIUM — Heatmap cell text fails contrast on mid-intensity cells (Fixed, with a documented ceiling)
**Page:** Heatmap · **File:** `site/heatmap.html:168`
**Repro (pre-fix):** default "Stars gained" view → TypeScript/Today cell measured **2.69:1** (white text on mid-green), Rust/Week 2.81:1; 5 cells < 4.5:1.
**Cause:** text flipped to white at `t > 0.55`, but on the `#E4F2EC → #0B7A57` ramp, dark ink outperforms white until t ≈ 0.9 (crossover math: white only reaches useful contrast on the deepest greens — 5.3:1 at t=1.0 vs ink's 3.5:1 there).
**Fix:** white flips at `t > 0.9`; sub-label uses `--muted` only on pale cells (`t ≤ 0.2`), `--ink` in the mid band, `rgba(255,255,255,.92)` on the darkest. Verified post-fix: worst main text **4.04:1** (all cells pass the 3:1 large-text bar with margin; most pass 4.5), worst sub-label **3.59:1** (was 2.69). The hottest cells look unchanged (white on deep green), preserving the design. Reaching a strict 4.5:1 everywhere is impossible with any single flip point on this ramp — see Proposed #2.

### 3. MEDIUM — Heatmap mobile layout loses the column mapping (Fixed)
**Page:** Heatmap ≤ 720 px · **File:** `site/heatmap.html:41-50` (CSS), `:167,:170,:175-176,:179` (markup)
**Repro (pre-fix):** at 390px the three window headers wrapped into a 2+1 block above *all* rows, and each language's Month cell sat alone on a second line — nothing indicated which cell was which window (confirmed by screenshot).
**Fix:** every cell (and drill-down list and column footer) now carries a tiny `wtag` window label ("24H/7D/30D") that is `display:none` on desktop and shown only inside the ≤720px media query, where the now-meaningless header row is hidden. Desktop rendering verified unchanged (tags hidden, 4-column grid, headers visible).

### 4. MEDIUM — Pin/unpin loses keyboard focus (Fixed)
**Page:** Compare · **File:** `site/compare.html:147-151`
**Repro (pre-fix):** Tab to any pin button, press Enter → `togglePin` rebuilds the rail's `innerHTML`, the focused button is destroyed, focus silently falls to `<body>` (WCAG 2.4.3 papercut). Independently flagged by the static-audit sub-agent.
**Fix:** after re-render, focus is restored to the same button via its stable `data-pin` key. Verified: after a real click on a pin, `document.activeElement` is that pin (`aria-pressed="true"`). (The restored button can never be disabled: pinning marks it "on", unpinning frees a slot.)

### 5. LOW — Map lede promises a click behavior that doesn't exist (Fixed)
**Page:** Map · **File:** `site/map.html:71`
**Repro (pre-fix):** copy read "Hover **or click** a point to sync it with the board" — bubbles have no click handler (hover alone does the sync).
**Fix:** copy now reads "Hover a point to sync it with the board." (Wiring an actual click action is listed under Proposed #8 instead — that would be a feature addition.)

### 6. LOW — Board headline stuck on "Today's" in Week/Month view (Fixed)
**Page:** Board · **File:** `site/index.html:82,113`
**Repro (pre-fix):** switch to Week or Month → the h2 still said "Today's biggest movers" above weekly/monthly data.
**Fix:** the heading now derives from the shared `WLABEL` map per window ("Today's / This week's / This month's biggest movers"); the Day view renders exactly the original string, so the approved look is unchanged.

### 7. LOW — "1 repos" pluralization (Fixed)
**Page:** Heatmap · **File:** `site/heatmap.html:130,138,140,147,179`
**Repro (pre-fix):** several cells with a single repo (e.g. C/Week) rendered "1 repos" in the cell, tooltip, and aria-label.
**Fix:** tiny `nRepos()` helper ("1 repo" / "N repos") used in cell text, tooltip, and column footers. Verified: 7 cells now correctly singular, zero "1 repos" remaining.

### 8. LOW — Internal window keys leaked into empty-state copy (Fixed)
**Pages:** Board / Map / Compare · **Files:** `site/index.html:118`, `site/map.html:111`, `site/compare.html:128`
**Repro (pre-fix):** with an empty window the message interpolated the raw key: "Nothing cleared the *day* bar." / "…cleared the *week* threshold…" — "the this week bar" class of grammar was lurking.
**Fix:** messages now use the shared `WSUB` labels: "Nothing cleared the 24h bar." / "No repositories cleared the 24h threshold this run — check back tomorrow." Verified live in the empty-window simulation.

### 9. LOW — About's external link: inert `rel`, inconsistent behavior (Fixed)
**Page:** About · **File:** `site/about.html:150`
**Repro (pre-fix):** "source on GitHub" had `rel="noopener"` but no `target="_blank"` (making the rel a no-op) and opened same-tab — the only external link on the site to do so.
**Fix:** added `target="_blank"`, matching every other external link.

### 10. LOW — Dead code / dead markup (Fixed)
- `site/compare.html` — removed the unused `<div class="tt" id="tt">` (compare has no tooltip; the div was also missing the `role="status"` its siblings carry — moot once deleted).
- `site/index.html:122` — removed unused `lc` variable in the hero render.
- `site/assets/data.js:89-90` — `chrome(currentPage)` dropped its never-used parameter; comment corrected (it claimed to wire nav state that is actually static `aria-current` in each page's HTML).

### 11. POLISH — Favicon added (optional item, taken)
**Files:** all five pages, line 7.
The prompt marked the `favicon.ico` 404 as benign but allowed a trivial favicon. Added a one-line inline `data:` SVG star in the brand accent `#3B49DF` to each `<head>` — no new asset file, and the console is now fully silent on every page.

---

## Changes made (file-by-file)

| File | Line(s) | Change |
|---|---|---|
| `site/assets/theme.css` | 37 | `.ticker` — removed `margin:0 -22px` (site-wide horizontal overflow) |
| `site/assets/data.js` | 89-90 | `chrome()` — dropped unused param; corrected comment |
| `site/index.html` | 7 | favicon link |
| | 82, 113 | `#ledeH` + per-window headline text |
| | 118 | empty-state copy via `WSUB` |
| | 122 | removed dead `lc` var |
| `site/map.html` | 7 | favicon link |
| | 71 | lede copy: removed false "or click" affordance |
| | 111 | empty-state copy via `WSUB` |
| `site/heatmap.html` | 7 | favicon link |
| | 42, 45-50 | `.wtag` rule + mobile media-query block (show tags, hide `.mh`, hide footer spacer) |
| | 130 | `nRepos()` pluralization helper |
| | 138, 140, 147, 179 | pluralized cell text / tooltip / column feet |
| | 167, 170, 175-176, 179 | `wtag` spans in cells, drill-downs, column feet |
| | 168 | contrast thresholds: white at `t>0.9`; sub-label muted→ink→white bands (0.2 / 0.9), white sub alpha .92 |
| `site/compare.html` | 7 | favicon link |
| | (was 112) | removed dead `#tt` div |
| | 128 | empty-state copy via `WSUB` |
| | 147-151 | `togglePin` — keyboard focus restored after rail re-render |
| `site/about.html` | 7 | favicon link |
| | 150 | `target="_blank"` on the source-on-GitHub link |

Intentional-by-design items were left untouched: ticker duplication/`aria-hidden`/`tabindex="-1"`, `repoUrl()` construction, all escaping, dynamic map axes, Compare's in-app rail/chips, light-only theme, Google-Fonts loading, no heatmap window tab.

---

## Proposed but not done (owner's call)

> **Status: approved and implemented in Round 2** (except #10, which required no change) — kept here for the original rationale; see the addendum for what was done.

1. **`--faint` (#8A93A0) fails 4.5:1 on paper/panel** for small informational text it's applied to (board column headers, map axis tick values and card hints, heatmap column headers, ranks, footers) — ≈2.7:1 on `--paper`. A token darkening (e.g. `#6B7480` ≈ 4.5:1) would fix it everywhere, but that's a palette change (the Ticker tokens are locked per the design direction).
2. **Full 4.5:1 AA on heatmap cells** needs a darker ramp end (e.g. `#065138`) or larger sub-label type; the current ramp caps the worst sub-label at ~3.6:1 no matter which text color is chosen.
3. **Segmented controls use `role="tablist"`/`tab` without the rest of the APG tab pattern** (no `aria-controls`, no `role="tabpanel"`, no arrow-key roving) on Board/Map/Compare windows and the heatmap metric toggle. Either complete the pattern or demote to plain buttons with `aria-pressed`.
4. **Landmarks/headings:** map/heatmap/compare/about have no `<main>`; index's `<main id="board">` has its landmark role overridden by `role="list"` at render time; four pages have no `<h1>` (the lede is an `h2`). A small semantic restructure would fix all three.
5. **`aria-live="polite"` on the whole `#board`** re-announces ~50 rows on every window switch. Moving it to a compact status node (e.g. `.wmeta`) would quiet it, but would stop load/error states from being announced — needs a deliberate choice (this is why it wasn't changed).
6. **Heatmap legend precision:** "share of window" is, strictly, *value ÷ column leader* (per-column max normalization). The second legend line ("color normalized within each column") is accurate; consider "share of column leader" if precision matters.
7. **Compare growth curves don't change with the selected window** — sparks are whole-history (byte-identical across windows in the data), so only rail membership and table numbers respond to the window tabs. The footer says this, but a hint near the chart (or window-scoped curves) would remove the surprise.
8. **Map bubbles have `cursor:pointer` but no click action**, and heavily overlapped bubbles can't be hovered at their centers (discovered when an automated hover on an occluded bubble was intercepted by its neighbor — inherent to scatter plots; the synced leaderboard is the reliable path). A click → open-repo or click → scroll-leaderboard-row action would make the pointer cursor honest.
9. **"top 50 of 50" meta line** (Board) is redundant while the pipeline reports `count` == list length; if `count` ever carries the pre-cap total, the copy becomes meaningful. Pipeline-side, out of scope here.
10. **Board rank vs Map leaderboard order can diverge by design** (pipeline day-ranking divides by `elapsed_days`; the Map re-sorts by raw `pct_gain`, labeled "by velocity"). With current data the orders happen to agree; flagged for awareness only.

## Couldn't verify / assumptions

- External GitHub URLs were validated **by construction** against `owner`/`name` for all 150 repos in all views (and `full_name` cross-checked) — not by fetching github.com.
- Screen-reader output was verified structurally (aria attributes/states), not with real AT; keyboard testing was done with real Tab/Enter key events.
- Touch behavior (tap-to-hover synthesis on the map/heatmap) was not tested on a physical device.
- `prefers-reduced-motion` was verified via Playwright media emulation (`animation-name: none` under reduce; `scroll` otherwise), not an OS-level setting.
- The Claude-in-Chrome extension was not connected in this environment; the sweep was driven with the Playwright MCP browser (Chromium) instead. The escaping check additionally used an in-memory (never persisted) injected `<img onerror>`/`<script>` payload, which rendered as inert text.

## Data safety — restoration confirmed

`site/data/latest.json` SHA-256 before, backup, and after restore are identical:
`2aa0cf9640073e2c9b4a04471b7f64e5f8b2dda20e825a6fd54b2cc1a10e4aac`
`cmp` confirmed byte-for-byte equality ("RESTORED BYTE-FOR-BYTE"), `git status` shows the file unmodified, and both temp copies (`latest.json.bak`, `latest.json.moved`, kept only in the session scratchpad, never inside `site/`) were deleted. `site/data/archive/` was never touched. No test artifacts remain in `site/` or the workspace (Playwright screenshots/logs were deleted).

**Simulations run (serially, one agent):**
1. *Load failure:* moved `latest.json` out → all four data pages rendered the friendly `Starling.fail` message in their correct containers (`#board`, `#plot`, `#matrix`, `#rail`): "Couldn't load the latest data (HTTP 404). It refreshes once a day — try again shortly."
2. *Empty window:* wrote a variant with `windows.day.repos = []`, `count = 0` → Board/Map/Compare showed their empty-state copy (no crashes; Week/Month still rendered), Heatmap rendered the Day column as dashed "—" cells with a "+0★ across 0 repos" footer.

## How it was served & tested

```
cd Github-Trending/site
python -m http.server 8080          # http://127.0.0.1:8080/
```

Driven via the Playwright MCP browser (Chromium): every page loaded at 1280×900, 768×900, and 390×844; all window tabs, the metric toggle, row expands, pins/unpins, rail opens, similar-mover chips exercised; real hovers for map sync and both tooltips; real Tab-key pass (ticker links correctly skipped, 2px accent focus ring visible, no positive tabindex); media-emulated reduced-motion; per-window link audits (hero, 49 rows, 50 leaderboard rows, 9 drill-down links, compare table) all resolving to `https://github.com/<owner>/<name>`. Final regression sweep across all five pages after the last edit: **0 console errors, 0 page errors**.

---

## Round 2 — proposals implemented (2026-07-20)

The owner reviewed the ten proposals and approved them all. Nine touched code; #10 was awareness-only (the Board/Map ordering difference is by design — the Map's leaderboard is explicitly "by velocity"). Where a proposal offered alternatives, the choice made is noted. `data/latest.json` was not touched in this round.

**1. `--faint` darkened for AA — `assets/theme.css:3`.** Token changed `#8A93A0 → #66707C`. The proposal's example `#6B7480` was measured first and *missed* on `--paper` (4.29:1), so the shipped value was chosen by measurement: **4.56:1 on paper, 5.03:1 on panel** (verified live against the rendered `.thead`). Every faint-text consumer (column headers, axis ticks, hints, ranks, footers, heatmap `.mh`) now passes 4.5:1. The hardcoded `#AEB5C0` in heatmap's `.mh span` was folded into `var(--faint)` (`heatmap.html:16`).

**2. Heatmap full 4.5:1 AA — `heatmap.html:40` (heatbar), `:123-129`, `:168`.** Ramp end deepened `#0B7A57 → #065138` as proposed. Straight interpolation still has a mid-luminance band (bg luminance ≈ .183–.206) where *no* text color can reach 4.5:1, so a `heat()` remap makes the ramp **skip that band** (a ~5% luminance step at t=0.68, visually imperceptible — confirmed by screenshot). Text flips ink→white at the same t=0.68; the `.s` sub-label now inherits the cell color and its `opacity:.9` was removed (it was silently costing ~8% contrast). The former muted sub-label tier is gone — on tinted mid-cells no gray can pass AA, so sub-hierarchy is now carried by size alone. **Measured result: worst cell text ≥ 4.58:1 (stars), 6.49:1 (repos), 4.64:1 (avg velocity) — main and sub text, every cell, every metric.**

**3. APG tabs completed (chose "complete" over "demote") — `assets/data.js` (`segKeys`, wired in `chrome()`), all four tablists.** Roving tabindex (active tab `0`, others `-1`), ArrowLeft/Right/Up/Down + Home/End with focus-follows-activation; each tab got `aria-controls`, and each controlled region is now a labeled `role="tabpanel"`: `#boardPanel` (index), `#mapPanel` (map), `#matrix` (heatmap), `#desk` (compare). Verified with real key events: ArrowRight activates and focuses the next tab, Home returns, inactive tabs report `tabIndex -1`.

**4. Landmarks & headings — all five pages.** Every page now wraps its content in `<main>` (index's board reverted from `<main>` to a `<div>`, so `role="list"` no longer overrides a landmark; `about.html` wraps `.doc`). Each data page's lede was promoted `h2 → h1` (theme selector widened to `.lede h1, .lede h2` — `theme.css:60` — so the visual size is identical).

**5. Live-region rework — `index.html`, `assets/data.js`.** `aria-live="polite"` came off the full board list (no more ~50-row re-announcements per window switch); the `.wmeta` line is now `role="status"`, announcing the concise "Today · vs. yesterday · top 50 · since …" summary instead. The trade-off flagged in the proposal (losing load-failure announcements) was closed by giving the shared `Starling.fail()` error state `role="alert"` — verified present on the rendered error and benefiting all four pages. The board also drops `role="list"` while showing a non-list empty state (`index.html` empty branch).

**6. Heatmap legend precision — `heatmap.html:186`.** "share of window" → **"share of column leader"**, matching the actual per-column-max normalization.

**7. Compare chart honesty (chose "clearer hint" over window-scoped curves) — `compare.html:66,109`.** A visible note under the chart header: *"Curves plot % growth over each repo's full tracked history — the window tabs change the repo list, not the curves."* Window-scoping was rejected because Day-window curves would collapse to two-point lines (sparks are full-history; confirmed in the data).

**8. Map bubbles: click is now real — `map.html:71,190-198`.** Clicking a bubble scrolls its leaderboard row into view and focuses it (highlighting both via the existing sync). A late `mouseleave` fired by the scroll on stacked layouts was wiping the highlight, so the handler keeps it when focus sits on the matching row. Lede updated: "Hover a point to sync it with the board — click to jump to its row." Verified at desktop and 768px (row focused, bubble + row highlighted, row scrolled into view).

**9. "top 50 of 50" dedupe (UI-side; pipeline untouched) — `index.html:120`.** The "of N" clause now renders only when `count` exceeds the listed length: today reads "top 50 · since 2026-07-17", and becomes "top 50 of N" automatically if the pipeline ever reports the pre-cap total.

**10. No change** — divergence between pipeline rank and the Map's velocity sort is intentional and labeled in the UI; left as documented behavior.

**Round 2 verification:** full battery re-run — worst-case contrast audits across all three heatmap metrics, real arrow-key runs on two tablists, bubble-click behavior at two widths, in-memory empty-window and `fail()` regressions (role handling correct, content restores), 390px overflow probe on all five pages (all `0px`), landmark/h1/tabpanel presence on every page — **0 console errors, 0 page errors**. Two design-token values changed with owner approval (`--faint`, heat-ramp end); the project's design-direction memory was updated to match.
