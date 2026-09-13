#!/usr/bin/env bash
# Daily publish run. Safe to run any number of times: the queue resumes where it
# stopped and never re-adds a song that is already in a playlist.
#
# Schedule it AFTER the quota reset (midnight US/Pacific) in your own timezone.
set -uo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO" || exit 1

PLAYLISTS="${YTPS_QUEUE_DIR:-out/moods}"
PRIVACY="${YTPS_PRIVACY:-private}"
LOG="${YTPS_LOG:-.ytps/publish.log}"
mkdir -p "$(dirname "$LOG")"

{
  echo "=== $(date '+%Y-%m-%d %H:%M:%S %Z') ==="
  if [ ! -x ./.venv/bin/ytps ]; then
    echo "ytps not found at ./.venv/bin/ytps - is the venv built?"
    exit 1
  fi
  NO_COLOR=1 ./.venv/bin/ytps publish queue "$PLAYLISTS" \
      --privacy "$PRIVACY" --yes --next-run "tomorrow, same time"
} >> "$LOG" 2>&1

# Never fail the scheduler: a quota stop is an expected daily outcome, not an error.
exit 0
