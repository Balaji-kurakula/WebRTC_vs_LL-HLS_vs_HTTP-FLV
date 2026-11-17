#!/usr/bin/env python3
"""
QoE metrics computed from the raw per-frame browser telemetry of one run.

The definitions mirror `summarize()` in web/index.html and are applied identically to all three
protocols:
  * Measurement window: [warm-up, end of run], but never before the protocol's first frame.
  * Latency: per presented frame, (display time on the server clock) - (capture time in barcode).
  * Stall: a gap > 200 ms between consecutively presented frames (rendering-side definition,
    independent of player internals; cf. W3C webrtc-stats freezeCount). Stall time is clipped
    to the window; stall ratio = stall time / window length.
  * A protocol that never renders a frame during the run is counted as a failure
    (stall ratio 100 %, no latency).
"""

import numpy as np

STALL_GAP_MS = 200


def _clip_stalls(stalls, win_start, win_end):
    count, total, longest = 0, 0.0, 0.0
    for s in stalls:
        start, dur = s[0], s[1]
        a, b = max(start, win_start), min(start + dur, win_end)
        if b > a:
            count += 1
            total += b - a
            longest = max(longest, b - a)
    return count, total, longest


def protocol_metrics(rep, warmup_ms, end_ms):
    """rep = report['protocols'][proto] from the browser."""
    out = {"ttff_ms": rep.get("ttffMs"), "waiting_events": rep.get("waitingEvents"),
           "decode_fail": rep.get("decodeFail"), "invalid_lat": rep.get("invalidLat")}
    first = rep.get("firstFrameRelMs")
    if first is None:
        out.update({"ok": False, "fail_reason": "no_first_frame", "stall_ratio_pct": 100.0,
                    "window_s": (end_ms - warmup_ms) / 1000})
        return out

    win_start, win_end = max(warmup_ms, first), end_ms
    win_ms = win_end - win_start
    if win_ms <= 1000:
        out.update({"ok": False, "fail_reason": "first_frame_after_warmup_window", "stall_ratio_pct": 100.0,
                    "window_s": win_ms / 1000})
        return out

    # frame entry: [t_rel_ms, latency (number | None = not sampled | -1 = unreadable), presentedFrames]
    frames = [f for f in rep.get("frames", []) if win_start <= f[0] <= win_end]
    sampled = [f[1] for f in frames if f[1] is not None]
    lats = np.array([l for l in sampled if l >= 0], dtype=float)
    n_frames = len(frames)
    pfs = [f[2] for f in frames if len(f) > 2 and f[2] is not None]
    presented = (pfs[-1] - pfs[0]) if len(pfs) > 1 else n_frames
    count, stall_ms, longest = _clip_stalls(rep.get("stalls", []), win_start, win_end)
    bufs = [b for t, b in rep.get("buffer", []) if win_start <= t <= win_end and b is not None]

    out.update({
        "ok": len(lats) > 0,
        "fail_reason": None if len(lats) else "no_decoded_latency",
        "window_s": win_ms / 1000,
        "frames": int(presented),
        "fps": presented / (win_ms / 1000),
        "decode_rate": (len(lats) / len(sampled)) if sampled else 0.0,
        "lat_n": int(len(lats)),
        "lat_mean_ms": float(lats.mean()) if len(lats) else None,
        "lat_p50_ms": float(np.percentile(lats, 50)) if len(lats) else None,
        "lat_p95_ms": float(np.percentile(lats, 95)) if len(lats) else None,
        "lat_p99_ms": float(np.percentile(lats, 99)) if len(lats) else None,
        "lat_std_ms": float(lats.std(ddof=1)) if len(lats) > 1 else None,
        "lat_min_ms": float(lats.min()) if len(lats) else None,
        "lat_max_ms": float(lats.max()) if len(lats) else None,
        "stall_count": count,
        "stall_ms": stall_ms,
        "stall_ratio_pct": 100.0 * stall_ms / win_ms,
        "stalls_per_min": count / (win_ms / 60000),
        "longest_stall_ms": longest,
        "buffer_mean_s": float(np.mean(bufs)) if bufs else None,
    })
    rtc = rep.get("rtcStats")
    if rtc:
        for k in ("packetsLost", "packetsReceived", "nackCount", "pliCount", "freezeCount", "framesDropped"):
            out[f"rtc_{k}"] = rtc.get(k)
        if rtc.get("jitterBufferEmittedCount"):
            out["rtc_jb_target_ms"] = 1000 * (rtc.get("jitterBufferTargetDelay") or 0) / rtc["jitterBufferEmittedCount"]
    return out


def clock_info(meta):
    """Clock offset used by the browser, its uncertainty, and drift between start/end calibrations."""
    cal = meta.get("clock") or []
    start = meta.get("startedWallMs")
    if not cal or start is None:
        return {"clock_offset_ms": None, "clock_unc_ms": None, "clock_drift_ms": None, "path_rtt_min_ms": None}
    before = [c for c in cal if c["atWallMs"] <= start + 500] or cal[:1]
    after = [c for c in cal if c["atWallMs"] > start + 500]
    c0 = before[-1]
    return {
        "clock_offset_ms": c0["offsetMs"],
        "clock_unc_ms": c0["uncMs"],
        "clock_drift_ms": (after[-1]["offsetMs"] - c0["offsetMs"]) if after else None,
        "path_rtt_min_ms": c0["rttMinMs"],
    }


def run_rows(run):
    """Flattens one saved run (harness JSON) into one row per protocol."""
    base = {k: run.get(k) for k in ("campaign", "run_id", "rep", "order_index", "profile", "buffer", "status")}
    browser = run.get("browser") or {}
    meta = browser.get("meta", {})
    base.update(clock_info(meta) if meta else {})
    rows = []
    if run.get("status") != "ok" or not browser:
        for proto in run.get("protocols", ["webrtc", "llhls", "httpflv"]):
            rows.append({**base, "protocol": proto, "ok": False, "fail_reason": run.get("status")})
        return rows
    warmup_ms = 1000 * (meta.get("warmupSec") or 0)
    end_ms = meta.get("endRelMs")
    # Prefer the counters the page snapshotted exactly at the window edges; fall back to the
    # harness's before/after snapshots (whole session) for older runs.
    ww = meta.get("wireWindow") or {}
    a, b = ww.get("start") or {}, ww.get("end") or {}
    if a.get("counters") and b.get("counters") and b.get("serverTimeMs", 0) > a.get("serverTimeMs", 0):
        tc = {p: {k: b["counters"][p][k] - a["counters"][p][k] for k in ("bytes", "packets", "drops")}
              for p in b["counters"] if p in a["counters"]}
        span_s = (b["serverTimeMs"] - a["serverTimeMs"]) / 1000
    else:
        tc = (run.get("harness") or {}).get("tc_delta") or {}
        span_s = end_ms / 1000 if end_ms else None
    for proto, rep in browser.get("protocols", {}).items():
        row = {**base, "protocol": proto}
        row.update(protocol_metrics(rep, warmup_ms, end_ms))
        c = tc.get(proto)
        if c and span_s:
            row["wire_kbps"] = c["bytes"] * 8 / span_s / 1000
            row["wire_packets"] = c["packets"]
            row["wire_drops"] = c["drops"]
            row["wire_drop_pct"] = 100 * c["drops"] / (c["packets"] + c["drops"]) if (c["packets"] + c["drops"]) else 0.0
        rows.append(row)
    return rows
