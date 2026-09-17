#!/bin/bash
# Daily refresh: re-scrape library storytimes, rebuild the site, push if changed.
# Run from cron. The push helper authenticates through the Secure Vault, so this
# needs the VM's authd socket (present in the normal agent runtime).
set -euo pipefail
cd "$(dirname "$0")/.."

python3 scripts/refresh_storytimes.py
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
