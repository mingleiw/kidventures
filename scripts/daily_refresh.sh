#!/bin/bash
# Daily refresh: re-scrape library storytimes, refresh other recurring events,
# rebuild the site, push if changed.
# Run from cron. The push helper authenticates through the Secure Vault, so this
# needs the VM's authd socket (present in the normal agent runtime).
set -euo pipefail
cd "$(dirname "$0")/.."

python3 scripts/refresh_storytimes.py          # Sacramento-area library storytimes
python3 scripts/refresh_marin_storytimes.py   # Mill Valley / Marin library storytimes
python3 scripts/refresh_marin_events.py       # other recurring Marin events (Marin Mommies)
python3 scripts/refresh_scm_events.py         # Sacramento Children's Museum weekly programs
python3 build.py

if [ -z "$(git status --porcelain)" ]; then
  echo "no changes"
  exit 0
fi

# gh-push-tree lives outside the repo (it holds no secrets; auth comes from the
# Secure Vault at call time).
~/workspace/skills/github/bin/gh-push-tree "$(pwd)" "Daily storytime refresh ($(date +%F))" main

# Keep the local clone in sync with what was just pushed so tomorrow's
# `git status` only shows genuinely new changes.
git fetch -q origin main
git reset -q --hard origin/main
echo "pushed and synced"

# --- Sacramento branch (kidventures.fun) ---
# The Sacramento branch builds a Sacramento-only site from the same data.
# main is the single source of truth for scraped data; sync the scraper-owned
# files, but NOT data/events.json or data/towns.json (the branch carries its own
# Sacramento additions there) and NOT build.py (the branch has FOCUS_REGION and
# the kidventures.fun BASE_URL).
git checkout -q Sacramento
git checkout -q main -- data/dated_events_sac.json \
                       data/dated_events_marin.json \
                       data/dated_events_curated.json
python3 build.py

if [ -z "$(git status --porcelain)" ]; then
  echo "sacramento: no changes"
else
  ~/workspace/skills/github/bin/gh-push-tree "$(pwd)" "Daily Sacramento refresh ($(date +%F))" Sacramento
  git fetch -q origin Sacramento
  git reset -q --hard origin/Sacramento
  echo "sacramento: pushed and synced"
fi

# Leave the workspace on main, the normal working branch.
git checkout -q main
