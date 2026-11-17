#!/usr/bin/env bash
# Start the SERVER side of the two-machine testbed (run on the lab PC):
#   SRS v5 (WebRTC + HTTP-FLV) and MediaMTX (LL-HLS) containers sharing one network namespace,
#   the timestamped 720p30 stream generator (RTMP over loopback), and the control agent.
# Usage:  bash server/up.sh [SERVER_IP]
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DEFAULT_IP="$(ip -4 route get 1.1.1.1 2>/dev/null | awk '{for(i=1;i<=NF;i++) if($i=="src"){print $(i+1); exit}}')"
SERVER_IP="${1:-${SERVER_IP:-$DEFAULT_IP}}"
AGENT_PORT="${AGENT_PORT:-9000}"
SRS_IMAGE="${SRS_IMAGE:-ossrs/srs:5}"
MTX_IMAGE="${MTX_IMAGE:-bluenviron/mediamtx:1.21.3}"
mkdir -p "$ROOT/logs" "$ROOT/run"

echo "[up] server IP / WebRTC ICE candidate: $SERVER_IP"
bash "$ROOT/server/down.sh" >/dev/null 2>&1 || true

sudo -n docker run -d --name streaming-srs \
  -p 1935:1935 -p 1985:1985 -p 18080:8080 -p 8000:8000/udp -p 8888:8888 \
  -e CANDIDATE="$SERVER_IP" \
  -v "$ROOT/config/srs.conf:/usr/local/srs/conf/srs.conf:ro" \
  "$SRS_IMAGE" ./objs/srs -c conf/srs.conf >/dev/null
sudo -n docker run -d --name streaming-llhls --network container:streaming-srs \
  -v "$ROOT/config/mediamtx.yml:/mediamtx.yml:ro" \
  "$MTX_IMAGE" >/dev/null
echo "[up] containers started ($SRS_IMAGE, $MTX_IMAGE)"
sleep 2

# Timestamped generator -> RTMP on loopback (auto-restarts if FFmpeg exits)
setsid nohup bash "$ROOT/server/run_generator.sh" >"$ROOT/logs/generator.log" 2>&1 </dev/null &
echo $! >"$ROOT/run/generator.pid"

# Control agent: clock probes, tc/netem profiles, live dashboard
setsid nohup python3 "$ROOT/server/agent.py" --port "$AGENT_PORT" >"$ROOT/logs/agent.log" 2>&1 </dev/null &
echo $! >"$ROOT/run/agent.pid"

sleep 4
echo "[up] live dashboard: http://$SERVER_IP:$AGENT_PORT/"
curl -s "http://127.0.0.1:$AGENT_PORT/api/status" | python3 -m json.tool
