#!/usr/bin/env python3
"""
Two-machine measurement campaign runner (runs on the VIEWER laptop).

For every run it: applies a tc/netem profile on the server (via the agent), snapshots the
per-protocol tc counters, launches a fresh headless Chromium on this machine that plays all three
protocols simultaneously from the server, collects the raw per-frame telemetry, snapshots the tc
counters again, and stores everything as one JSON file per run.

Design
  * Repetitions use a randomized complete block design: each repetition is one full pass over all
    conditions in a freshly shuffled order (seeded), so slow drifts in the real network affect all
    conditions and protocols equally.
  * The three protocols play at the same time in the same browser, each through its own identically
    configured netem pipe -> paired comparison (same instant, same physical path).
  * Every run starts a cold browser profile, so start-up delay is measured from scratch.
  * Clock offset between laptop and server is measured by the page before and after each run and
    independently by this script (both recorded).
  * Resumable: re-running with the same --campaign skips runs that already have a result file.

Usage
  python scripts/run_campaign.py --plan pilot --reps 1 --duration 30
  python scripts/run_campaign.py --plan full --reps 5 --campaign main_2026-11-13
  python scripts/run_campaign.py --campaign main_2026-11-13            (resume)
"""

import argparse
import csv
import http.client
import http.server
import json
import os
import platform
import random
import re
import shutil
import statistics
import subprocess
import sys
import tempfile
import threading
import time
import urllib.request
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from metrics import run_rows  # noqa: E402
from network_profiles import PROFILES  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
WEB_DIR = ROOT / "web"
CAMPAIGNS_DIR = ROOT / "results" / "campaigns"

BUFFERS = (0.2, 0.5, 1.0, 2.0, 3.5)
# One-factor sweeps use a 1.0 s buffer target: at 0.5 s LL-HLS already stalls on an unimpaired link
# (MediaMTX advertises PART-HOLD-BACK = 0.5 s), so impairments would be confounded with that.
SENS_BUF = 1.0
PLANS = {
    "full": (
        [("baseline", b) for b in BUFFERS]
        + [("cellular_4g", b) for b in BUFFERS]
        + [(p, SENS_BUF) for p in ("bw_5m", "bw_3m", "bw_2.2m", "bw_1.6m")]
        + [(p, SENS_BUF) for p in ("rtt_80ms", "rtt_160ms", "rtt_300ms")]
        + [(p, SENS_BUF) for p in ("loss_1pct", "loss_3pct", "loss_5pct")]
    ),
    "pilot": [("baseline", 0.5), ("cellular_4g", 0.5), ("rtt_160ms", 0.5)],
}

BROWSERS = [
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
    "/usr/bin/google-chrome",
    "/usr/bin/chromium",
]


# ----------------------------------------------------------------------------- local page server
class _Handler(http.server.SimpleHTTPRequestHandler):
    expected_run = None
    report = None
    event = threading.Event()

    def __init__(self, *a, **kw):
        super().__init__(*a, directory=str(WEB_DIR), **kw)

    def log_message(self, *a):
        pass

    def do_POST(self):
        if self.path != "/api/report":
            self.send_response(404)
            self.end_headers()
            return
        body = self.rfile.read(int(self.headers.get("Content-Length", 0)))
        try:
            rep = json.loads(body.decode())
        except json.JSONDecodeError:
            rep = None
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(b'{"ok":true}')
        if rep and rep.get("meta", {}).get("runId") == _Handler.expected_run:
            _Handler.report = rep
            _Handler.event.set()


# ----------------------------------------------------------------------------- server agent helpers
class Agent:
    def __init__(self, host, port):
        self.host, self.port = host, port

    def call(self, path, payload=None, timeout=20):
        data = json.dumps(payload).encode() if payload is not None else None
        req = urllib.request.Request(f"http://{self.host}:{self.port}{path}", data=data,
                                     method="POST" if data is not None else "GET",
                                     headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read().decode())

    def clock_probe(self, n=15):
        """Cristian-style offset (laptop - server) from the min-RTT probe over a keep-alive connection."""
        conn = http.client.HTTPConnection(self.host, self.port, timeout=5)
        samples = []
        try:
            for _ in range(n):
                w0 = time.time() * 1000
                p0 = time.perf_counter()
                conn.request("GET", "/api/time")
                t_srv = json.loads(conn.getresponse().read().decode())["t"]
                rtt = (time.perf_counter() - p0) * 1000
                samples.append((rtt, w0 + rtt / 2 - t_srv))
        finally:
            conn.close()
        samples.sort()
        rtts = [s[0] for s in samples]
        return {"offset_ms": round(samples[0][1], 2), "unc_ms": round(samples[0][0] / 2, 2),
                "rtt_min_ms": round(rtts[0], 2), "rtt_median_ms": round(statistics.median(rtts), 2),
                "n": len(samples), "at": time.time()}


def find_browser(explicit=None):
    for p in ([explicit] if explicit else []) + BROWSERS:
        if p and os.path.exists(p):
            return p
    raise SystemExit("No Chrome/Edge found; pass --browser")


def browser_version(exe):
    if os.name == "nt":
        try:
            ps = f"(Get-Item '{exe}').VersionInfo.ProductVersion"
            return subprocess.run(["powershell", "-NoProfile", "-Command", ps],
                                  capture_output=True, text=True, timeout=15).stdout.strip()
        except Exception:  # noqa: BLE001
            return None
    return subprocess.run([exe, "--version"], capture_output=True, text=True).stdout.strip()


# ----------------------------------------------------------------------------- physical-link characterisation
def ping_stats(host, count):
    flag = "-n" if os.name == "nt" else "-c"
    out = subprocess.run(["ping", flag, str(count), host], capture_output=True, text=True,
                         timeout=count * 3 + 10).stdout
    rtts = [float(x) for x in re.findall(r"time[=<]([\d.]+)\s*ms", out)]
    if not rtts:
        return {"sent": count, "received": 0}
    rtts_sorted = sorted(rtts)
    diffs = [abs(a - b) for a, b in zip(rtts, rtts[1:])]
    return {
        "sent": count, "received": len(rtts), "loss_pct": round(100 * (count - len(rtts)) / count, 2),
        "min_ms": min(rtts), "median_ms": statistics.median(rtts), "mean_ms": round(statistics.mean(rtts), 2),
        "p95_ms": rtts_sorted[min(len(rtts) - 1, int(0.95 * len(rtts)))], "max_ms": max(rtts),
        "jitter_ms": round(statistics.mean(diffs), 2) if diffs else 0.0,   # RFC 3550-style mean |delta|
        "note": "Windows ping reports whole milliseconds" if os.name == "nt" else None,
    }


def downlink_throughput(agent, nbytes=30_000_000, repeats=3):
    rates = []
    for _ in range(repeats):
        t0 = time.perf_counter()
        with urllib.request.urlopen(f"http://{agent.host}:{agent.port}/api/blob?bytes={nbytes}", timeout=120) as r:
            got = 0
            while True:
                chunk = r.read(1 << 16)
                if not chunk:
                    break
                got += len(chunk)
        rates.append(got * 8 / (time.perf_counter() - t0) / 1e6)
    return {"bytes": nbytes, "mbps_runs": [round(x, 1) for x in rates], "mbps_median": round(statistics.median(rates), 1)}


def wifi_info():
    if os.name != "nt":
        return None
    out = subprocess.run(["netsh", "wlan", "show", "interfaces"], capture_output=True, text=True).stdout
    keep = ("Description", "State", "Radio type", "Band", "Channel", "Receive rate (Mbps)",
            "Transmit rate (Mbps)", "Signal", "Authentication")
    info = {}
    for line in out.splitlines():
        if ":" in line:
            k, v = line.split(":", 1)
            k = k.strip()
            if k in keep and k not in info:
                info[k] = v.strip()
    return info or None


def characterise_link(agent, server):
    print("[link] characterising the physical laptop <-> server path ...")
    link = {"ping": ping_stats(server, 30), "http_clock_probe": agent.clock_probe(40),
            "downlink_tcp": downlink_throughput(agent), "wifi": wifi_info()}
    p = link["ping"]
    print(f"[link] ping min/median/p95 = {p.get('min_ms')}/{p.get('median_ms')}/{p.get('p95_ms')} ms, "
          f"loss {p.get('loss_pct')}%, downlink ~{link['downlink_tcp']['mbps_median']} Mbps, "
          f"clock offset {link['http_clock_probe']['offset_ms']:+.1f} ms")
    return link


# ----------------------------------------------------------------------------- one run
def tc_delta(before, after):
    out = {}
    for proto, a in (after.get("counters") or {}).items():
        b = (before.get("counters") or {}).get(proto)
        if b and a.get("bytes") is not None and a["bytes"] >= b["bytes"]:
            out[proto] = {k: a[k] - b[k] for k in ("bytes", "packets", "drops")}
    return out


def do_run(args, agent, browser_exe, run, page_port):
    run_id = run["run_id"]
    agent.call("/api/netem/apply", {"profile": run["profile"]})
    agent.call("/api/kick", {})
    time.sleep(1.5)
    clock_before = agent.clock_probe(10)
    tc_before = agent.call("/api/netem")

    _Handler.expected_run, _Handler.report = run_id, None
    _Handler.event.clear()
    url = (f"http://127.0.0.1:{page_port}/index.html?autorun=1&server={args.server}&agentPort={args.agent_port}"
           f"&duration={args.duration}&warmup={args.warmup}&buffer={run['buffer']}"
           f"&profile={run['profile']}&run={run_id}")
    if args.protocol != "all":
        url += f"&protocol={args.protocol}"
    if args.page_params:
        url += "&" + args.page_params.lstrip("&")
    profile_dir = tempfile.mkdtemp(prefix="cs6048_chrome_")
    cmd = [browser_exe, f"--user-data-dir={profile_dir}", "--no-first-run", "--no-default-browser-check",
           "--autoplay-policy=no-user-gesture-required", "--disable-background-timer-throttling",
           "--disable-renderer-backgrounding", "--disable-backgrounding-occluded-windows",
           "--mute-audio", "--window-size=1600,1000", url]
    if not args.headed:
        cmd.insert(1, "--headless=new")
    t_start = time.time()
    proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        got = _Handler.event.wait(timeout=args.duration + 45)
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
        shutil.rmtree(profile_dir, ignore_errors=True)
    tc_after = agent.call("/api/netem")
    clock_after = agent.clock_probe(10)
    return {
        **run,
        "status": "ok" if got and _Handler.report else "timeout",
        "profile_spec": PROFILES[run["profile"]],
        "started_at": datetime.fromtimestamp(t_start).isoformat(timespec="seconds"),
        "duration_s": args.duration, "warmup_s": args.warmup,
        "harness": {"clock_before": clock_before, "clock_after": clock_after, "tc_before": tc_before,
                    "tc_after": tc_after, "tc_delta": tc_delta(tc_before, tc_after),
                    "tc_interval_s": (tc_after.get("server_time_ms", 0) - tc_before.get("server_time_ms", 0)) / 1000,
                    "wall_s": round(time.time() - t_start, 2)},
        "browser": _Handler.report,
    }


# ----------------------------------------------------------------------------- campaign
def build_plan(conditions, reps, seed):
    runs = []
    for rep in range(1, reps + 1):
        order = list(conditions)
        random.Random(seed * 1000 + rep).shuffle(order)
        for prof, buf in order:
            runs.append({"run_id": f"r{rep:02d}_{prof}_b{buf}", "rep": rep, "profile": prof, "buffer": buf})
    for i, r in enumerate(runs):
        r["order_index"] = i
    return runs


def parse_conditions(spec):
    out = []
    for item in spec.split(","):
        prof, buf = item.split(":")
        if prof not in PROFILES:
            raise SystemExit(f"unknown profile {prof}")
        out.append((prof, float(buf)))
    return out


def rebuild_csv(cdir):
    rows = []
    for f in sorted((cdir / "runs").glob("*.json")):
        rows.extend(run_rows(json.loads(f.read_text(encoding="utf-8"))))
    if not rows:
        return 0
    keys = []
    for r in rows:
        keys.extend(k for k in r if k not in keys)
    with open(cdir / "runs.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=keys)
        w.writeheader()
        w.writerows(rows)
    return len(rows)


def fmt_row(r):
    if not r.get("ok"):
        return f"{r['protocol']:>7}: FAILED ({r.get('fail_reason')})"
    return (f"{r['protocol']:>7}: lat {r['lat_mean_ms']:7.0f} ms (p95 {r['lat_p95_ms']:6.0f}) | "
            f"stall {r['stall_ratio_pct']:5.1f}% ({r['stall_count']}) | TTFF {r['ttff_ms']} ms | "
            f"fps {r['fps']:4.1f} | decode {100 * r['decode_rate']:.0f}% | wire {r.get('wire_kbps', 0):5.0f} kbps")


def keep_awake(on):
    """Asks Windows not to sleep while the campaign runs (no setting is changed; ends with the process)."""
    if os.name != "nt":
        return
    import ctypes
    es_continuous, es_system_required = 0x80000000, 0x00000001
    ctypes.windll.kernel32.SetThreadExecutionState(es_continuous | (es_system_required if on else 0))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--server", default="10.21.232.54")
    ap.add_argument("--agent-port", type=int, default=9000)
    ap.add_argument("--campaign", default=None, help="campaign name (existing name = resume)")
    ap.add_argument("--plan", choices=sorted(PLANS), default="full")
    ap.add_argument("--conditions", default=None, help="custom list, e.g. baseline:0.5,cellular_4g:1.0")
    ap.add_argument("--reps", type=int, default=5)
    ap.add_argument("--duration", type=int, default=45, help="seconds of playback per run")
    ap.add_argument("--warmup", type=int, default=10, help="seconds excluded from steady-state metrics")
    ap.add_argument("--seed", type=int, default=6048)
    ap.add_argument("--page-port", type=int, default=3000)
    ap.add_argument("--browser", default=None)
    ap.add_argument("--headed", action="store_true", help="show the browser window (debugging)")
    ap.add_argument("--protocol", choices=["all", "webrtc", "llhls", "httpflv"], default="all",
                    help="play only one protocol (interference control experiments)")
    ap.add_argument("--page-params", default="", help="extra query parameters for the player page, e.g. hlsMaxLat=0.8")
    ap.add_argument("--skip-link-test", action="store_true")
    ap.add_argument("--retry-failed", action="store_true", help="re-run runs whose status is not ok")
    args = ap.parse_args()

    agent = Agent(args.server, args.agent_port)
    status = agent.call("/api/status")
    if not (status.get("publisher") or {}).get("active"):
        raise SystemExit(f"Server is not publishing the test stream: {json.dumps(status, indent=2)}")
    browser_exe = find_browser(args.browser)

    name = args.campaign or f"{args.plan}_{datetime.now():%Y%m%d_%H%M}"
    cdir = CAMPAIGNS_DIR / name
    (cdir / "runs").mkdir(parents=True, exist_ok=True)
    meta_path = cdir / "meta.json"
    if meta_path.exists():
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        plan = meta["plan"]
        args.duration, args.warmup = meta["duration_s"], meta["warmup_s"]
        args.protocol, args.page_params = meta.get("protocol", "all"), meta.get("page_params", "")
        print(f"[campaign] resuming '{name}' ({len(plan)} runs planned)")
    else:
        conditions = parse_conditions(args.conditions) if args.conditions else PLANS[args.plan]
        plan = build_plan(conditions, args.reps, args.seed)
        for r in plan:
            r["campaign"] = name
        meta = {
            "campaign": name, "created": datetime.now().isoformat(timespec="seconds"),
            "plan_name": args.conditions or args.plan, "reps": args.reps, "seed": args.seed,
            "duration_s": args.duration, "warmup_s": args.warmup,
            "protocol": args.protocol, "page_params": args.page_params,
            "conditions": [list(c) for c in conditions], "plan": plan, "profiles": PROFILES,
            "topology": {
                "server": {"role": "media server + stream source + tc/netem", "ip": args.server,
                           "host": status.get("host"), "cpu": status.get("cpu"), "kernel": status.get("kernel"),
                           "srs_version": status.get("srs_version"), "containers": status.get("containers")},
                "client": {"role": "viewer (headless Chromium) + campaign runner", "host": platform.node(),
                           "os": platform.platform(), "cpu": platform.processor(),
                           "browser": browser_exe, "browser_version": browser_version(browser_exe)},
                "stream": {"video": "H.264 Baseline 1280x720@30, CBR 1800 kbps, GOP 15 (0.5 s), no B-frames",
                           "audio": "AAC-LC 96 kbps 44.1 kHz stereo", "source": status.get("publisher")},
            },
        }
        if not args.skip_link_test:
            meta["physical_link"] = characterise_link(agent, args.server)
        meta_path.write_text(json.dumps(meta, indent=2), encoding="utf-8")
        print(f"[campaign] '{name}': {len(meta['conditions'])} conditions x {args.reps} reps = {len(plan)} runs, "
              f"{args.duration}s each (warm-up {args.warmup}s)")

    httpd = http.server.ThreadingHTTPServer(("127.0.0.1", args.page_port), _Handler)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()

    def done(r):
        f = cdir / "runs" / f"{r['run_id']}.json"
        if not f.exists():
            return False
        if args.retry_failed:
            return json.loads(f.read_text(encoding="utf-8")).get("status") == "ok"
        return True

    todo = [r for r in plan if not done(r)]
    print(f"[campaign] {len(plan) - len(todo)} done, {len(todo)} to go. Results -> {cdir}")
    durations = []
    keep_awake(True)
    try:
        for i, run in enumerate(todo, 1):
            eta = ""
            if durations:
                rem = statistics.mean(durations) * (len(todo) - i + 1)
                eta = f" | ETA {int(rem // 60)}m{int(rem % 60):02d}s"
            print(f"\n[{i}/{len(todo)}] {run['run_id']} (profile={run['profile']}, buffer={run['buffer']}s){eta}")
            t0 = time.time()
            result = do_run(args, agent, browser_exe, run, args.page_port)
            if result["status"] != "ok":
                print("   no report received; retrying once ...")
                result = do_run(args, agent, browser_exe, run, args.page_port)
            (cdir / "runs" / f"{run['run_id']}.json").write_text(json.dumps(result), encoding="utf-8")
            for row in run_rows(result):
                print("   " + fmt_row(row))
            ci = (result.get("browser") or {}).get("meta", {}).get("clock") or []
            if ci:
                print(f"   clock offset {ci[0]['offsetMs']:+.1f} +/- {ci[0]['uncMs']:.1f} ms, "
                      f"path RTT {ci[0]['rttMinMs']:.1f} ms")
            durations.append(time.time() - t0)
    except KeyboardInterrupt:
        print("\n[campaign] interrupted - resume later with the same --campaign")
    finally:
        keep_awake(False)
        try:
            agent.call("/api/netem/apply", {"profile": "baseline"})
        except Exception as e:  # noqa: BLE001
            print(f"[campaign] WARNING: could not reset server profile: {e}")
        httpd.shutdown()
        n = rebuild_csv(cdir)
        print(f"[campaign] {n} protocol-run rows in {cdir / 'runs.csv'}")


if __name__ == "__main__":
    main()
