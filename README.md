# Kidventures

Where to take the kids, across Northern California.

One page per city. Pick a city, get the places near it sorted by distance, with
the parking and weather notes that decide whether it's worth the drive.

```
/                    city picker — dropdown plus a crawlable list of every city
/elk-grove/          places near Elk Grove, closest first
/berkeley/           places near Berkeley, closest first
...                  38 cities
```

## Files

```
build.py             generates every page — run this after editing data
data/places.json     30 destinations
data/events.json     recurring weekly events
data/towns.json      42 towns with coordinates
templates/           shared fragments (icon sprite, "Before you go")
assets/style.css     styles, shared by every page
assets/app.js        client script, shared by every city page
index.html           GENERATED — do not edit
<city-slug>/         GENERATED — do not edit
sitemap.xml          GENERATED
```

**Anything marked GENERATED is overwritten by `build.py`.** Edit the JSON, then
rebuild. Generated city directories carry a `.generated` marker file so the build
can clean up ones that no longer qualify.

## Building

```sh
python3 build.py
```

No dependencies — standard library only. The output is committed, so GitHub Pages
still serves plain static files and nothing runs on deploy.

Why a build step, when "no build step" used to be the point: a city page needs its
places sorted by distance *from that city*. Doing that here rather than in the
browser means each page ships genuinely different, crawlable content, and the
whole list still renders with JavaScript off.

## Deploying

**Settings → Pages → Deploy from a branch → `main` → `/ (root)`**

Once enabled, live at <https://mingleiw.github.io/kidventures/>

Push to `main` and Pages redeploys. Run `build.py` and commit its output first, or
the live site won't reflect your data edits.

If the repo is ever renamed, or a custom domain is pointed at it, change
`BASE_URL` at the top of `build.py` and rebuild. It drives every canonical URL and
the sitemap, and a wrong value quietly tells search engines the pages live
somewhere they don't.

## Which cities get a page

Two thresholds in `build.py`:

| Constant | Value | What it controls |
| --- | --- | --- |
| `MIN_PLACES` | 4 | A city needs this many places within `MAX_MILES` to get a page at all |
| `MAX_MILES` | 25 | The radius that qualification is measured over |
| `LIST_MILES` | 40 | A city page only lists places within this far |

Currently 38 of 42 towns qualify. Skipped: **Petaluma** (1 place within 25mi),
**Santa Rosa** (0), **Livermore** (2), **Gilroy** (1).

This is deliberate, and it matters if the site is ever monetised. Publishing 42
pages that all carry the same 30 places in a different order is the doorway-page
pattern search engines demote. `LIST_MILES` is what stops each page being padded
with destinations nobody would drive to from there — it's why the Elk Grove page
lists 9 Sacramento places and not 21 Bay Area ones as well.

To add a skipped city, add places near it. The thresholds are a symptom, not the
cause.

## Adding a place

Add an object to `data/places.json` and rebuild. It appears automatically on
every city page within `LIST_MILES` of it.

```jsonc
{
  "name": "Fairytale Town",
  "where": "William Land Park, Sacramento",   // shown under the name
  "desc": "Storybook sets built at child scale…",
  "note": "Shares the park with the zoo…",     // the "Before you go" line
  "cta": "Map, hours &amp; tickets",
  "mapq": "Fairytale+Town+Sacramento+CA",      // Google Maps search query
  "icon": "i-play",                            // see templates/sprite.svg
  "cat": "play",                               // colour coding
  "age": "0-2 3-5 6-9",                        // space separated
  "region": "sac",
  "env": "outdoor",                            // "indoor", "outdoor", or both
  "lat": 38.535, "lon": -121.503,              // required: drives everything
  "ages": "Under 10", "envlabel": "Outdoors"   // human labels for the tags
}
```

`age` and `env` must match the filter buttons' `data-v` values exactly
(`0-2` `3-5` `6-9` `10+`, and `indoor` `outdoor`) or the card can never be
filtered to. `cat` is one of `science` `animals` `outdoors` `play` `making`
`water` and only sets the icon colour.

**Coordinates are the important field.** They decide which city pages the place
appears on, in what order, and what distance is printed. The current ones are
hand-entered approximations — good enough to rank 5 miles against 40, not
surveyed.

## Adding a weekly event

Add to `data/events.json`. Events show on city pages whose region matches.

```jsonc
{
  "day": 6,                     // 0=Sun … 6=Sat
  "time": "08:00",              // OPTIONAL. 24h. Omit if the hour is genuinely
                                // unknown — never guess it; see below
  "timeLabel": "Mornings",      // OPTIONAL. Shown instead of a clock when `time`
                                // is absent but the period IS sourced
  "until": "12:00",             // optional
  "title": "Elk Grove Certified Farmers' Market",
  "venue": "Laguna Gateway Center", "city": "Elk Grove",
  "region": "sac", "ages": "All ages",
  "blurb": "Year-round Saturday market…",
  "source": "https://…"         // REQUIRED
}
```

**`source` is not optional.** Every listing renders a "Where this came from"
link, so a parent can verify it in one tap. No source, no listing.

**`time` is optional, and that is deliberate.** A confirmed day at a confirmed
venue is worth listing even when the hour isn't known; a guessed clock time is
not, because a family drives to it. Omit `time` and the row renders "Time not
confirmed", sorts after the timed events, and shows its source link so the hour
can be checked. Do not fill it in with a plausible-looking value.

If the source says something real but vague — "each Saturday morning" — put that
in `timeLabel` and leave `time` out. It carries what is known and no more.

### What does not fit this model

**Sacramento Public Library storytimes.** They are scheduled per date and rotate
between branches through the month, so there is no stable "Saturdays at Franklin"
rule to encode. Listing one would be wrong most weeks. They are deliberately
absent — do not add them from a single dated listing that happens to show up in
search.

**Registered classes** (Cosumnes CSD Toddler Time, Buddy Bunch). You enrol in
those; they are not drop-in, so they do not belong on a "what's on today" page.

**The Elk Grove library** has a grand opening on **10 October 2026** at its new
address, 9260 Elk Grove Blvd. Nothing is listed there until it is open and a
schedule is published.

### Why recurring events, not a dated calendar

A static site has no editor to retire stale entries. A one-off date is wrong
forever once it passes. A weekday rule — *"Saturdays at 8"* — stays true for
months, and the browser works out which dates it lands on. It's the version of an
events calendar that a static site can keep honest.

## Editorial rule

**No opening hours, admission prices or one-off dates anywhere on the page.**

They change constantly and a stale value sends a family on a wasted trip. Cards
carry only things that rarely change, plus a map link that's always current.

Map links are Google Maps *search* links, not specific URLs, so they can't 404 and
survive a venue redesigning its website.

## Ads

Two comment markers sit where an ad unit would go — one on the root page between
the picker and the city index, one on each city page above the shortlist. Search
for `ad slot` in `build.py`.

If ads happen, the SEO notes above stop being theoretical: revenue tracks traffic,
traffic tracks whether these pages are worth indexing, and that is exactly what
`MIN_PLACES` and `LIST_MILES` protect.

## Implementation notes — don't remove these

- `[hidden] { display: none !important; }` is **load-bearing**. Cards are
  `display:flex`, which would otherwise override the `hidden` attribute and break
  filtering entirely.
- Distances are baked into `data-dist` at build time. `app.js` never computes
  geography — it re-ranks using those numbers.
- Weather is an enhancement, never a dependency. A blocked request, bad status,
  unexpected shape or 4s timeout all leave it unknown, and the shortlist ranks on
  distance alone while claiming nothing about the sky.
- `localStorage` access is wrapped in `try/catch` — private browsing throws, and
  the site must still work.
- Event text is escaped before insertion, so an apostrophe or `&` in a venue name
  can't break the markup.
- The nav link has a short form (`Cities`) below 420px, because "Change city"
  plus the brand overflows a 320px screen.

## Possible next steps

- [ ] More Peninsula and North Bay places — the thinnest regions
- [ ] Places near Petaluma, Santa Rosa, Livermore and Gilroy so they qualify
- [ ] Storytimes for the Elk Grove library after its **10 October 2026** grand
      opening at 9260 Elk Grove Blvd; nothing is listed there until a schedule
      is published
- [ ] The hour for the A Seat at the Table Books storytime, which is listed
      without one
- [ ] An age filter on the weekly events (`ages` is display-only today)
- [ ] Per-city `<title>` tuning if search traffic ever becomes the goal
