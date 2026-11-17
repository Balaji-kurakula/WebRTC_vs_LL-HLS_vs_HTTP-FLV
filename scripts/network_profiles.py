#!/usr/bin/env python3
"""
Reproducible network-emulation profiles (Linux tc/netem) for the two-machine testbed.

The profiles are applied on the SERVER (lab PC) inside the SRS/MediaMTX container's network
namespace, on the egress of `eth0`, i.e. on the server -> viewer (downlink) direction.
Because ACKs / RTCP from the viewer return unshaped, `delay_ms` is exactly the extra RTT added
on top of the physical path.

A 4-band `prio` root qdisc gives every protocol its own, identically-configured netem pipe so
that the three protocols never compete for the same emulated bottleneck:
    band 1:1  unshaped     RTMP ingest (:1935) and all host-local traffic (docker gateway)
    band 1:2  netem 20:    WebRTC        (UDP :8000 media, :1985 signalling)
    band 1:3  netem 30:    HTTP-FLV      (TCP :8080 inside the container, :18080 on the host)
    band 1:4  netem 40:    Apple LL-HLS  (TCP :8888)
The structure is installed for EVERY profile (baseline uses pass-through netem) so per-protocol
on-the-wire byte / packet / drop counters are always available from `tc -s`.

This module is imported by `server/agent.py` (which executes the commands) and can be used from
the laptop as a CLI that talks to the agent:
    python scripts/network_profiles.py list
    python scripts/network_profiles.py --server 10.21.232.54 apply cellular_4g
    python scripts/network_profiles.py --server 10.21.232.54 status
    python scripts/network_profiles.py --server 10.21.232.54 reset
"""

import argparse
import json
import sys
import urllib.request

# rate_kbps=None means "no rate cap". delay/jitter are one-way on the downlink (= added RTT).
PROFILES = {
    "baseline": {
        "description": "No emulated impairment (physical path only)",
        "rate_kbps": None, "delay_ms": 0, "jitter_ms": 0, "loss_pct": 0.0,
    },
    # --- Bandwidth sweep (20 ms added RTT, 0% loss). Stream is ~1.9 Mbps (1800k video + 96k audio)
    "bw_5m": {
        "description": "5.0 Mbps, +20 ms RTT, 0% loss (reference link)",
        "rate_kbps": 5000, "delay_ms": 20, "jitter_ms": 2, "loss_pct": 0.0,
    },
    "bw_3m": {
        "description": "3.0 Mbps, +20 ms RTT, 0% loss (~1.6x stream bitrate)",
        "rate_kbps": 3000, "delay_ms": 20, "jitter_ms": 2, "loss_pct": 0.0,
    },
    "bw_2.2m": {
        "description": "2.2 Mbps, +20 ms RTT, 0% loss (~1.15x stream bitrate, tight)",
        "rate_kbps": 2200, "delay_ms": 20, "jitter_ms": 2, "loss_pct": 0.0,
    },
    "bw_1.6m": {
        "description": "1.6 Mbps, +20 ms RTT, 0% loss (below stream bitrate, overload)",
        "rate_kbps": 1600, "delay_ms": 20, "jitter_ms": 2, "loss_pct": 0.0,
    },
    # --- RTT sweep (5 Mbps, 0% loss). bw_5m is the 20 ms point.
    "rtt_80ms": {
        "description": "5.0 Mbps, +80 ms RTT, 0% loss (cross-country)",
        "rate_kbps": 5000, "delay_ms": 80, "jitter_ms": 2, "loss_pct": 0.0,
    },
    "rtt_160ms": {
        "description": "5.0 Mbps, +160 ms RTT, 0% loss (intercontinental)",
        "rate_kbps": 5000, "delay_ms": 160, "jitter_ms": 2, "loss_pct": 0.0,
    },
    "rtt_300ms": {
        "description": "5.0 Mbps, +300 ms RTT, 0% loss (satellite-like)",
        "rate_kbps": 5000, "delay_ms": 300, "jitter_ms": 2, "loss_pct": 0.0,
    },
    # --- Random loss sweep (5 Mbps, 20 ms). bw_5m is the 0% point.
    "loss_1pct": {
        "description": "5.0 Mbps, +20 ms RTT, 1% random loss",
        "rate_kbps": 5000, "delay_ms": 20, "jitter_ms": 2, "loss_pct": 1.0,
    },
    "loss_3pct": {
        "description": "5.0 Mbps, +20 ms RTT, 3% random loss",
        "rate_kbps": 5000, "delay_ms": 20, "jitter_ms": 2, "loss_pct": 3.0,
    },
    "loss_5pct": {
        "description": "5.0 Mbps, +20 ms RTT, 5% random loss",
        "rate_kbps": 5000, "delay_ms": 20, "jitter_ms": 2, "loss_pct": 5.0,
    },
    # --- Composite mobile profile (same parameters as the single-machine study)
    "cellular_4g": {
        "description": "4G/LTE-like: 2.2 Mbps, +70 ms RTT, 25 ms jitter, 0.8% loss",
        "rate_kbps": 2200, "delay_ms": 70, "jitter_ms": 25, "loss_pct": 0.8,
    },
}

INTERFACE = "eth0"
NETEM_LIMIT_PKTS = 1000

# netem handle -> protocol
BANDS = [
    ("1:2", "20:", "webrtc"),
    ("1:3", "30:", "httpflv"),
    ("1:4", "40:", "llhls"),
]
# container-side source port -> band
PORT_BAND_MAP = [
    (8000, "1:2"),  # WebRTC media (UDP)
    (1985, "1:2"),  # WebRTC signalling (SRS HTTP API)
    (8080, "1:3"),  # HTTP-FLV
    (8888, "1:4"),  # LL-HLS
]
HANDLE_TO_PROTO = {h: p for _, h, p in BANDS}


def netem_args(p):
    args = []
    if p["rate_kbps"]:
        args += ["rate", f"{p['rate_kbps']}kbit"]
    if p["delay_ms"] > 0:
        args += ["delay", f"{p['delay_ms']}ms"]
        if p["jitter_ms"] > 0:
            args += [f"{p['jitter_ms']}ms"]
    if p["loss_pct"] > 0:
        args += ["loss", f"{p['loss_pct']}%"]
    args += ["limit", str(NETEM_LIMIT_PKTS)]
    return args


def build_tc_commands(name, unshaped_dst=None):
    """Returns the list of `tc ...` argument lists that install profile `name` from scratch.

    `unshaped_dst` (e.g. the docker bridge gateway 172.17.0.1) keeps host-local traffic such as the
    agent's own SRS API calls out of the emulated pipes.
    """
    if name not in PROFILES:
        raise ValueError(f"Unknown profile '{name}'. Choices: {list(PROFILES)}")
    p = PROFILES[name]
    cmds = [
        ["tc", "qdisc", "replace", "dev", INTERFACE, "root", "handle", "1:", "prio", "bands", "4",
         "priomap"] + ["0"] * 16,
    ]
    for band, handle, _ in BANDS:
        cmds.append(["tc", "qdisc", "add", "dev", INTERFACE, "parent", band, "handle", handle, "netem"]
                    + netem_args(p))
    if unshaped_dst:
        cmds.append(["tc", "filter", "add", "dev", INTERFACE, "protocol", "ip", "parent", "1:0", "prio", "1",
                     "u32", "match", "ip", "dst", f"{unshaped_dst}/32", "flowid", "1:1"])
    for sport, flowid in PORT_BAND_MAP:
        cmds.append(["tc", "filter", "add", "dev", INTERFACE, "protocol", "ip", "parent", "1:0", "prio", "2",
                     "u32", "match", "ip", "sport", str(sport), "0xffff", "flowid", flowid])
    return cmds


def reset_commands():
    return [["tc", "qdisc", "del", "dev", INTERFACE, "root"]]


# ---------------------------------------------------------------- CLI (talks to the server agent)

def _agent_call(server, port, path, payload=None):
    url = f"http://{server}:{port}{path}"
    data = json.dumps(payload).encode() if payload is not None else None
    req = urllib.request.Request(url, data=data, method="POST" if data is not None else "GET",
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=15) as r:
        return json.loads(r.read().decode())


def list_profiles():
    print(f"{'Profile':<13} | {'Rate':>10} | {'Added RTT':>14} | {'Loss':>5} | Description")
    print("-" * 100)
    for k, v in PROFILES.items():
        rate = f"{v['rate_kbps']} kbps" if v["rate_kbps"] else "unlimited"
        dj = f"{v['delay_ms']}+/-{v['jitter_ms']} ms"
        print(f"{k:<13} | {rate:>10} | {dj:>14} | {v['loss_pct']:>4.1f}% | {v['description']}")


def main():
    ap = argparse.ArgumentParser(description="Network profile manager (via the server agent)")
    ap.add_argument("--server", default="10.21.232.54")
    ap.add_argument("--agent-port", type=int, default=9000)
    ap.add_argument("action", choices=["list", "apply", "reset", "status"])
    ap.add_argument("profile", nargs="?", default="baseline")
    a = ap.parse_args()
    if a.action == "list":
        list_profiles()
    elif a.action == "apply":
        print(json.dumps(_agent_call(a.server, a.agent_port, "/api/netem/apply", {"profile": a.profile}), indent=2))
    elif a.action == "reset":
        print(json.dumps(_agent_call(a.server, a.agent_port, "/api/netem/apply", {"profile": "baseline"}), indent=2))
    elif a.action == "status":
        print(json.dumps(_agent_call(a.server, a.agent_port, "/api/netem"), indent=2))


if __name__ == "__main__":
    sys.exit(main())
