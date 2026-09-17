#!/usr/bin/env python3
"""One-time import of recurring weekly events from the Marin Mommies calendar.

Fetches ~3 weeks of day pages, keeps events that repeat on the same weekday,
and appends them to data/events.json as weekly events (region "marin").

Not part of the daily refresh: Marin Mommies listings are curated weekly
patterns, not dated instances. Re-run manually when they go stale.
"""
import json
import re
import html as H
import subprocess
import time
from collections import Counter, defaultdict
from datetime import date, timedelta

BASE = "https://www.marinmommies.com"
UA = "kidventures-import/1.0 (one-time import; contact via github.com/mingleiw/kidventures)"
EVENTS_JSON = "data/events.json"


def fetch(url):
    out = subprocess.run(
        ["curl", "-sL", "--max-time", "30", "-A", UA, url],
        capture_output=True, text=True,
    ).stdout
    time.sleep(0.4)
    return out


def clean(s):
    s = H.unescape(re.sub(r"<[^>]+>", " ", s or ""))
    return re.sub(r"\s+", " ", s).strip()


def parse_day(html):
    rows = re.split(r'<div class="views-row ', html)[1:]
    events = []
    for row in rows:
        m = re.search(r'views-field-title.*?<a href="(/calendar/[^"]+)">(.*?)</a>', row, re.S)
        if not m:
            continue
        slug, title = m.group(1), clean(m.group(2))
        dt = re.search(r'content="(\d{4}-\d{2}-\d{2})T(\d{2}):(\d{2})', row)
        venue = re.search(r'views-field-field-address-locality.*?<strong>(.*?)</strong>', row, re.S)
        body = re.search(r'views-field-body.*?<span class="field-content">(.*?)</span>', row, re.S)
        events.append({
            "slug": slug,
            "title": title,
            "date": dt.group(1) if dt else None,
            "time": f"{dt.group(2)}:{dt.group(3)}" if dt else None,
            "venue_str": clean(venue.group(1)) if venue else "",
            "blurb": clean(body.group(1)) if body else "",
        })
    return events


def parse_detail(html):
    end = re.search(r'date-display-end[^>]*>([^<]+)<', html)
    body = re.search(r'views-field-body.*?<div class="field-items".*?>(.*?)</div>', html, re.S)
    return {
        "until_disp": clean(end.group(1)) if end else None,
        "body": clean(body.group(1)) if body else "",
    }


def to_24h(disp):
    m = re.match(r"(\d{1,2}):(\d{2})\s*([ap])\.?m\.?", disp.strip().lower())
    if not m:
        return None
    h, mi, ap = int(m.group(1)), m.group(2), m.group(3)
    if ap == "p" and h != 12:
        h += 12
    if ap == "a" and h == 12:
        h = 0
    return f"{h:02d}:{mi}"


def infer_ages(title):
    t = title.lower()
    if re.search(r"crawl|bab(y|ies)|newborn", t):
        return "Babies & toddlers"
    if re.search(r"26 ?mo|toddler", t):
        return "Under 3"
    if re.search(r"0[–-]5|preschool", t):
        return "Under 6"
    if re.search(r"\b(4|5)[–-]\d{1,2}\b", t):
        return "Ages 4+"
    return "All ages"


def main():
    start = date(2026, 9, 17)
    days = [start + timedelta(days=i) for i in range(21)]

    by_slug = defaultdict(list)
    for d in days:
        html = fetch(f"{BASE}/calendar/{d.isoformat()}")
        for ev in parse_day(html):
            if ev["date"]:
                by_slug[ev["slug"]].append(ev)
        print(f"parsed {d.isoformat()}: {len(parse_day(html))} events")

    existing = json.load(open(EVENTS_JSON))
    have = {(e["title"], e.get("venue"), e.get("day")) for e in existing}

    added, skipped = [], []
    for slug, occs in sorted(by_slug.items()):
        first = occs[0]
        if "mill valley" in first["venue_str"].lower():
            skipped.append((first["title"], "Mill Valley venue — covered by library scraper"))
            continue
        js_days = Counter()
        times = Counter()
        for o in occs:
            y, m_, d_ = map(int, o["date"].split("-"))
            js_days[(date(y, m_, d_).weekday() + 1) % 7] += 1
            if o["time"]:
                times[o["time"]] += 1
        if len(js_days) >= 5:
            skipped.append((first["title"], "daily drop-in — no weekly slot"))
            continue
        recur = [(wd, n) for wd, n in js_days.items() if n >= 2]
        if not recur:
            skipped.append((first["title"], "one-off / seasonal"))
            continue
        wd = max(recur, key=lambda x: x[1])[0]
        time_24 = times.most_common(1)[0][0] if times else None

        detail = parse_detail(fetch(BASE + slug))
        until = to_24h(detail["until_disp"]) if detail["until_disp"] else None
        blurb = detail["body"] or first["blurb"]
        blurb = re.sub(r"\.\.\.$", "", blurb).strip()
        if len(blurb) > 220:
            blurb = blurb[:217].rsplit(" ", 1)[0] + "…"

        venue_str = first["venue_str"]
        if ", " in venue_str:
            venue, city = venue_str.rsplit(", ", 1)
        else:
            venue, city = venue_str, venue_str
        # normalize "Tiburon Belvdere" style typos lightly — keep source wording
        key = (first["title"], venue.strip(), wd)
        if key in have:
            skipped.append((first["title"], "already in events.json"))
            continue

        ev = {
            "time": time_24 or "10:00",
            "title": first["title"],
            "venue": venue.strip(),
            "city": city.strip(),
            "region": "marin",
            "ages": infer_ages(first["title"]),
            "blurb": blurb,
            "source": BASE + slug,
            "day": wd,
        }
        if until and until != ev["time"]:
            ev["until"] = until
        existing.append(ev)
        have.add(key)
        added.append(ev)

    json.dump(existing, open(EVENTS_JSON, "w"), indent=1, ensure_ascii=False)
    open(EVENTS_JSON, "a").write("\n")

    print(f"\nadded {len(added)} weekly events")
    for e in added:
        print(f"  day={e['day']} {e['time']} {e['title']} — {e['venue']}, {e['city']}")
    print(f"\nskipped {len(skipped)}")
    for t, why in skipped:
        print(f"  - {t} ({why})")


if __name__ == "__main__":
    main()
