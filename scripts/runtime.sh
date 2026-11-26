#!/usr/bin/env bash
# One GitHub Actions tick: restore encrypted state, collect, short bot session, save state, publish journal.
# Designed to be run on ubuntu-latest. Does not print secrets.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
mkdir -p data
ENC_LOCAL=data/pmsignals.sqlite.enc
DB="${PM_DB_PATH:-$ROOT/data/pmsignals.sqlite}"

if [[ -z "${STATE_KEY:-}" ]]; then
  echo "STATE_KEY is required" >&2
  exit 1
fi

# Restore previous state from branch "state" if it exists (optional first run).
if git ls-remote --exit-code origin refs/heads/state >/dev/null 2>&1; then
  git fetch origin state:state
  git show state:pmsignals.sqlite.enc > "$ENC_LOCAL"
  ./scripts/state_crypt.sh decrypt "$ENC_LOCAL" "$DB"
  echo "restored encrypted state"
else
  echo "no state branch yet; starting with a fresh database"
fi

# Collector + journal + 7-day grading.
python run_cycle.py

# Short getUpdates session so buyers can talk to the bot during this tick.
# Default 180s leaves room for checkout, encrypt, and push inside a 10-minute job.
export PM_SESSION_SECONDS="${PM_SESSION_SECONDS:-180}"
python bot.py --session-seconds "$PM_SESSION_SECONDS"

# Checkpoint WAL into the main file before encrypting.
python - <<'PY'
import sqlite3, os
from pmsignals.config import DB_PATH
con = sqlite3.connect(DB_PATH)
con.execute("PRAGMA wal_checkpoint(TRUNCATE)")
con.close()
print("checkpointed", DB_PATH)
PY

./scripts/state_crypt.sh encrypt "$DB" "$ENC_LOCAL"

# Publish only the encrypted blob to an orphan-like single-commit branch "state".
# The blob is public but useless without STATE_KEY. History is force-replaced so
# old snapshots don't accumulate.
work=$(mktemp -d)
git init -q -b state "$work"
cp "$ENC_LOCAL" "$work/pmsignals.sqlite.enc"
printf 'This branch holds only an AES-256-CBC encrypted SQLite snapshot. It is not useful without the Actions secret STATE_KEY.\n' > "$work/README.md"
git -C "$work" add pmsignals.sqlite.enc README.md
git -C "$work" -c user.name="npc-signal-runtime" -c user.email="41898282+github-actions[bot]@users.noreply.github.com" \
  commit -qm "state $(date -u +%Y-%m-%dT%H:%MZ)"
git -C "$work" remote add origin "$(git remote get-url origin)"
git -C "$work" push -f origin state
rm -rf "$work"
echo "pushed encrypted state"

# Publish static site + journal to branch gh-pages (GitHub Pages source).
# Only the five public files; never the database or secrets.
work=$(mktemp -d)
git init -q -b gh-pages "$work"
for f in index.html terms.html journal.html journal.json style.css; do
  [[ -f site/$f ]] && cp "site/$f" "$work/"
done
printf 'User-agent: *\nAllow: /\n' > "$work/robots.txt"
git -C "$work" add -A
if git -C "$work" diff --cached --quiet; then
  echo "gh-pages unchanged"
else
  git -C "$work" -c user.name="npc-signal-runtime" -c user.email="41898282+github-actions[bot]@users.noreply.github.com" \
    commit -qm "journal $(date -u +%Y-%m-%dT%H:%MZ)"
  git -C "$work" remote add origin "$(git remote get-url origin)"
  # Do not force-push gh-pages if it already has history we didn't fetch; replace contents via force
  # because this branch must contain only the static site.
  git -C "$work" push -f origin gh-pages
  echo "pushed gh-pages"
fi
rm -rf "$work"
