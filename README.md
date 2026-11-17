# WebRTC vs. LL-HLS vs. HTTP-FLV: a two-machine live-streaming testbed (CS6048)

We compare how three live-streaming delivery protocols trade **end-to-end latency** against **playback
smoothness** (stalls) as the client buffer target and the network (bandwidth, RTT, loss, a 4G-like mix) change.
The media server and the viewer run on **two physical machines**. Every condition is repeated several times,
and all three protocols are measured simultaneously from the same source frames.

**Team:** Ayush Shukla, Balaji K, Rajesh · CS6048 Modern Networking Advances, IIT Madras
<!-- repo-url -->**Repository:** https://github.com/Balaji-kurakula/WebRTC_vs_LL-HLS_vs_HTTP-FLV<!-- /repo-url -->

- Final report: [`deliverables/new_final_two_machine/Final_Report_WebRTC_vs_LLHLS_vs_HTTPFLV_TwoMachine.pdf`](deliverables/new_final_two_machine/Final_Report_WebRTC_vs_LLHLS_vs_HTTPFLV_TwoMachine.pdf)
- Final presentation: `deliverables/new_final_two_machine/Final_Presentation_WebRTC_vs_LLHLS_vs_HTTPFLV_TwoMachine.pptx`
- Every run, offline: `deliverables/new_final_two_machine/Results_Explorer_All_Runs.html`
- Demo-day checklist: **[DEMO_RUNBOOK.md](DEMO_RUNBOOK.md)**

This repository (identical to the submission zip) holds the report (PDF), the presentation, the results explorer,
all code needed to run the testbed, the campaigns and the analysis, and the raw data of every run.

## Physical setup

| Machine | Role | Software |
|---|---|---|
| **Lab PC** `10.21.232.54` (Ubuntu 24.04, i7-14700, 1 GbE) | timestamped 720p30 source → **SRS v5** (WebRTC + HTTP-FLV) → **MediaMTX 1.21.3** (Apple LL-HLS); **tc/netem** emulation; control agent | Docker, FFmpeg 6.1, Python 3.12 |
| **Laptop** (Windows 11) | viewer: Chromium plays all three protocols; campaign runner; analysis | Chrome/Edge, Python 3.11 |

```
 Laptop (viewer)                                Lab PC (server)
 ┌──────────────────────────────┐   campus /    ┌──────────────────────────────────────────────┐
 │ Chrome: WebRTC | LL-HLS | FLV │   Wi-Fi path  │ stream_generator.py ─RTMP(loopback)─► SRS v5  │
 │  barcode → latency, stalls    │◄──────────────│   SRS: WebRTC (:8000/udp, :1985) + FLV (:18080)│
 │ run_campaign.py / analysis    │               │   └─forward─► MediaMTX: LL-HLS (:8888)         │
 └──────────────────────────────┘               │ tc prio + 3× netem on egress (one per protocol)│
           ▲  clock probes, profile switch       │ agent.py :9000 (time, tc, dashboard)           │
           └─────────────────────────────────────┴──────────────────────────────────────────────┘
```

**Why this split.** The source sits next to the server (RTMP over loopback), so ingest is never affected by
the emulated or real network. Only the delivery path (server → viewer) is impaired, which is the path the
protocols differ on. Linux `tc` on a real NIC is also far more faithful than emulation inside WSL2/Docker Desktop.

**Network emulation.** A 4-band `prio` qdisc on the server container's egress gives each protocol its own,
identically configured `netem` queue (WebRTC: UDP 8000 + 1985, HTTP-FLV: 8080, LL-HLS: 8888). RTMP ingest and
host-local traffic stay unshaped. ACKs return unshaped, so `delay` = added RTT. The same structure is installed
for the baseline (pass-through), so per-protocol on-the-wire byte/drop counters are always available.

## Measurement method

- **Latency (glass-to-glass style):** every frame carries its capture time (server clock, ms) as a 36-cell
  barcode (sync bits + 32-bit timestamp + parity). The browser reads the barcode on the presented frame
  (`requestVideoFrameCallback`, ~10 samples/s per player) and subtracts it from the display time converted to
  the server clock.
- **Clock synchronisation between the two machines:** the laptop's clock was ~71 s off the lab PC's, so
  synchronisation is mandatory. The page measures the offset with NTP/Cristian-style probes to the agent's
  `/api/time` over HTTP keep-alive with `TCP_NODELAY` (min-RTT sample; error ≤ RTT/2, typically ±1–3 ms).
  It does this before and after every run, and the campaign runner measures it independently as a cross-check.
- **Stalls:** any gap > 200 ms between consecutively presented frames, measured identically for all three
  players at the renderer (not from player-specific events). Stall ratio = stalled time / measurement window.
- **Start-up delay:** player creation → first presented frame, in a fresh browser profile (cold start).
- **Frame rate:** from the compositor's `presentedFrames` counter.
- **Wire rate / drops:** bytes and drops in each protocol's tc queue on the server during the measurement window.
- **Buffer level:** `buffered.end − currentTime` (LL-HLS, FLV); jitter-buffer delay of recently emitted frames
  (WebRTC `getStats`).
- **Buffer-target knob per player:** WebRTC `RTCRtpReceiver.jitterBufferTarget`; hls.js `liveSyncDuration` with
  low-latency mode and ≤ 1.25× playback-rate catch-up; mpegts.js latency chasing (`target + 0.45 s` max,
  `0.9 × target` min). For FLV targets > 0.6 s the buffer is established once by seeking back from the live edge.

## Experimental design

- **Conditions (full plan, 20):** buffer target 0.2 / 0.5 / 1.0 / 2.0 / 3.5 s on `baseline` and on `cellular_4g`
  (2.2 Mbps, +70 ms ± 25 ms, 0.8% loss). Then, at a 1.0 s buffer target, one factor at a time around a
  5 Mbps / +20 ms reference: bandwidth 5 / 3 / 2.2 / 1.6 Mbps, added RTT 20 / 80 / 160 / 300 ms, random loss
  0 / 1 / 3 / 5 %. The sweeps use 1.0 s because at 0.5 s LL-HLS already stalls on an unimpaired link (MediaMTX
  advertises `PART-HOLD-BACK=0.5`), which would confound the network effect. See
  `python scripts/network_profiles.py list`.
- **Repetitions:** 5 per condition, randomized complete-block order (each repetition is a full pass in a fresh
  shuffled order), so slow changes in the real network hit all conditions equally.
- **Paired:** all three protocols play at the same time in each run, so comparisons are paired by run.
- **Per run:** 45 s of playback, first 10 s excluded as warm-up; cold browser; profile applied before start.
- **Statistics:** mean ± 95% t-confidence interval across repetitions; paired t-tests between protocols.
- **Recorded with every campaign:** physical-path characterisation (ICMP RTT distribution, downlink TCP
  throughput, Wi-Fi radio info), software versions, image IDs, CPU/OS, and the full run order.

## Key results (campaign `main_20261113`: 20 conditions × 5 repetitions = 300 protocol-runs)

Full tables: `results/campaigns/main_20261113/analysis/summary.md`; every run: `deliverables/new_final_two_machine/Results_Explorer_All_Runs.html`.

- **WebRTC has the lowest latency in 19 of 20 conditions** (10 statistically clear, paired t-test p < 0.05). Its
  jitter buffer holds the configured target almost exactly. On the clean link, latency is 0.28 s at a 0.2 s
  target and 3.58 s at 3.5 s; it is stall-free from a 0.5 s target up (1.6% at 0.2 s, almost all in one run in
  which all three players stalled).
- **Clean link:** HTTP-FLV tracks the target slightly above WebRTC, with at most 1.9% stalls. LL-HLS is stall-free
  only at a 1 s target. Most of its stall time is single 5.1–5.2 s freezes *at a gap in the buffered media*:
  playback stops at a hole in the MSE buffer while 0.7–4.2 s of later media is already buffered, and hls.js reports
  `bufferStalledError`, then skips the hole (`bufferNudgeOnStall`). All 15 freeze runs had 2–8 disjoint buffered
  ranges; all 5 runs at a 1 s target kept one contiguous range and had no freeze (15 of 20 vs 0 of 5 runs, Fisher's
  exact p ≈ 0.005). Short starvation stalls add to this at 0.2 and 0.5 s.
- **4G-like link** (2.2 Mbps, +70 ± 25 ms, 0.8% loss): WebRTC 0.42–3.70 s latency with ≤ 5% stalls; LL-HLS 28–58%
  stalls at 5–6 s latency; HTTP-FLV up to 14% stalls and 0.8–2.6 s above its target in the main campaign, but
  clearly better when played alone (1.45 s and 0% stalls at a 1 s target), so treat those numbers as pessimistic.
- **Bandwidth:** at 1.6 Mbps, HTTP-FLV has 0% stalls, LL-HLS 27% and WebRTC 81%. The encoder undershoots its 1.8 Mbps
  target (~1.5 Mbps stream), and the same stream costs 1.53 (HTTP-FLV), 1.72 (WebRTC) and 2.14 (LL-HLS) Mbps on
  the wire. Whichever protocol no longer fits under the cap stalls; SRS cannot lower WebRTC's bitrate here.
- **RTT +20 → +300 ms:** LL-HLS latency 2.61 → 6.09 s (every 200 ms part costs round trips), HTTP-FLV 1.30 → 1.67 s,
  WebRTC 1.12 → 1.39 s.
- **5% random loss:** WebRTC 1.10 s and 1.8% stalls (NACK repairs single packets); LL-HLS 5.3 s and 32% stalls
  (head-of-line blocking). HTTP-FLV measured 3.01 s and 9.3% in the main campaign, but only 1.67 s and 1.5% when
  played alone (see validation): loss costs it some latency, and co-playback roughly doubled the damage.
- **Data quality:** 100% of sampled frames decoded; clock-offset error bound ±1.6 ms median (max ±8.4 ms); 1 of
  300 protocol-runs froze after its first frames (LL-HLS, +80 ms RTT); it counts as ~100% stalls, and that cell's
  latency mean covers the other 4 runs.

## Validation experiments (before the main campaign)

| Campaign | Question | Result |
|---|---|---|
| `pilot1` vs `val_hls_default` | Does hls.js's forced seek-to-live (`liveMaxLatencyDuration = target + 0.8 s`, used in the single-machine study) bias LL-HLS? | Yes, it is a trade-off. Forced seeking holds latency to ~1.4–2.2 s but stalls 33–97% of the time; without it latency drifts to 2.9–5.8 s and stalls fall to ~42–49%. The main campaign uses the hls.js default (no forced seek), matching the other two players, which never jump into unbuffered data. |
| `val_hls_default` vs `val_llhls_alone` | Does playing three players in one browser distort results? | LL-HLS stalls even when alone (15–38% at baseline/0.5 s), so stalls are not caused by co-location. Start-up is faster alone (0.4 s vs 1.1 s), so start-up delay includes some CPU contention. Viewer CPU stays at 10–33% during runs. |
| `val_buffer_check` | Where does LL-HLS become smooth on an unimpaired link? | Single runs, superseded by the main campaign (5 repetitions): there LL-HLS is stall-free only at a 1 s target; at every other target most runs had one ~5 s freeze at a gap in the buffered media (`bufferStalledError`, then `bufferNudgeOnStall`), plus short starvation stalls at 0.2–0.5 s. |
| `ctrl_alone_*` vs `main_20261113` | Does sharing one browser bias the main campaign? (each protocol alone, clean and 4G links at 1 s, 3 runs) | Clean link: no difference for any protocol (e.g. WebRTC 1.085 vs 1.087 s). 4G: WebRTC and LL-HLS unaffected; **HTTP-FLV did clearly better alone** (1.39–1.50 s and 0% stalls in every alone run vs 1.6–7.9 s and 0.8–17% together). `ctrl_alone_httpflv_extra` confirms this at 5% loss (1.67 s / 1.5% alone vs 3.01 s / 9.3%) and on 4G at 0.5 s (1.03 s / 3.7% vs 2.54 s / 13%). Likely cause: bursty TCP arrivals while three players compete for the browser main thread. HTTP-FLV's impaired-link results are therefore reported as pessimistic. |

Comparison tables and plots: `results/comparisons/validation_llhls/`, `interference_control/`, `interference_control_httpflv/`.

## Repository layout

```text
server/
  up.sh, down.sh           start/stop SRS + MediaMTX containers, generator, agent (run on the lab PC)
  deploy.sh                copy server-side files laptop -> lab PC (Git Bash)
  agent.py                 :9000 clock probes, tc profile switching + counters, live dashboard
  run_generator.sh         keeps the timestamped generator running
config/srs.conf, mediamtx.yml
web/index.html             player + measurement page (live demo and automated runs); vendor/ = hls.js, mpegts.js
scripts/
  stream_generator.py      720p30 source with 32-bit timestamp barcode + pacing-health log
  network_profiles.py      the tc/netem profiles (single source of truth) + CLI via the agent
  run_campaign.py          campaign runner (laptop): repetitions, randomized order, resumable
  metrics.py               QoE metric definitions (used by runner and analysis)
  analyze_campaign.py      aggregates a campaign: CSVs, paired tests, figures (fig0 setup ... fig7 trace), summary.md
  build_explorer.py        offline HTML explorer: every run x protocol, per-condition summary, per-run traces
  compare_campaigns.py     same conditions across campaigns (A/B, interference control, Wi-Fi vs wired)
results/campaigns/<name>/  meta.json, runs/*.json (raw), runs.csv, analysis/
results/comparisons/<name>/
deliverables/
  new_final_two_machine/   final presentation, final report (.pdf) and results explorer of the two-machine campaign
```

## Running it

```bash
# laptop (Git Bash): push code to the lab PC, then start the server side there
bash server/deploy.sh networks@10.21.232.54
ssh networks@10.21.232.54 'bash ~/cs6048_testbed/server/up.sh'
```

- **Live demo:** open `http://10.21.232.54:9000/`, then pick a network profile and buffer target.
- **Campaign:** `python scripts/run_campaign.py --plan full --reps 5 --campaign <name>` (resume with the same name).
- **Analysis:** `python scripts/analyze_campaign.py <name>`, then `python scripts/build_explorer.py <name>`
  (opens offline: `results/campaigns/<name>/analysis/results_explorer.html`)
- **Comparisons:** `python scripts/compare_campaigns.py --out <dir> campA=labelA campB=labelB`
- **Stop the server:** `ssh networks@10.21.232.54 'bash ~/cs6048_testbed/server/down.sh'`

The lab PC has no Internet access. Docker images were pulled on the laptop and copied over
(`docker save | docker load`), and numpy was installed from a wheel.

## Changes from the midterm (single-machine) version

The midterm prototype ran server and viewer on one machine, ran each configuration once for ~9 s, and its page applied
several heuristic adjustments on top of the measurements:
- an added "virtual buffer" term to WebRTC latency for targets > 0.5 s
- a buffer-dependent subtraction from WebRTC freeze time
- WebRTC buffer level floored at 0.9 × target
- "A/V drift" for LL-HLS / HTTP-FLV derived from playback rate / drop ratio

The current page reports only directly measured quantities. A/V drift is no longer reported, because the
source has no audio timestamp to measure it against. Conclusions should be drawn from `results/campaigns/`.
