#!/usr/bin/env python3
"""Daily check of Sacramento Children's Museum recurring programs.

Fetches the museum's program pages and keeps the hand-added weekly SCM entries
in data/events.json (tagged origin="scm") in sync. Verifies each program page
still describes a weekly recurrence; updates day/time if the museum changed the
schedule. If a program page is gone or no longer weekly, exits nonzero and
leaves events.json untouched so a human can look.
"""
import json
import os
import re
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EVENTS_JSON = os.path.join(ROOT, "data", "events.json")
ORIGIN = "scm"
UA = "kidventures-refresh/1.0 (daily refresh; contact via github.com/mingleiw/kidventures)"

# program page -> expected weekly signal (regex, case-insensitive)
PROGRAMS = {
    "Tiny Tuesday": {
        "url": "https://sackids.org/programs/tiny-tuesday/",
        "weekly": r"every tuesday",
    },
}

WEEKDAY = {"monday": 1, "tuesday": 2, "wednesday": 3, "thursday": 4,
           "friday": 5, "saturday": 6, "sunday": 0}


def fetch(url):
    return subprocess.run(
        ["curl", "-sL", "--max-time", "30", "-A", UA, url],
        capture_output=True, text=True,
    ).stdout


def main():
    events = json.load(open(EVENTS_JSON))
    by_title = {e["title"]: e for e in events if e.get("origin") == ORIGIN}
    problems, checked = [], []

    for title, spec in PROGRAMS.items():
        html = fetch(spec["url"])
        if not html or len(html) < 1000:
            problems.append(f"{title}: program page unreachable")
            continue
        text = re.sub(r"<[^>]+>", " ", html)
        text = re.sub(r"\s+", " ", text)
        if not re.search(spec["weekly"], text, re.I):
            problems.append(f"{title}: page no longer describes a weekly recurrence")
            continue
        m = re.search(r"every (monday|tuesday|wednesday|thursday|friday|saturday|sunday)",
                      text, re.I)
        if m and title in by_title:
            want_day = WEEKDAY[m.group(1).lower()]
            e = by_title[title]
            if e.get("day") != want_day:
                print(f"  RESCHEDULED: {title} day {e.get('day')} -> {want_day}")
                e["day"] = want_day
        checked.append(title)

    if problems:
        for p in problems:
            print(f"ERROR: {p}", file=sys.stderr)
        return 1

    json.dump(events, open(EVENTS_JSON, "w"), indent=1, ensure_ascii=False)
    open(EVENTS_JSON, "a").write("\n")
    print(f"scm refresh: checked {len(checked)} program(s): {', '.join(checked)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
