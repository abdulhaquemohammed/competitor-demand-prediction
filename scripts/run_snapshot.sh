#!/bin/bash
# Takes one snapshot of all four companies and rebuilds the dataset.
# Called by launchd every Monday and Thursday (see scripts/com.cadetx.snapshot.plist).
cd "$(dirname "$0")/.." || exit 1
mkdir -p logs

# After the Mac wakes, Wi-Fi can take a minute to come back. Wait for a TCP connection
# to the job boards (no HTTP request), checking every 15s, for at most 5 minutes.
network_up() {
  .venv/bin/python -c "import socket
for h in ('api.ashbyhq.com', 'boards-api.greenhouse.io', 'nvidia.wd5.myworkdayjobs.com'):
    socket.create_connection((h, 443), timeout=5).close()" 2>/dev/null
}

{
  echo "=== $(date -u '+%Y-%m-%d %H:%M UTC') ==="
  waited=0
  until network_up; do
    if [ "$waited" -ge 300 ]; then echo "network still down after 5 min, trying anyway"; break; fi
    echo "network not ready, waiting 15s"; sleep 15; waited=$((waited + 15))
  done
  .venv/bin/python -u src/collect.py; status=$?
  .venv/bin/python -u src/build_dataset.py || status=1
  .venv/bin/python -u src/preprocess.py || status=1
  .venv/bin/python -u src/extract_skills.py || status=1
  echo "exit status: $status"
} >> logs/snapshots.log 2>&1
exit $status
