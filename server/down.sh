#!/usr/bin/env bash
# Stop everything started by server/up.sh (agent, generator, containers).
set -uo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
for name in agent generator; do
  pidfile="$ROOT/run/$name.pid"
  if [ -f "$pidfile" ]; then
    pid="$(cat "$pidfile")"
    kill -- "-$pid" 2>/dev/null || kill "$pid" 2>/dev/null
    rm -f "$pidfile"
  fi
done
pkill -f "$ROOT/server/run_generator.sh" 2>/dev/null
pkill -f "$ROOT/scripts/stream_generator.py" 2>/dev/null
pkill -f "$ROOT/server/agent.py" 2>/dev/null
sudo -n docker rm -f streaming-llhls streaming-srs >/dev/null 2>&1
echo "[down] testbed stopped"
