#!/usr/bin/env python3
"""
Testbed control agent - runs on the SERVER (lab PC) next to SRS + MediaMTX.

Endpoints (CORS enabled, HTTP/1.1 keep-alive so clock probes are symmetric):
  GET  /api/time                 -> {"t": server_epoch_ms}       clock-offset probes (Cristian / NTP style)
  GET  /api/profiles             -> available tc/netem profiles
  GET  /api/netem                -> active profile + per-protocol tc counters (bytes / packets / drops)
  POST /api/netem/apply          {"profile": "<name>"}          apply a profile (predefined names only)
  POST /api/netem/clear          remove all tc state from the container
  POST /api/kick                 disconnect stale SRS play clients
  GET  /api/status               containers, publisher, versions, host info
  GET  /api/blob?bytes=N         N bytes of zeros (downlink throughput test, max 200 MB)
  GET  /<file>                   static files from ../web (live-demo dashboard)

The agent itself runs unprivileged and only calls `sudo -n docker inspect` and
`sudo -n nsenter -t <pid> -n tc ...` with argument lists built from the predefined profiles.
It listens on the host network namespace, so its own traffic (clock probes) is never shaped.
"""

import argparse
import json
import os
import platform
import subprocess
import sys
import threading
import time
import urllib.request
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
from network_profiles import HANDLE_TO_PROTO, PROFILES, build_tc_commands, reset_commands  # noqa: E402

WEB_DIR = ROOT / "web"
CONTAINER = "streaming-srs"
LLHLS_CONTAINER = "streaming-llhls"
SRS_API = "http://127.0.0.1:1985"

_lock = threading.Lock()
_state = {"profile": None, "applied_at": None, "pid": None, "gateway": None}


def _run(cmd, timeout=10):
    return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)


def _inspect(fmt, name=CONTAINER):
    r = _run(["sudo", "-n", "docker", "inspect", "-f", fmt, name])
    return r.stdout.strip() if r.returncode == 0 else None


def _container_pid(refresh=False):
    if refresh or not _state["pid"]:
        pid = _inspect("{{.State.Pid}}")
        _state["pid"] = pid if pid and pid != "0" else None
        _state["gateway"] = _inspect("{{range .NetworkSettings.Networks}}{{.Gateway}}{{end}}")
    return _state["pid"]


def _tc(args, check=True):
    pid = _container_pid()
    if not pid:
        raise RuntimeError(f"container {CONTAINER} is not running")
    r = _run(["sudo", "-n", "nsenter", "-t", pid, "-n"] + args)
    if r.returncode != 0 and check:
        # container may have been restarted -> refresh pid once
        pid = _container_pid(refresh=True)
        if not pid:
            raise RuntimeError(f"container {CONTAINER} is not running")
        r = _run(["sudo", "-n", "nsenter", "-t", pid, "-n"] + args)
        if r.returncode != 0:
            raise RuntimeError(f"{' '.join(args)} failed: {r.stderr.strip()}")
    return r


def apply_profile(name):
    with _lock:
        _container_pid(refresh=True)
        for cmd in reset_commands():
            _tc(cmd, check=False)
        for cmd in build_tc_commands(name, unshaped_dst=_state["gateway"]):
            _tc(cmd)
        _state["profile"] = name
        _state["applied_at"] = time.time()
    return netem_status()


def clear_tc():
    with _lock:
        for cmd in reset_commands():
            _tc(cmd, check=False)
        _state["profile"] = None
        _state["applied_at"] = time.time()


def netem_status():
    out = {"profile": _state["profile"], "spec": PROFILES.get(_state["profile"]),
           "applied_at": _state["applied_at"], "server_time_ms": time.time() * 1000, "counters": {}}
    try:
        r = _tc(["tc", "-s", "-j", "qdisc", "show", "dev", "eth0"], check=False)
        for q in json.loads(r.stdout or "[]"):
            proto = HANDLE_TO_PROTO.get(q.get("handle"))
            if proto:
                out["counters"][proto] = {k: q.get(k) for k in
                                          ("bytes", "packets", "drops", "overlimits", "requeues", "backlog", "qlen")}
    except Exception as e:  # noqa: BLE001
        out["error"] = str(e)
    return out


def kick_play_clients():
    kicked = 0
    try:
        with urllib.request.urlopen(f"{SRS_API}/api/v1/clients/?count=200", timeout=3) as r:
            for c in json.loads(r.read().decode()).get("clients", []):
                if not c.get("publish") and c.get("id"):
                    req = urllib.request.Request(f"{SRS_API}/api/v1/clients/{c['id']}", method="DELETE")
                    try:
                        urllib.request.urlopen(req, timeout=3)
                        kicked += 1
                    except Exception:  # noqa: BLE001
                        pass
    except Exception as e:  # noqa: BLE001
        return {"kicked": kicked, "error": str(e)}
    return {"kicked": kicked}


def status():
    st = {"server_time_ms": time.time() * 1000, "host": platform.node(), "kernel": platform.release(),
          "profile": _state["profile"], "containers": {}, "publisher": None}
    for name in (CONTAINER, LLHLS_CONTAINER):
        st["containers"][name] = {
            "running": _inspect("{{.State.Running}}", name) == "true",
            "image": _inspect("{{.Config.Image}}", name),
            "image_id": _inspect("{{.Image}}", name),
        }
    try:
        with urllib.request.urlopen(f"{SRS_API}/api/v1/streams/?count=50", timeout=3) as r:
            data = json.loads(r.read().decode())
        for s in data.get("streams", []):
            if s.get("name") == "stream":
                st["publisher"] = {"active": s.get("publish", {}).get("active"), "clients": s.get("clients"),
                                   "video": s.get("video"), "audio": s.get("audio"),
                                   "recv_kbps": s.get("kbps", {}).get("recv_30s")}
        with urllib.request.urlopen(f"{SRS_API}/api/v1/versions", timeout=3) as r:
            st["srs_version"] = json.loads(r.read().decode()).get("data", {}).get("version")
    except Exception as e:  # noqa: BLE001
        st["srs_error"] = str(e)
    try:
        st["cpu"] = next((l.split(":", 1)[1].strip() for l in open("/proc/cpuinfo") if l.startswith("model name")), None)
        st["loadavg"] = os.getloadavg()
    except Exception:  # noqa: BLE001
        pass
    return st


class Handler(SimpleHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    # Headers and body go out as separate writes; without TCP_NODELAY, Nagle + the client's delayed
    # ACK add ~40 ms to every small response and wreck the clock-probe accuracy.
    disable_nagle_algorithm = True

    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(WEB_DIR), **kwargs)

    def log_message(self, fmt, *args):
        if not self.path.startswith("/api/time"):
            sys.stderr.write("%s - %s\n" % (self.address_string(), fmt % args))

    def end_headers(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Cache-Control", "no-store")
        super().end_headers()

    def _json(self, obj, code=200):
        body = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Content-Length", "0")
        self.end_headers()

    def do_GET(self):
        u = urlparse(self.path)
        if u.path == "/api/time":
            t = time.time() * 1000  # stamp as late as possible, right before the reply
            return self._json({"t": t})
        if u.path == "/api/profiles":
            return self._json({"profiles": PROFILES, "active": _state["profile"]})
        if u.path == "/api/netem":
            return self._json(netem_status())
        if u.path == "/api/status":
            return self._json(status())
        if u.path == "/api/blob":
            n = min(int(parse_qs(u.query).get("bytes", ["10000000"])[0]), 200_000_000)
            self.send_response(200)
            self.send_header("Content-Type", "application/octet-stream")
            self.send_header("Content-Length", str(n))
            self.end_headers()
            chunk = b"\0" * 65536
            sent = 0
            while sent < n:
                k = min(len(chunk), n - sent)
                self.wfile.write(chunk[:k])
                sent += k
            return None
        return super().do_GET()

    def do_POST(self):
        u = urlparse(self.path)
        length = int(self.headers.get("Content-Length") or 0)
        body = self.rfile.read(length) if length else b""
        try:
            payload = json.loads(body.decode() or "{}")
        except json.JSONDecodeError:
            payload = {}
        try:
            if u.path == "/api/netem/apply":
                name = payload.get("profile") or parse_qs(u.query).get("profile", [None])[0]
                if name not in PROFILES:
                    return self._json({"error": f"unknown profile {name!r}"}, 400)
                return self._json(apply_profile(name))
            if u.path == "/api/netem/clear":
                clear_tc()
                return self._json({"ok": True})
            if u.path == "/api/kick":
                return self._json(kick_play_clients())
        except Exception as e:  # noqa: BLE001
            return self._json({"error": str(e)}, 500)
        return self._json({"error": "not found"}, 404)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=9000)
    ap.add_argument("--profile", default="baseline", help="profile applied at start-up")
    a = ap.parse_args()
    try:
        apply_profile(a.profile)
        print(f"[agent] applied start-up profile '{a.profile}'", flush=True)
    except Exception as e:  # noqa: BLE001
        print(f"[agent] WARNING: could not apply start-up profile: {e}", flush=True)
    srv = ThreadingHTTPServer(("0.0.0.0", a.port), Handler)
    srv.daemon_threads = True
    print(f"[agent] listening on :{a.port}  (dashboard: http://<server-ip>:{a.port}/)", flush=True)
    srv.serve_forever()


if __name__ == "__main__":
    main()
