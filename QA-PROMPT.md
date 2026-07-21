# TASK: QA + polish pass on the "Starling" website (do NOT redesign)

<!-- Reusable prompt. Feed this entire file to a Claude Fable 5 agent that can serve
     the site and drive it in a real browser. -->

You are doing a thorough quality-assurance and light-polish pass over a static
website. You have NO prior context on this project — everything you need is below.
Work conservatively: fix real defects and make minor polish tweaks, but DO NOT
redesign anything or change the visual identity. When in doubt, flag it in your
report instead of changing it.

## What the site is
"Starling" — a static site that surfaces the GitHub repositories gaining stars
fastest ("velocity" = % stars gained), updated daily. Location:
`Github-Trending/site/`. Plain HTML/CSS/JS, NO build step.

Pages (all in `site/`):
- `index.html`  — Board (the home / entry page). A "top mover" hero + a ranked
                  list. Day/Week/Month window tabs. A scrolling ticker strip.
- `map.html`    — Scatter plot of velocity (Y) vs total stars (X, log scale) +
                  a summary "tape" of KPIs + a leaderboard synced to the plot.
                  Day/Week/Month tabs.
- `heatmap.html`— "Sector rotation" matrix: languages (rows) × Today/Week/Month
                  (columns), each cell colored by its share of that column.
                  A "Color by" toggle (Stars gained / Repos / Avg velocity), and
                  each row expands to show the top repos driving it. Cell tooltips.
- `compare.html`— Master–detail: a left rail of repos, a detail panel, and a
                  "pin up to 4" overlay chart of normalized growth + a table.
                  Day/Week/Month tabs.
- `about.html`  — A static methodology explainer.

Shared assets:
- `assets/theme.css` — design tokens + shared chrome (masthead, ticker, the
                       Board/Map/Heatmap/Compare nav switcher, window control,
                       tooltip, panels, legend, loading/error/empty states).
- `assets/data.js`   — a `Starling` global: `load()` (fetches
                       `./data/latest.json`), plus helpers `esc, fmt, pctOf,
                       langColor, readable, sparkline, repoUrl, buildTicker, win,
                       generatedDate, chrome, fail`, and `LANG`/`WLABEL` maps.
- `data/latest.json` — the live data. Shape: {version, as_of, generated_at,
                       windows:{day,week,month}}; each window {boundary_date,
                       count, repos:[...]}; each repo has: rank, full_name, owner,
                       name, html_url, avatar_url, description, language, topics[],
                       stars, abs_gain, pct_gain, elapsed_days, summary, spark[].

IMPORTANT: the pages `fetch()` `./data/latest.json`, so they MUST be served over
HTTP — opening via file:// will fail to load data. Serve it:
    cd Github-Trending/site
    python -m http.server 8080
then browse http://127.0.0.1:8080/ . Use your browser automation to drive it and
read the console.

## File index — where everything lives
Paths below are relative to the repo/workspace root (the directory that contains
both `Github-Trending/` and `design-mockups/`). Run commands from there. The QA
target is entirely under `Github-Trending/site/`.

    Github-Trending/
      site/                     <-- THE QA TARGET (only edit files in here)
        index.html              Board page (home / entry point)
        map.html                Map page (scatter + leaderboard)
        heatmap.html            Heatmap page (sector-rotation matrix)
        compare.html            Compare page (master–detail + pin overlay)
        about.html              Methodology explainer (static)
        assets/
          theme.css             SHARED design tokens + chrome (all pages link it)
          data.js               SHARED `Starling` helpers + data loader (all pages)
        data/
          latest.json           the live data the pages fetch() — back up before
                                any simulation; restore byte-for-byte after
          archive/              dated JSON snapshots; the pages do NOT use these —
                                leave them alone
      QA-PROMPT.md              this prompt (for reference)
      QA-REPORT.md              <-- WRITE YOUR REPORT HERE (create it; outside site/)

    OUT OF SCOPE — do not read for the task, do not touch:
      design-mockups/           (workspace root) earlier prototypes — NOT the site
      Github-Trending/github_trending/     Python data pipeline / backend
      Github-Trending/tests, tools, logs, docs, pyproject.toml, uv.lock, .venv/
      Github-Trending/github_trending.duckdb*   the database

## On-page element index — the DOM handles to drive/test
Shared on every page: `#clock` (masthead date), `#tickTrack` (the ticker track),
`nav.views` (the Board/Map/Heatmap/Compare + "How it works" switcher). The three
data pages also share `#tt` (the hover tooltip, `position:fixed`, pointer-events
none) and a window control `.seg` containing `button[data-win="day|week|month"]`.
`Starling.fail(id, err)` renders the load-error message into the per-page container
named in parentheses below.

- index.html (Board): `#board` (list container — ALSO the error/empty target
  "board"), `#wlabel`, `#wcount`; hero `.hero` with `a.name`; rows `.row` with
  `.id .nm a`; window tabs `.seg button[data-win]`.
- map.html: `#tape` (KPI strip), `#plot` (scatter SVG — error target "plot"),
  `#lb` (leaderboard), `#legend`; bubbles `circle.bub[data-i]`, leaderboard links
  `#lb a.row[data-i]` (bubble↔row sync by matching data-i); window `.seg button[data-win]`.
- heatmap.html: `#matrix` (the grid — error target "matrix"); metric toggle
  `#metricSeg button[data-k="stars|count|avgvel"]`; rows `.rowh[data-l]`, cells
  `.cell[data-w][data-l]`, drill-downs `.expand[data-exp]` (repo links inside).
  NOTE: no window tab here — by design it shows all three windows as columns.
- compare.html: `#rail` (repo list — error target "rail"), `#detail`, `#cmpChart`,
  `#cmpTable`, `#cmpCount`; rail open buttons `.open[data-open]`, pin buttons
  `.pin[data-pin]` (max 4), detail external link `.ghlink`; window `.seg button[data-win]`.
- about.html: static content, `nav.views`, and back-to-board links only.

`Starling` API surface (in `assets/data.js`) you may need: `load()`, `win(w)`,
`esc()`, `fmt()`, `pctOf()`, `langColor()`, `readable()`, `sparkline()`,
`repoUrl()`, `buildTicker()`, `generatedDate()`, `chrome()`, `fail()`, plus the
`LANG`, `WLABEL`, `WSUB`, `WSINCE` maps.

## Intentional decisions — treat these as CORRECT BY DESIGN; do NOT "fix" them
- The ticker strip is a decorative, duplicated marquee (items rendered twice for a
  seamless loop). Its container is `aria-hidden="true"` and its links are
  `tabindex="-1"` ON PURPOSE — mouse-clickable convenience; keyboard/screen-reader
  users navigate via the main board/lists. Do NOT expose it to AT, de-duplicate it,
  or make its links focusable.
- Repo links are built by `Starling.repoUrl(r)` =
  `https://github.com/<encodeURIComponent(owner)>/<encodeURIComponent(name)>`,
  deliberately NOT trusting `html_url`. Keep this.
- Every user-content string (repo name/owner/summary/description/topics/language)
  is escaped with `Starling.esc()` before being put in innerHTML. NEVER remove
  escaping; if you add any interpolation, escape it too and build URLs via repoUrl.
- The Map's scatter axes are COMPUTED from each window's data (the month window
  reaches >1000% velocity and ~100k stars). Do NOT hardcode axis ranges.
- In Compare, the left-rail repo names and the "Similar movers" chips are in-app
  controls that open the DETAIL panel — they are intentionally NOT external links.
  The GitHub link lives in the detail header ("View on GitHub ↗") and the compare
  table. Do NOT turn rail names into external links.
- The site is intentionally LIGHT-only (it replaced a former dark theme). Do NOT
  add a dark mode.
- Fonts load from Google Fonts CDN — intentional. Do NOT inline or swap them.
- The Heatmap intentionally has NO Day/Week/Month tab — it shows all three windows
  as columns. That's correct.
- A `favicon.ico` 404 in the console is expected/benign (there's no favicon yet).
  Do NOT treat it as a bug to chase. You MAY add a simple favicon if trivial, but
  it is optional and not a defect.

## What you MAY change (defects + minor polish)
- Broken or dead controls (a button/tab/toggle/link that does nothing).
- JavaScript errors/exceptions in the console (favicon 404 excepted).
- Broken links / wrong hrefs / leftover `href="#"` placeholders.
- Accessibility defects: missing/incorrect focus states, missing labels, bad
  contrast, keyboard traps, wrong aria-selected/aria-current/aria-expanded.
- Responsive/overflow bugs (horizontal scroll, clipped content, broken grids).
- Copy typos and unclear error/empty-state wording.
- Minor polish: small spacing/alignment nits, hover/focus affordances, empty-state
  microcopy — ONLY if the approved look is preserved.

## What you MUST NOT change (propose in the report instead)
- Palette, typography, or layout structure; anything that alters the visual design.
- Adding or removing pages/views/features.
- Restructuring `assets/theme.css` or `assets/data.js` (keep them shared across
  pages; don't fork per-page copies).
- The escaping logic, `repoUrl`, or the dynamic-axis logic.
Anything structural or redesign-flavored: describe it in the report; don't do it.

## Working style: you may run sub-agents
You are allowed and encouraged to spawn sub-agents to parallelize this pass — for
example, one sub-agent per page (Board / Map / Heatmap / Compare / About) running
the sweep, or dedicated sub-agents for a focused concern (accessibility hunt,
responsive-layout hunt, console-error hunt), or verification passes on findings.
Rules for delegating:
- Give every sub-agent the FULL context it needs: the intentional-decisions list,
  the may/must-not-change rules, and the exact checks it owns. A sub-agent with
  partial context WILL "fix" intentional things (e.g. the aria-hidden ticker) —
  don't let that happen.
- You (the orchestrator) own the final report and the decision on every edit.
  Prefer having sub-agents RETURN findings + proposed diffs, and you apply and
  serialize the edits — ESPECIALLY to the shared files `assets/theme.css` and
  `assets/data.js`, which must never be edited by two agents at the same time.
- Editing different page HTML files in parallel is fine (they're independent).
- Run the data-failure / empty-window SIMULATION on ONE agent only, serially — it
  mutates the shared `data/latest.json`. Never simulate it from two agents at once,
  and restore the file before any other data-dependent test runs.
- All sub-agents follow the same constraints (no redesign, keep escaping and
  repoUrl, preserve the visual identity, restore data).

## The QA sweep — be comprehensive
Serve the site, then verify (fixing defects as you go, re-testing after each fix):

1. Windows: on Board, Map, Compare — switch Today → Week → Month. Confirm the list/
   plot/rail re-render with different repos, the ticker updates, the meta line
   updates, and (Map) the axes rescale sensibly.
2. Board: the hero link and every row link resolve to the correct
   github.com/owner/name; sparklines render; the summary falls back
   (summary → description → "Summary pending.") when a field is missing.
3. Map: hovering a bubble shows a tooltip AND highlights the matching leaderboard
   row (and hovering a row highlights its bubble); leaderboard links work; the KPI
   tape values look right; quadrant labels and axis ticks are sane in all 3 windows.
4. Heatmap: matrix renders; the "Color by" toggle relabels+recolors cells; clicking
   a row expands a drill-down with working repo links; cell tooltips work; languages
   absent from a window show a dashed "—" cell; column totals render.
5. Compare: rail lists all repos and scrolls; clicking a rail name updates the
   detail; pin/unpin works up to 4 (the 5th pin is disabled), and the overlay chart
   + table update with series colors matching the pin badges; "Similar movers" chips
   refocus the detail; the detail "View on GitHub ↗" and table names link out; the
   big detail sparkline renders.
6. Navigation: the Board/Map/Heatmap/Compare switcher appears on every page with the
   correct current-page state and all links resolve; the brand logo returns to the
   Board; About's back-links work.
7. Failure states (SIMULATE, then restore — see safety note):
   - Break the data load (e.g., serve so `data/latest.json` 404s, or point at a bad
     file) → confirm each page shows the friendly error via `Starling.fail`
     (containers: Board `board`, Map `plot`, Heatmap `matrix`, Compare `rail`).
   - Feed a `latest.json` where one window's `repos` is `[]` → confirm that page's
     empty-state message renders instead of crashing.
8. Responsive: at ~390px and ~768px — no horizontal page overflow; grids collapse
   (board rows, map deck, heatmap matrix, compare desk); the ticker still scrolls;
   controls remain usable.
9. Accessibility: Tab through all interactive elements — every one shows a visible
   focus ring and is reachable; `prefers-reduced-motion: reduce` stops the ticker
   animation; aria states are correct; decorative SVGs are aria-hidden.
10. Console: no JS errors/exceptions on any page or during any interaction (favicon
    404 excepted).

## SAFETY: the data file
Before any failure/empty simulation, back up the real data:
    copy Github-Trending/site/data/latest.json to a temp path (e.g. latest.json.bak)
Do your simulations, then RESTORE `data/latest.json` to the original, byte-for-byte.
Verify it's restored (diff against the backup) and delete the backup. The live site
depends on this file — do NOT leave it modified. Do NOT leave any stray test files
in `site/` (the whole folder is deployed).

## Deliverable
- Edit files IN PLACE in `Github-Trending/site/`. Do NOT commit. Do NOT deploy.
- Write a report at `Github-Trending/QA-REPORT.md` (OUTSIDE `site/` so it isn't
  deployed) containing:
  - Summary (overall health; how many issues found/fixed).
  - Findings, severity-ranked — each with: page, `file:line`, how to reproduce, and
    whether you Fixed it or are Proposing it.
  - Changes made — each with `file:line` and what/why.
  - Proposed but not done — structural/redesign items for the owner to decide.
  - Couldn't verify / assumptions.
  - Confirmation that `data/latest.json` was restored intact after simulations, and
    the exact commands you used to serve and test.
- Leave the working tree so `git diff` shows only your intentional edits and the
  data file is unchanged.

## Out of scope — do not touch
- The `design-mockups/` folder (separate prototypes).
- The Python data pipeline / backend. Treat all on-page copy, including About's
  methodology numbers, as authoritative — do not cross-reference or rewrite them.

Begin by confirming you can drive a browser (fail fast if you cannot). Then serve
the site, do a first read-through of each page and the console, and work through
the sweep above — delegating to sub-agents where it helps.
