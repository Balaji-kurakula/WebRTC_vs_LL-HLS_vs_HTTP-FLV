#!/usr/bin/env python3
"""
Compare the same conditions across campaigns, e.g. two player configurations (A/B), one protocol alone vs
all three together (interference control), or two physical setups (Wi-Fi vs wired viewer).

Usage:
  python scripts/compare_campaigns.py --out validation_hls pilot1=hls_maxlat_0.8 val_hls_default=hls_default
Each argument is <campaign>[=<label>]. Writes results/comparisons/<out>/compare.md and compare.png.
"""

import argparse
import sys
from pathlib import Path

import matplotlib
import numpy as np
import pandas as pd

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent))
from analyze_campaign import (COLOR, INK2, MARKER, NAME, PROTOS, SURFACE, clamp_err, fmt_ci,  # noqa: E402
                              load_campaign, save, summarize)

ROOT = Path(__file__).resolve().parent.parent


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("campaigns", nargs="+", help="<campaign>[=<label>]")
    ap.add_argument("--out", required=True)
    a = ap.parse_args()

    frames = []
    for spec in a.campaigns:
        name, _, label = spec.partition("=")
        _, _, _, df = load_campaign(name)
        s = summarize(df)
        s["campaign"] = label or name
        frames.append(s)
    summ = pd.concat(frames, ignore_index=True)
    labels = [f.campaign.iloc[0] for f in frames]
    conds = [c for c in dict.fromkeys(zip(summ.profile, summ.buffer))
             if all(((summ.campaign == l) & (summ.profile == c[0]) & np.isclose(summ.buffer, c[1])).any() for l in labels)]

    out = ROOT / "results" / "comparisons" / a.out
    out.mkdir(parents=True, exist_ok=True)

    rows = [(c, l) for c in conds for l in labels]
    fig, axes = plt.subplots(1, 2, figsize=(12, 0.42 * len(rows) + 1.6), sharey=True)
    for ax, (m, lab, scale) in zip(axes, [("lat_mean_ms", "Mean latency (s)", 1000), ("stall_ratio_pct", "Stall ratio (%)", 1)]):
        for i, p in enumerate(PROTOS):
            for y, (c, l) in enumerate(rows):
                r = summ[(summ.campaign == l) & (summ.profile == c[0]) & np.isclose(summ.buffer, c[1]) & (summ.protocol == p)]
                if r.empty:
                    continue
                v, h = r.iloc[0][f"{m}_mean"], r.iloc[0][f"{m}_ci95"]
                ax.errorbar(v / scale, y + (i - 1) * 0.18,
                            xerr=clamp_err(v / scale, h / scale, 0, 100 if m == "stall_ratio_pct" else None), color=COLOR[p],
                            marker=MARKER[p], markersize=6.5, capsize=2, elinewidth=1, markeredgecolor=SURFACE,
                            label=NAME[p] if y == 0 else None)
        ax.set_xlabel(lab)
        ax.set_xlim(left=0)
        ax.grid(axis="y", visible=False)
    for y in range(len(labels), len(rows), len(labels)):
        for ax in axes:
            ax.axhline(y - 0.5, color=INK2, linewidth=0.6, alpha=0.5)
    axes[0].set_yticks(range(len(rows)))
    axes[0].set_yticklabels([f"{c[0]} @ {c[1]:g}s | {l}" for c, l in rows], fontsize=8)
    axes[0].invert_yaxis()
    axes[1].legend(loc="lower right")
    fig.suptitle(f"Comparison: {' vs '.join(labels)} (mean of repetitions, 95% CI)", fontweight="bold", y=1.0)
    fig.tight_layout()
    save(fig, out / "compare.png")

    L = [f"# Comparison: {' vs '.join(labels)}", "",
         "| Condition | Protocol | " + " | ".join(f"{l}: latency (ms)" for l in labels) + " | "
         + " | ".join(f"{l}: stall (%)" for l in labels) + " |",
         "|---|---|" + "---|" * (2 * len(labels))]
    for c in conds:
        for p in PROTOS:
            lat, st = [], []
            for l in labels:
                r = summ[(summ.campaign == l) & (summ.profile == c[0]) & np.isclose(summ.buffer, c[1]) & (summ.protocol == p)]
                if r.empty:
                    lat.append("-")
                    st.append("-")
                    continue
                r = r.iloc[0]
                lat.append(fmt_ci(r.lat_mean_ms_mean, r.lat_mean_ms_ci95))
                st.append(fmt_ci(r.stall_ratio_pct_mean, r.stall_ratio_pct_ci95, d=1))
            if all(x == "-" for x in lat):
                continue
            L.append(f"| {c[0]} @ {c[1]:g}s | {NAME[p]} | " + " | ".join(lat) + " | " + " | ".join(st) + " |")
    (out / "compare.md").write_text("\n".join(L) + "\n", encoding="utf-8")
    print(f"[compare] {out / 'compare.md'}")


if __name__ == "__main__":
    main()
