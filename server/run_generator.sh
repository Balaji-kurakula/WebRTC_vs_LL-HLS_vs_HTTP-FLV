#!/usr/bin/env bash
# Keeps the timestamped stream generator running (restarts it if FFmpeg / RTMP drops).
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
URL="${1:-rtmp://127.0.0.1:1935/live/stream}"
while true; do
  echo "[gen] $(date -Is) starting generator -> $URL"
  python3 "$ROOT/scripts/stream_generator.py" "$URL"
  echo "[gen] $(date -Is) generator exited with code $?, restarting in 2 s"
  sleep 2
done
