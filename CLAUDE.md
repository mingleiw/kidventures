# Kidventures

Static site. One page per city: pick a city, get places near it sorted by
distance. `README.md` has the full detail; this file is the things that bite.

## Generated files — never edit by hand

`index.html`, every `<city-slug>/` directory, `sitemap.xml` and `robots.txt` are
written by `build.py`. Editing them directly works until the next build, then
silently disappears.

Source of truth is `data/*.json` plus `templates/`.

```sh
python3 build.py     # stdlib only, no dependencies
```

**Run it after any data edit and commit its output**, or the live site won't
reflect the change. Generated city directories carry a `.generated` marker so the
build can remove ones that stop qualifying.

## Deploying

Push to `main`. Pages serves `/ (root)` from it.

`BASE_URL` at the top of `build.py` drives every canonical link and the sitemap.
If the repo is renamed or a domain is pointed at it, change that one line and
rebuild — a stale value produces no error, it just tells search engines the pages
live somewhere they don't.

## Rules that are not style preferences

**Events need a `source` URL.** Every listing renders a "Where this came from"
link so a parent can verify it. No source, no listing. This exists because
invented listings were shipped once already, and a fabricated storytime sends a
family on a real drive.

**Dated events come from the daily refresh, never from memory.** Sacramento
Public Library storytimes live in `data/dated_events_sac.json`, written by
`scripts/refresh_storytimes.py` (scrapes the library's public listing; stdlib
only). Mill Valley Public Library storytimes live in
`data/dated_events_marin.json`, written by
`scripts/refresh_marin_storytimes.py` (reads the library's public LibCal
JSON feed; stdlib only). One file per source, so a broken scraper can never
wipe another source's data. Do not hand-add dated instances — the scrapers
own those files. Do not encode library storytimes as weekly recurrences in
`data/events.json` either: they are published per date. Recurring
(non-library) weekly events from the Marin Mommies calendar were imported
once via `scripts/import_marin_mommies.py` (2026-09-16, 40 events); re-run
manually when they go stale. `build.py` folds the
next 7 days of dated events into the page JSON; `assets/app.js` matches them
by `e.date`.

**No opening hours, prices or one-off dates.** They change constantly and there
is no editor here to retire a stale value. Cards carry only slow-changing facts
plus a map link, which is always current. Map links are Google Maps *search*
links, never specific URLs, so they cannot 404.

**Weather is an enhancement, never a dependency.** Any failure — blocked request,
bad status, unexpected shape, timeout — leaves it unknown, and the shortlist
ranks on distance alone while claiming nothing about the sky. Test that path
first; it is the one that runs when the network is hostile.

**Coordinates decide everything.** `lat`/`lon` on a place determine which city
pages it appears on, in what order, and what distance is printed. Current values
are hand-entered approximations: fine for 5 miles versus 40, not surveyed.

## Load-bearing details

- `[hidden] { display: none !important; }` in `style.css` — cards are
  `display:flex`, which would otherwise override the `hidden` attribute and break
  filtering entirely.
- Distances are baked into `data-dist` at build time. `assets/app.js` never
  computes geography; it re-ranks using those numbers. The full list therefore
  renders correctly with JavaScript off.
- `localStorage` access is wrapped in `try/catch` — private browsing throws.
- Event text is escaped before insertion; venue names contain apostrophes.

## Why there are thresholds in build.py

`MIN_PLACES` (4) and `MAX_MILES` (25) decide whether a city gets a page at all.
`LIST_MILES` (40) caps what a page lists.

These are not tuning knobs. Without them the site is 42 pages carrying the same
30 places in a different order, which is the doorway-page pattern search engines
demote — and the stated long-term plan is ads, so indexability is load-bearing.
Four towns currently do not qualify. The fix is places near them, not a lower
threshold.

## Verify before pushing

No test suite. What has caught real bugs:

- Horizontal overflow at 320px — the header has broken twice this way.
- A city page other than the first one (orders and descriptions must differ).
- The raw HTML with JS off: distances must ascend.
- Every root link resolving to a real generated file.
