#!/usr/bin/env bash
# Copy the server-side files from the laptop to the lab PC (run in Git Bash on the laptop).
# Usage:  bash server/deploy.sh [user@host]
set -euo pipefail
TARGET="${1:-networks@10.21.232.54}"
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
tar czf - config server web scripts/stream_generator.py scripts/network_profiles.py \
  | ssh "$TARGET" 'mkdir -p ~/cs6048_testbed && tar xzf - -C ~/cs6048_testbed && echo "[deploy] synced to ~/cs6048_testbed"'
