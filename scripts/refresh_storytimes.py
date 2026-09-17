#!/usr/bin/env python3
"""Daily refresh of Sacramento Public Library storytimes.

The library schedules storytimes per date and rotates them between branches,
so they cannot be encoded as weekly recurrences. Instead this script scrapes
the library's public event listing once a day and writes *dated* instances to
data/dated_events.json. build.py folds the next 7 days of those into each
Sacramento-area town page.

    python3 scripts/refresh_storytimes.py

Stdlib only. Reads nothing but the public listing; writes data/dated_events.json.
"""

import datetime as dt
import json
import os
import re
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Communico "series" page that server-renders every upcoming Family Storytime
# instance (any of the /event/<id> aliases render the same listing).
LISTING_URL = "https://engage.saclibrary.org/event/14016514"

DAYS_AHEAD = 45  # how far out to keep dated entries

BRANCH_CITY = {
    "Elk Grove": "Elk Grove",
    "Franklin": "Elk Grove",
    "Galt - Marian O. Lawrence": "Galt",
    "Rancho Cordova": "Rancho Cordova",
    "Orangevale": "Orangevale",
    "Fair Oaks": "Fair Oaks",
    "Carmichael": "Carmichael",
    "Rio Linda": "Rio Linda",
    "North Highlands - Antelope": "North Highlands",
    "Walnut Grove": "Walnut Grove",
    "Isleton": "Isleton",
    "Nonie Wetzel Courtland": "Courtland",
}

MONTHS = {m: i + 1 for i, m in enumerate(
    "Jan Feb Mar Apr May Jun Jul Aug Sep Oct Nov Dec".split())}


def fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent": "kidventures-refresh/1.0"})
    with urllib.request.urlopen(req, timeout=60) as resp:
        return resp.read().decode("utf-8", errors="replace")


def parse_clock(s):
    """'10:30am' -> '10:30'. Returns None for unparseable input."""
    m = re.match(r"(\d{1,2})(?::(\d{2}))?\s*([ap])\.?m\.?", s.strip(), re.I)
    if not m:
        return None
    h, mi, ap = int(m.group(1)), int(m.group(2) or 0), m.group(3).lower()
    if ap == "p" and h != 12:
        h += 12
    if ap == "a" and h == 12:
        h = 0
    return "%02d:%02d" % (h, mi)


def parse_when(s, today):
    """'Wed, Sep 16, 10:00am - 11:00am' -> ('2026-09-16', '10:00', '11:00')."""
    m = re.match(r"\w{3}, (\w{3}) (\d{1,2}), (.+)", s.strip())
    if not m:
        return None
    mon, day, rest = m.group(1), int(m.group(2)), m.group(3).strip()
    if mon not in MONTHS or "all day" in rest.lower():
        return None
    year = today.year
    if MONTHS[mon] < today.month - 1:  # year rollover guard
        year += 1
    date = "%04d-%02d-%02d" % (year, MONTHS[mon], day)
    parts = [p.strip() for p in rest.split("-", 1)]
    start = parse_clock(parts[0])
    if not start:
        return None
    end = parse_clock(parts[1]) if len(parts) > 1 else None
    return date, start, end


def strip_tags(s):
    return re.sub(r"<[^>]+>", "", s or "").strip()


def parse_listing(html, today):
    events = []
    for block in html.split('<div class="amev-event">')[1:]:
        m = re.search(r'amev-event-title"><a href="(https://engage\.saclibrary\.org/event/\d+)">([^<]+)</a>', block)
        if not m:
            continue
        url, title = m.group(1), m.group(2).strip()
        if "storytime" not in title.lower() and "cuentos" not in title.lower():
            continue
        if "amev-event-canceled" in block or ">Cancelled<" in block or ">Rescheduled<" in block:
            continue
        m = re.search(r'amev-event-time headingtext">([^<]+)</div>', block)
        if not m:
            continue
        when = parse_when(m.group(1), today)
        if not when:
            continue
        date, start, end = when
        if date < today.isoformat():
            continue
        m = re.search(r'amev-event-location headingtext">.*?</i>\s*([^<]+)', block, re.S)
        branch = strip_tags(m.group(1)) if m else ""
        branch = re.sub(r"\s*-\s*$", "", branch).strip()
        m = re.search(r'amev-event-description">(.*?)</div>\s*</div>', block, re.S)
        desc = strip_tags(m.group(1)) if m else ""

        city = BRANCH_CITY.get(branch, "Sacramento" if branch else "")
        venue = branch if not branch else (branch if "Library" in branch else branch + " Library")
        bilingual = "espa\u00f1ol" in desc.lower() or "cuentos" in desc.lower()
        baby = "baby" in title.lower()
        if baby:
            blurb = "Gentle songs, rhymes and book-sharing for babies and caregivers."
        else:
            blurb = "Songs, rhymes, movement and stories for young children."
        if bilingual:
            blurb += " Bilingual Spanish/English."

        events.append({
            "date": date,
            "time": start,
            "title": title,
            "venue": venue,
            "city": city,
            "region": "sac",
            "ages": "Babies" if baby else "All ages",
            "blurb": blurb,
            "source": url,
        })
        if end:
            events[-1]["until"] = end

    # dedupe on (date, time, venue, title); keep chronological
    seen, uniq = set(), []
    for e in sorted(events, key=lambda e: (e["date"], e["time"], e["venue"])):
        key = (e["date"], e["time"], e["venue"], e["title"])
        if key not in seen:
            seen.add(key)
            uniq.append(e)
    return uniq


def main():
    today = dt.date.today()
    cutoff = (today + dt.timedelta(days=DAYS_AHEAD)).isoformat()
    html = fetch(LISTING_URL)
    events = [e for e in parse_listing(html, today) if e["date"] <= cutoff]
    out = os.path.join(ROOT, "data", "dated_events.json")
    with open(out, "w", encoding="utf-8") as f:
        json.dump(events, f, ensure_ascii=False, indent=1)
        f.write("\n")
    print("wrote %d dated storytimes to %s (through %s)" % (len(events), out, cutoff))


if __name__ == "__main__":
    main()
