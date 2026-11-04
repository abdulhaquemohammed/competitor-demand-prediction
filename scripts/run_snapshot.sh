#!/bin/bash
# Takes one snapshot of all four companies and rebuilds the dataset.
# Called by launchd every Monday and Thursday (see scripts/com.cadetx.snapshot.plist).
cd "$(dirname "$0")/.." || exit 1
mkdir -p logs
{
  echo "=== $(date -u '+%Y-%m-%d %H:%M UTC') ==="
  .venv/bin/python src/collect.py
  .venv/bin/python src/build_dataset.py
} >> logs/snapshots.log 2>&1
