#!/usr/bin/env python3
"""
Analysis of a two-machine measurement campaign (results/campaigns/<name>/).

Recomputes every metric from the raw per-run JSON files (single source of truth: scripts/metrics.py),
aggregates the repetitions of each condition, runs paired protocol comparisons, and writes:

  analysis/runs_all.csv            every protocol x run, all metrics (the "all runs" table)
  analysis/summary_by_condition.csv  mean, std, 95% CI per condition x protocol
  analysis/pairwise.csv            paired differences between protocols per condition (t-test)
  analysis/summary.md              human-readable summary (setup, tables, data quality)
  analysis/fig*.png                figures

Usage:  python scripts/analyze_campaign.py <campaign_name>  [--compare other_campaign]
"""

import argparse
import json
import math
import sys
from pathlib import Path

import matplotlib
import matplotlib.ticker
import numpy as np
import pandas as pd

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from scipy import stats  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent))
from metrics import run_rows  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
CAMPAIGNS = ROOT / "results" / "campaigns"

PROTOS = ["webrtc", "llhls", "httpflv"]
NAME = {"webrtc": "WebRTC", "llhls": "LL-HLS", "httpflv": "HTTP-FLV"}
# Validated categorical slots 1-3 (all-pairs CVD-safe); markers give a second, non-colour cue.
COLOR = {"webrtc": "#2a78d6", "llhls": "#eb6834", "httpflv": "#1baf7a"}
MARKER = {"webrtc": "o", "llhls": "s", "httpflv": "^"}
INK, INK2, GRID, SURFACE = "#0b0b0b", "#52514e", "#e4e3df", "#fcfcfb"
SOURCE_KBPS = 1896  # 1800k video + 96k audio (encoder target)

SWEEPS = {
    "Bandwidth cap": [("bw_5m", "5.0"), ("bw_3m", "3.0"), ("bw_2.2m", "2.2"), ("bw_1.6m", "1.6")],
    "Added RTT": [("bw_5m", "20"), ("rtt_80ms", "80"), ("rtt_160ms", "160"), ("rtt_300ms", "300")],
    "Random loss": [("bw_5m", "0"), ("loss_1pct", "1"), ("loss_3pct", "3"), ("loss_5pct", "5")],
}
SWEEP_UNITS = {"Bandwidth cap": "Mbps", "Added RTT": "ms", "Random loss": "%"}

plt.rcParams.update({
    "font.family": "sans-serif", "font.size": 9.5, "axes.titlesize": 10.5, "axes.titleweight": "bold",
    "axes.labelsize": 9.5, "axes.edgecolor": "#b9b8b3", "axes.labelcolor": INK2, "xtick.color": INK2,
    "ytick.color": INK2, "axes.grid": True, "grid.color": GRID, "grid.linewidth": 0.8,
    "axes.spines.top": False, "axes.spines.right": False, "figure.facecolor": SURFACE,
    "axes.facecolor": SURFACE, "savefig.facecolor": SURFACE, "figure.dpi": 160, "legend.frameon": False,
    "lines.linewidth": 2.0, "lines.markersize": 6.5,
})


# ----------------------------------------------------------------------------- loading
def load_campaign(name):
    cdir = CAMPAIGNS / name
    meta = json.loads((cdir / "meta.json").read_text(encoding="utf-8"))
    runs = [json.loads(f.read_text(encoding="utf-8")) for f in sorted((cdir / "runs").glob("*.json"))]
    df = pd.DataFrame([row for r in runs for row in run_rows(r)])
    df["cond"] = df["profile"] + " @ " + df["buffer"].map(lambda b: f"{b:g}s")
    return cdir, meta, runs, df


def ci95(x):
    x = np.asarray([v for v in x if v is not None and not (isinstance(v, float) and math.isnan(v))], float)
    n = len(x)
    if n == 0:
        return np.nan, np.nan, np.nan, 0
    m = x.mean()
    if n == 1:
        return m, np.nan, np.nan, 1
    s = x.std(ddof=1)
    h = stats.t.ppf(0.975, n - 1) * s / math.sqrt(n)
    return m, s, h, n


METRICS = ["lat_mean_ms", "lat_p50_ms", "lat_p95_ms", "stall_ratio_pct", "stall_count", "ttff_ms", "fps",
           "buffer_mean_s", "wire_kbps", "wire_drop_pct", "decode_rate"]


def summarize(df):
    rows = []
    for (prof, buf, proto), g in df.groupby(["profile", "buffer", "protocol"], sort=False):
        r = {"profile": prof, "buffer": buf, "protocol": proto, "runs": len(g), "ok_runs": int(g["ok"].sum())}
        for m in METRICS:
            if m not in g:
                continue
            mean, sd, h, n = ci95(g[m].tolist())
            r.update({f"{m}_mean": mean, f"{m}_sd": sd, f"{m}_ci95": h, f"{m}_n": n})
        rows.append(r)
    return pd.DataFrame(rows)


def pairwise(df):
    """Paired comparison per condition: the 3 protocols run simultaneously in each run -> pair by run_id."""
    out = []
    for (prof, buf), g in df.groupby(["profile", "buffer"], sort=False):
        for metric in ("lat_mean_ms", "stall_ratio_pct"):
            piv = g.pivot_table(index="run_id", columns="protocol", values=metric)
            for a, b in (("webrtc", "llhls"), ("webrtc", "httpflv"), ("httpflv", "llhls")):
                if a not in piv or b not in piv:
                    continue
                d = (piv[a] - piv[b]).dropna()
                if len(d) == 0:
                    continue
                mean, sd, h, n = ci95(d.tolist())
                p = stats.ttest_1samp(d, 0).pvalue if n >= 2 and sd > 0 else np.nan
                out.append({"profile": prof, "buffer": buf, "metric": metric, "a": a, "b": b, "n_pairs": n,
                            "mean_diff_a_minus_b": mean, "ci95": h, "p_paired_t": p,
                            "a_better_in_runs": int((d < 0).sum()), "b_better_in_runs": int((d > 0).sum())})
    return pd.DataFrame(out)


# ----------------------------------------------------------------------------- figure helpers
def get(summ, prof, buf, proto, m):
    s = summ[(summ.profile == prof) & (np.isclose(summ.buffer, buf)) & (summ.protocol == proto)]
    if s.empty or f"{m}_mean" not in s:
        return np.nan, np.nan
    return s.iloc[0][f"{m}_mean"], s.iloc[0][f"{m}_ci95"]


def legend_handles(ax):
    for p in PROTOS:
        ax.plot([], [], color=COLOR[p], marker=MARKER[p], label=NAME[p])


def clamp_err(vals, half, lo=0.0, hi=None):
    """Asymmetric error bars for mean ± CI half-width, clipped to the physically possible range
    (with 2-3 repetitions a t-interval can otherwise extend below 0 or above 100 %)."""
    v = np.atleast_1d(np.asarray(vals, float))
    h = np.nan_to_num(np.atleast_1d(np.asarray(half, float)))
    lower = np.minimum(h, v - lo)
    upper = h if hi is None else np.minimum(h, hi - v)
    return np.vstack([np.maximum(lower, 0), np.maximum(upper, 0)])


def set_log_seconds(ax):
    """Log x-axis with plain-number second ticks (0.2, 0.5, 1, 2, 5 ...)."""
    ax.set_xscale("log")
    ax.xaxis.set_major_locator(matplotlib.ticker.FixedLocator([0.1, 0.2, 0.5, 1, 2, 5, 10, 20, 50]))
    ax.xaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda v, _: f"{v:g}"))
    ax.xaxis.set_minor_formatter(matplotlib.ticker.NullFormatter())


def save(fig, path):
    fig.savefig(path, bbox_inches="tight")
    plt.close(fig)
    print(f"[plot] {path.name}")


def fig_tradeoff(summ, out):
    """Latency vs stall ratio as the client buffer target is varied (the core trade-off)."""
    panels = [p for p in ("baseline", "cellular_4g") if p in set(summ.profile)]
    panels = [p for p in panels if summ[summ.profile == p].buffer.nunique() >= 2]
    if not panels:
        return
    fig, axes = plt.subplots(1, len(panels), figsize=(6.2 * len(panels), 4.6), squeeze=False)
    for ax, prof in zip(axes[0], panels):
        bufs = sorted(summ[summ.profile == prof].buffer.unique())
        for p in PROTOS:
            pts = [(b, *get(summ, prof, b, p, "lat_mean_ms"), *get(summ, prof, b, p, "stall_ratio_pct")) for b in bufs]
            pts = [t for t in pts if not np.isnan(t[1])]
            if not pts:
                continue
            b_, x, xe, y, ye = zip(*pts)
            # Markers only (no connecting line: the points are not ordered in latency), stall-ratio CI bars only
            # (latency CIs are in fig2); points lying on the zero-stall line are not labelled, their x is ~ the target.
            ax.errorbar(np.array(x) / 1000, y, yerr=clamp_err(y, ye, 0, 100), color=COLOR[p], linestyle="none",
                        marker=MARKER[p], markersize=8, capsize=2.5, elinewidth=1, markeredgecolor=SURFACE,
                        markeredgewidth=1.2, label=NAME[p])
            for bb, xx, yy in zip(b_, x, y):
                if yy >= 2:
                    ax.annotate(f"{bb:g}s", (xx / 1000, yy), textcoords="offset points", xytext=(6, 4), fontsize=8,
                                color=INK2)
        ax.set_title(f"{prof}: latency vs. stalls as buffer target varies")
        ax.set_xlabel("Mean end-to-end latency (s)")
        ax.set_ylabel("Stall ratio (% of playback time)")
        ax.set_ylim(bottom=-1)
        ax.set_xlim(left=0)
    axes[0][0].legend(loc="upper right")
    fig.text(0.01, -0.02, "Points = mean of repetitions (one per buffer target 0.2-3.5 s), bars = 95% CI of the stall ratio; "
             "labels = buffer target. Lower-left is better.", fontsize=8, color=INK2)
    fig.tight_layout()
    save(fig, out / "fig1_latency_vs_stall_tradeoff.png")


def fig_buffer_sweep(summ, out):
    panels = [p for p in ("baseline", "cellular_4g") if p in set(summ.profile)
              and summ[summ.profile == p].buffer.nunique() >= 2]
    if not panels:
        return
    fig, axes = plt.subplots(2, len(panels), figsize=(5.6 * len(panels), 6.4), squeeze=False, sharex=True)
    for c, prof in enumerate(panels):
        bufs = sorted(summ[summ.profile == prof].buffer.unique())
        for r, (m, lab, scale) in enumerate([("lat_mean_ms", "Mean latency (s)", 1000), ("stall_ratio_pct", "Stall ratio (%)", 1)]):
            ax = axes[r][c]
            for p in PROTOS:
                ys = np.array([get(summ, prof, b, p, m) for b in bufs], float)
                ax.errorbar(bufs, ys[:, 0] / scale, yerr=clamp_err(ys[:, 0] / scale, ys[:, 1] / scale, 0,
                                                                     100 if m == "stall_ratio_pct" else None), color=COLOR[p],
                            marker=MARKER[p], capsize=2.5, elinewidth=1, markeredgecolor=SURFACE, label=NAME[p])
            if r == 0:
                ax.plot(bufs, bufs, color=INK2, linestyle=":", linewidth=1)
                ax.annotate("latency = buffer", (bufs[-1], bufs[-1]), textcoords="offset points",
                            xytext=(-60, 6), fontsize=7.5, color=INK2)
                ax.set_title(f"{prof}")
            ax.set_ylabel(lab)
            ax.set_ylim(bottom=0)
            if r == 1:
                ax.set_xlabel("Client buffer target (s)")
                ax.set_xticks(bufs)
    axes[0][0].legend(loc="upper left")
    fig.suptitle("Effect of the client buffer target (mean of repetitions, 95% CI)", fontweight="bold", y=1.0)
    fig.tight_layout()
    save(fig, out / "fig2_buffer_sweep.png")


def sens_buffer(summ, prof, preferred=1.0):
    """Buffer target at which a sweep profile was run (prefers 1.0 s if several)."""
    b = sorted(summ[summ.profile == prof].buffer.unique())
    if not b:
        return preferred
    return preferred if any(np.isclose(b, preferred)) else b[0]


def fig_sensitivity(summ, out):
    avail = {k: v for k, v in SWEEPS.items() if sum(pr in set(summ.profile) for pr, _ in v) >= 2}
    if not avail:
        return
    fig, axes = plt.subplots(2, len(avail), figsize=(4.6 * len(avail), 6.2), squeeze=False)
    for c, (title, levels) in enumerate(avail.items()):
        levels = [(pr, lab) for pr, lab in levels if pr in set(summ.profile)]
        xs = np.arange(len(levels))
        for r, (m, lab, scale) in enumerate([("lat_mean_ms", "Mean latency (s)", 1000), ("stall_ratio_pct", "Stall ratio (%)", 1)]):
            ax = axes[r][c]
            for i, p in enumerate(PROTOS):
                ys = np.array([get(summ, pr, sens_buffer(summ, pr), p, m) for pr, _ in levels], float)
                ax.errorbar(xs + (i - 1) * 0.08, ys[:, 0] / scale,
                            yerr=clamp_err(ys[:, 0] / scale, ys[:, 1] / scale, 0, 100 if m == "stall_ratio_pct" else None),
                            color=COLOR[p],
                            marker=MARKER[p], capsize=2.5, elinewidth=1, markeredgecolor=SURFACE, label=NAME[p])
            ax.set_xticks(xs)
            ax.set_xticklabels([lab for _, lab in levels])
            ax.set_ylim(bottom=0)
            if r == 0:
                ax.set_title(title)
            else:
                ax.set_xlabel(f"{title} ({SWEEP_UNITS[title]})")
            if c == 0:
                ax.set_ylabel(lab)
    axes[0][0].legend(loc="upper left")
    bufs = sorted({sens_buffer(summ, pr) for lv in avail.values() for pr, _ in lv if pr in set(summ.profile)})
    fig.suptitle(f"Sensitivity to bandwidth, RTT and loss (buffer target {', '.join(f'{b:g}' for b in bufs)} s; "
                 "mean of repetitions, 95% CI)",
                 fontweight="bold", y=1.0)
    fig.tight_layout()
    save(fig, out / "fig3_network_sensitivity.png")


def cond_order(meta, df):
    seen = []
    for prof, buf in meta.get("conditions", []):
        c = f"{prof} @ {buf:g}s"
        if c in set(df.cond) and c not in seen:
            seen.append(c)
    for c in df.cond.unique():
        if c not in seen:
            seen.append(c)
    return seen


def fig_all_runs(df, meta, out):
    """Every run as one dot: shows run-to-run variability behind every mean."""
    conds = cond_order(meta, df)
    h = max(3.2, 0.34 * len(conds) + 1.2)
    fig, axes = plt.subplots(1, 2, figsize=(12.5, h), sharey=True)
    ypos = {c: i for i, c in enumerate(conds)}
    for ax, (m, lab, scale, log) in zip(axes, [("lat_mean_ms", "Mean latency per run (s, log scale)", 1000, True),
                                               ("stall_ratio_pct", "Stall ratio per run (%)", 1, False)]):
        for i, p in enumerate(PROTOS):
            g = df[df.protocol == p]
            y = g.cond.map(ypos) + (i - 1) * 0.22
            vals = g[m] / scale
            ax.scatter(vals, y, color=COLOR[p], marker=MARKER[p], s=26, alpha=0.85, edgecolors=SURFACE,
                       linewidths=0.6, label=NAME[p], zorder=3)
        if log:
            set_log_seconds(ax)
        ax.set_xlabel(lab)
        ax.grid(axis="y", visible=False)
    axes[0].set_yticks(range(len(conds)))
    axes[0].set_yticklabels(conds, fontsize=8)
    axes[0].invert_yaxis()
    h_, l_ = axes[1].get_legend_handles_labels()   # below the panels, where it cannot cover any run
    fig.legend(h_, l_, loc="lower center", ncol=3, bbox_to_anchor=(0.5, 0.0))
    fail = df[~df.ok.astype(bool)]
    note = f"{len(df)} protocol-runs in {df.run_id.nunique()} runs" + (f"; {len(fail)} failed to play (plotted at 100% stall)" if len(fail) else "")
    fig.suptitle(f"All runs, all conditions ({note})", fontweight="bold", y=1.0)
    fig.tight_layout(rect=(0, 0.045, 1, 1))
    save(fig, out / "fig4_all_runs.png")


def fig_cdf(runs, out):
    targets = [c for c in [("baseline", 0.5), ("cellular_4g", 0.5)]
               if any(r["profile"] == c[0] and r["buffer"] == c[1] and r.get("browser") for r in runs)]
    if not targets:
        return
    fig, axes = plt.subplots(1, len(targets), figsize=(5.6 * len(targets), 3.9), squeeze=False)
    for ax, (prof, buf) in zip(axes[0], targets):
        for p in PROTOS:
            lats = []
            for r in runs:
                if r["profile"] != prof or r["buffer"] != buf or not r.get("browser"):
                    continue
                m = r["browser"]["meta"]
                rep = r["browser"]["protocols"].get(p)
                if not rep or rep.get("firstFrameRelMs") is None:
                    continue
                lo = max(1000 * m["warmupSec"], rep["firstFrameRelMs"])
                lats += [f[1] for f in rep["frames"] if lo <= f[0] <= m["endRelMs"] and f[1] is not None and f[1] >= 0]
            if lats:
                x = np.sort(np.array(lats)) / 1000
                ax.plot(x, np.arange(1, len(x) + 1) / len(x), color=COLOR[p], label=f"{NAME[p]} (n={len(x)})")
        ax.set_title(f"{prof} @ {buf:g}s: per-frame latency CDF (all reps)")
        ax.set_xlabel("End-to-end latency (s)")
        ax.set_ylabel("Fraction of sampled frames")
        ax.set_ylim(0, 1.01)
        ax.legend(loc="lower right")
    fig.tight_layout()
    save(fig, out / "fig5_latency_cdf.png")


def fig_startup_overhead(summ, df, out):
    fig, axes = plt.subplots(1, 2, figsize=(11.5, 3.9))
    ax = axes[0]
    data = [df[(df.protocol == p) & df.ttff_ms.notna()].ttff_ms / 1000 for p in PROTOS]
    bp = ax.boxplot(data, widths=0.5, patch_artist=True, showfliers=True,
                    medianprops={"color": INK, "linewidth": 1.5}, flierprops={"markersize": 3})
    for patch, p in zip(bp["boxes"], PROTOS):
        patch.set_facecolor(COLOR[p])
        patch.set_alpha(0.75)
        patch.set_edgecolor(SURFACE)
    ax.set_xticks(range(1, 4))
    ax.set_xticklabels([NAME[p] for p in PROTOS])
    ax.set_ylabel("Start-up delay, cold browser (s)")
    ax.set_title("Time to first frame (all runs)")
    ax.set_ylim(bottom=0)

    ax = axes[1]
    # Overhead is compared where the link does not limit the rate: the clean link (all buffer targets)
    g = df[(df.profile == "baseline") & df.wire_kbps.notna()] if "wire_kbps" in df else df.iloc[0:0]
    vals = [g[g.protocol == p].wire_kbps for p in PROTOS]
    bp = ax.boxplot(vals, widths=0.5, patch_artist=True, showfliers=True,
                    medianprops={"color": INK, "linewidth": 1.5}, flierprops={"markersize": 3})
    for patch, p in zip(bp["boxes"], PROTOS):
        patch.set_facecolor(COLOR[p])
        patch.set_alpha(0.75)
        patch.set_edgecolor(SURFACE)
    ax.axhline(SOURCE_KBPS, color=INK2, linestyle=":", linewidth=1)
    ax.annotate("encoder target 1896 kbps", (0.55, SOURCE_KBPS), textcoords="offset points", xytext=(0, 4),
                fontsize=7.5, color=INK2)
    ax.set_xticks(range(1, 4))
    ax.set_xticklabels([NAME[p] for p in PROTOS])
    ax.set_ylabel("Server egress per protocol (kbps)")
    ax.set_title("On-the-wire rate, clean link (tc counters)")
    ax.set_ylim(bottom=0)
    fig.tight_layout()
    save(fig, out / "fig6_startup_and_wire_rate.png")


def fig_trace(runs, out):
    pick = next((r for r in runs if r["profile"] == "cellular_4g" and r["buffer"] == 0.5 and r.get("browser")), None)
    pick = pick or next((r for r in runs if r.get("browser")), None)
    if not pick:
        return
    m = pick["browser"]["meta"]
    fig, axes = plt.subplots(3, 1, figsize=(11.5, 6.4), sharex=True)
    for ax, p in zip(axes, PROTOS):
        rep = pick["browser"]["protocols"].get(p)
        if not rep:
            continue
        pts = [(f[0] / 1000, f[1] / 1000) for f in rep["frames"] if f[1] is not None and f[1] >= 0]
        if pts:
            t, l = zip(*pts)
            ax.plot(t, l, color=COLOR[p], linewidth=1.4)
        for s in rep["stalls"]:
            ax.axvspan(s[0] / 1000, (s[0] + s[1]) / 1000, color="#e34948", alpha=0.18, linewidth=0)
        ax.axvline(m["warmupSec"], color=INK2, linestyle=":", linewidth=1)
        ax.set_ylabel(f"{NAME[p]}\nlatency (s)")
        ax.set_ylim(bottom=0)
    axes[0].annotate("warm-up ends", (m["warmupSec"], axes[0].get_ylim()[1] * 0.9), textcoords="offset points",
                     xytext=(4, 0), fontsize=7.5, color=INK2)
    axes[-1].set_xlabel("Time since players started (s)")
    fig.suptitle(f"Example run {pick['run_id']} - latency per sampled frame; shaded = stalls (> 200 ms frame gap)",
                 fontweight="bold", y=1.0)
    fig.tight_layout()
    save(fig, out / "fig7_example_trace.png")


def fig_setup(meta, out):
    """Physical setup diagram drawn from the campaign's recorded metadata."""
    from matplotlib.patches import FancyArrowPatch, FancyBboxPatch
    topo, link = meta.get("topology", {}), meta.get("physical_link") or {}
    s, c = topo.get("server", {}), topo.get("client", {})
    ping, dl, wifi = link.get("ping", {}), link.get("downlink_tcp", {}), link.get("wifi") or {}
    os_name = c.get("os", "")
    if os_name.startswith("Windows-10-10.0."):
        build = int(os_name.split(".")[2].split("-")[0])
        os_name = f"Windows {'11' if build >= 22000 else '10'} (build {build})"
    fig, ax = plt.subplots(figsize=(12.5, 5.8))
    ax.set_xlim(0, 100)
    ax.set_ylim(0, 52)
    ax.axis("off")

    def box(x, y, w, h, title, lines, fc="#ffffff", ec="#9a9994", title_size=9):
        ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.3,rounding_size=1.0", fc=fc, ec=ec, lw=1.3))
        ax.text(x + 1, y + h - 1.4, title, fontsize=title_size, fontweight="bold", color=INK, va="top")
        for i, ln in enumerate(lines):
            ax.text(x + 1, y + h - 4.6 - i * 2.5, ln, fontsize=8.2, color=INK2, va="top")

    def arrow(p0, p1, color, style="-|>", ls="-"):
        ax.add_patch(FancyArrowPatch(p0, p1, arrowstyle=style, mutation_scale=13, color=color, lw=1.8, linestyle=ls))

    # outer machines
    box(1, 1, 30, 50, "Laptop (viewer)", [os_name, f"Chrome {c.get('browser_version', '')}"],
        fc="#f7f7f5", title_size=10.5)
    box(56, 1, 43, 50, f"Lab PC (server)  {s.get('ip', '')}",
        [f"{s.get('cpu', '')}, Linux {s.get('kernel', '')}", "wired 1 GbE, Docker, no Internet access"],
        fc="#f7f7f5", title_size=10.5)
    # viewer internals
    box(3, 24, 26, 15, "Browser (headless or dashboard)",
        ["WebRTC: RTCPeerConnection", "LL-HLS: hls.js 1.5", "HTTP-FLV: mpegts.js 1.7", "barcode -> latency; frame gaps"])
    box(3, 4, 26, 13, "run_campaign.py", ["randomized repetitions", "clock-offset probes", "raw JSON per run"])
    # server internals
    box(58, 27, 18, 12.5, "Source", ["720p30 H.264 + AAC", "timestamp barcode", "RTMP via loopback"])
    box(79, 27, 18.5, 12.5, f"SRS {s.get('srs_version', '')}", ["WebRTC  UDP :8000", "HTTP-FLV  TCP :18080",
                                                                 "forwards to MediaMTX"])
    box(79, 13, 18.5, 10, "MediaMTX 1.21.3", ["LL-HLS  TCP :8888", "1 s segm. / 200 ms parts"])
    box(58, 8, 18, 16, "tc/netem on egress", ["prio + 1 netem per", "protocol, same profile", "on each; ingest and",
                                              "control unshaped"], fc="#fff4ee", ec="#eb6834")
    box(79, 2.5, 18.5, 7, "agent.py :9000", ["clock, profiles, dashboard"])
    arrow((76, 33.2), (79, 33.2), "#9a9994")
    arrow((88, 27), (88, 23), "#9a9994")

    # real path between machines
    ax.text(43.5, 49, "Real network path", fontsize=10, fontweight="bold", ha="center", color=INK)
    path_lines = []
    if ping:
        path_lines.append(f"RTT min/med/p95 {ping.get('min_ms'):g}/{ping.get('median_ms'):g}/{ping.get('p95_ms'):g} ms")
    if dl:
        path_lines.append(f"downlink ~{dl.get('mbps_median')} Mbps (1 TCP)")
    if wifi.get("Radio type"):
        path_lines.append(f"viewer: {wifi.get('Radio type')} {wifi.get('Band', '')}")
        path_lines.append(f"Wi-Fi signal {wifi.get('Signal')}")
    for i, ln in enumerate(path_lines):
        ax.text(43.5, 46.2 - i * 2.4, ln, fontsize=8, ha="center", color=INK2)
    arrow((58, 16), (29.6, 30), "#2a78d6")
    ax.text(43.5, 30.2, "media, 3 protocols\neach via its own netem queue", fontsize=8, ha="center", va="bottom",
            color="#2a78d6")
    arrow((29.6, 6), (79, 6), "#52514e", style="<|-|>", ls="--")
    ax.text(43.5, 7.0, "clock probes, profile switch", fontsize=8, ha="center", color="#52514e")
    save(fig, out / "fig0_physical_setup.png")


# ----------------------------------------------------------------------------- report
def fmt_ci(mean, h, scale=1, d=0):
    if mean is None or (isinstance(mean, float) and math.isnan(mean)):
        return "n/a"
    s = f"{mean / scale:.{d}f}"
    if h is not None and not (isinstance(h, float) and math.isnan(h)):
        s += f" ± {h / scale:.{d}f}"
    return s


def write_summary(cdir, meta, df, summ, pw, out):
    L = [f"# Campaign `{meta['campaign']}` - results summary", ""]
    L += [f"- Created: {meta['created']}  |  plan: `{meta['plan_name']}`  |  repetitions: {meta['reps']}  |  "
          f"{meta['duration_s']} s per run, first {meta['warmup_s']} s excluded (warm-up)",
          f"- Runs completed: {df.run_id.nunique()} of {len(meta['plan'])} planned; protocol-runs analysed: {len(df)}",
          "- All three protocols play simultaneously in each run, each through its own identically configured "
          "tc/netem pipe on the server's egress -> paired comparisons.", ""]
    topo = meta.get("topology", {})
    link = meta.get("physical_link") or {}
    L += ["## Physical setup", "", "| Role | Machine | Details |", "|---|---|---|"]
    s, c = topo.get("server", {}), topo.get("client", {})
    L.append(f"| Media server + source + emulator | `{s.get('host')}` ({s.get('ip')}) | {s.get('cpu')}, Linux {s.get('kernel')}, "
             f"SRS {s.get('srs_version')}, MediaMTX {((s.get('containers') or {}).get('streaming-llhls') or {}).get('image')} |")
    L.append(f"| Viewer + campaign runner | `{c.get('host')}` | {c.get('os')}, browser {c.get('browser_version')} |")
    if link:
        p, d, w = link.get("ping", {}), link.get("downlink_tcp", {}), link.get("wifi") or {}
        L += ["", f"Path between them (before any emulation): ICMP RTT min/median/p95 = {p.get('min_ms')}/{p.get('median_ms')}/"
              f"{p.get('p95_ms')} ms, jitter {p.get('jitter_ms')} ms, loss {p.get('loss_pct')}%; single-TCP downlink "
              f"~{d.get('mbps_median')} Mbps; clock offset viewer-server {link['http_clock_probe']['offset_ms']:+.1f} ms "
              f"(± {link['http_clock_probe']['unc_ms']:.1f} ms)."]
        if w:
            L.append(f"Viewer link: {w.get('Radio type')} {w.get('Band', '')} channel {w.get('Channel')}, signal {w.get('Signal')}, "
                     f"rx/tx {w.get('Receive rate (Mbps)')}/{w.get('Transmit rate (Mbps)')} Mbps.")
    L.append("")

    L += ["## Results per condition (mean ± 95% CI over repetitions)", "",
          "| Condition | Protocol | OK runs | Mean latency (ms) | p95 latency (ms) | Stall ratio (%) | Stalls/run | Start-up (ms) | FPS | Wire (kbps) |",
          "|---|---|---|---|---|---|---|---|---|---|"]
    for _, r in summ.iterrows():
        L.append(f"| {r.profile} @ {r.buffer:g}s | {NAME[r.protocol]} | {r.ok_runs}/{r.runs} | "
                 f"{fmt_ci(r.get('lat_mean_ms_mean'), r.get('lat_mean_ms_ci95'))} | {fmt_ci(r.get('lat_p95_ms_mean'), r.get('lat_p95_ms_ci95'))} | "
                 f"{fmt_ci(r.get('stall_ratio_pct_mean'), r.get('stall_ratio_pct_ci95'), d=1)} | "
                 f"{fmt_ci(r.get('stall_count_mean'), r.get('stall_count_ci95'), d=1)} | "
                 f"{fmt_ci(r.get('ttff_ms_mean'), r.get('ttff_ms_ci95'))} | {fmt_ci(r.get('fps_mean'), None, d=1)} | "
                 f"{fmt_ci(r.get('wire_kbps_mean'), None)} |")
    L.append("")

    if not pw.empty:
        L += ["## Which protocol wins, per condition", "",
              "Winner = lowest mean. 'clear' = paired t-test p < 0.05 against the runner-up (needs >= 3 repetitions); "
              "otherwise the difference is within run-to-run noise.", "",
              "| Condition | Lowest latency | Fewest stalls |", "|---|---|---|"]
        wins = {m: {p: [0, 0] for p in PROTOS} for m in ("lat_mean_ms", "stall_ratio_pct")}
        ties = 0
        for (prof, buf), g in summ.groupby(["profile", "buffer"], sort=False):
            cells = []
            for m in ("lat_mean_ms", "stall_ratio_pct"):
                gg = g.dropna(subset=[f"{m}_mean"]).sort_values(f"{m}_mean")
                if gg.empty:
                    cells.append("n/a")
                    continue
                best, second = gg.iloc[0], gg.iloc[1] if len(gg) > 1 else None
                verdict = ""
                if second is not None:
                    q = pw[(pw.profile == prof) & (pw.buffer == buf) & (pw.metric == m) &
                           (((pw.a == best.protocol) & (pw.b == second.protocol)) | ((pw.b == best.protocol) & (pw.a == second.protocol)))]
                    if m == "stall_ratio_pct" and abs(best[f"{m}_mean"] - second[f"{m}_mean"]) < 0.05:
                        verdict = " (tie)"
                    elif not q.empty and q.iloc[0].n_pairs >= 3 and not np.isnan(q.iloc[0].p_paired_t):
                        verdict = " (clear)" if q.iloc[0].p_paired_t < 0.05 else " (not significant)"
                cells.append(f"{NAME[best.protocol]}{verdict}")
                if verdict == " (tie)":
                    ties += 1
                else:
                    wins[m][best.protocol][0] += 1
                    wins[m][best.protocol][1] += verdict == " (clear)"
            L.append(f"| {prof} @ {buf:g}s | {cells[0]} | {cells[1]} |")
        n_cond = summ.groupby(["profile", "buffer"]).ngroups
        L += ["", f"**Scoreboard over {n_cond} conditions** (wins / of which statistically clear):", "",
              "| Protocol | Lowest latency | Fewest stalls |", "|---|---|---|"]
        for p in PROTOS:
            L.append(f"| {NAME[p]} | {wins['lat_mean_ms'][p][0]} / {wins['lat_mean_ms'][p][1]} | "
                     f"{wins['stall_ratio_pct'][p][0]} / {wins['stall_ratio_pct'][p][1]} |")
        if ties:
            L += ["", f"{ties} condition(s) had a tie for fewest stalls (all within 0.05 percentage points)."]
        L.append("")

    L += ["## Data quality", ""]
    ok = df[df.ok.astype(bool)]
    if not ok.empty:
        L.append(f"- Barcode decode success on sampled frames: median {100 * ok.decode_rate.median():.1f}%, "
                 f"min {100 * ok.decode_rate.min():.1f}%.")
    if "clock_unc_ms" in df:
        cu = df.drop_duplicates("run_id")
        L.append(f"- Clock-offset uncertainty per run (± RTT/2): median {cu.clock_unc_ms.median():.1f} ms, max {cu.clock_unc_ms.max():.1f} ms; "
                 f"offset drift start->end of run: median |{cu.clock_drift_ms.abs().median():.1f}| ms, max |{cu.clock_drift_ms.abs().max():.1f}| ms.")
    fail = df[~df.ok.astype(bool)]
    L.append(f"- Protocol-runs that never rendered a frame: {len(fail)}" +
             (": " + ", ".join(f"{r.run_id}/{r.protocol}" for _, r in fail.iterrows()) if len(fail) else "."))
    L += ["", "## Metric definitions", "",
          "- **Latency**: display time of a frame (viewer clock converted to the server clock via the measured offset) minus "
          "the capture time encoded in that frame's 32-bit barcode. Sampled ~10x per second per player.",
          "- **Stall**: any gap > 200 ms between consecutively presented frames (requestVideoFrameCallback), identical for all "
          "players. Stall ratio = stalled time / measurement window.",
          "- **Start-up**: from creating the player to the first presented frame, in a fresh browser profile.",
          "- **Wire rate**: bytes leaving the server's per-protocol tc queue during the measurement window (includes headers, "
          "retransmissions, playlist/segment requests).", ""]
    (out / "summary.md").write_text("\n".join(L), encoding="utf-8")
    print(f"[report] {out / 'summary.md'}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("campaign")
    a = ap.parse_args()
    cdir, meta, runs, df = load_campaign(a.campaign)
    out = cdir / "analysis"
    out.mkdir(exist_ok=True)
    df.to_csv(out / "runs_all.csv", index=False)
    summ = summarize(df)
    summ.to_csv(out / "summary_by_condition.csv", index=False)
    pw = pairwise(df)
    pw.to_csv(out / "pairwise.csv", index=False)
    fig_setup(meta, out)
    fig_tradeoff(summ, out)
    fig_buffer_sweep(summ, out)
    fig_sensitivity(summ, out)
    fig_all_runs(df, meta, out)
    fig_cdf(runs, out)
    fig_startup_overhead(summ, df, out)
    fig_trace(runs, out)
    write_summary(cdir, meta, df, summ, pw, out)


if __name__ == "__main__":
    main()
