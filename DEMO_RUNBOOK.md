# Final-demo runbook (two machines)

| Machine | Role | Address |
|---|---|---|
| Lab PC `vijay425` (Ubuntu 24.04, i7-14700) | Media server (SRS + MediaMTX in Docker), timestamped 720p30 source, tc/netem emulator, control agent | `10.21.232.54`, user `networks` |
| Laptop (Windows 11) | Viewer: browser playing all three protocols; campaign runner and analysis | any network that can reach the lab PC |

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

## 0. The day before

1. From the laptop (Git Bash), push the latest code: `bash server/deploy.sh`
2. Start the server: `ssh networks@10.21.232.54 'bash ~/cs6048_testbed/server/up.sh'`
   It prints `"publisher": {"active": true ...}` when the stream is live.
3. Open `http://10.21.232.54:9000/` on the laptop and check that all three players show **LIVE**.

The lab PC has no Internet access. Everything it needs (Docker images, numpy, player JS) is already installed,
so nothing is downloaded during the demo.

## 1. Live demo (about 5 minutes)

Open **`http://10.21.232.54:9000/`** in Chrome on the laptop (full screen, F11).

1. **Show the setup.** Point at the header pills: server IP, measured clock offset (the laptop clock is
   ~71 s off the lab PC; this is measured and corrected in every run), and the active network profile.
2. **Baseline.** Profile `baseline`, buffer target `0.5 s`, then *Start / restart players*. Read out the three
   latency numbers and point at the live chart.
3. **Mobile network.** Pick `cellular_4g`, click **Apply** (no restart needed). Within a few seconds the
   chart shows latency rising and stall marks (red ticks) appearing, differently for each protocol.
4. **High RTT.** Apply `rtt_160ms`: LL-HLS needs a playlist reload plus a part request per 200 ms part, so
   it falls behind, while WebRTC/FLV keep playing.
5. **Tight bandwidth.** Apply `bw_1.6m`. The stream is ~1.5 Mbps, but WebRTC needs ~1.7 Mbps on the wire
   (RTP/SRTP + RTCP + retransmissions) and SRS cannot lower its bitrate, so WebRTC freezes while HTTP-FLV
   (~1.52 Mbps on the wire) keeps playing. Point at the "Wire rate / drops" boxes.
6. **Buffer trade-off.** Apply `cellular_4g` again first (on `bw_1.6m` WebRTC stalls for lack of bandwidth, which a
   bigger buffer cannot fix). Then change the buffer target 0.2 s → 2.0 s: latency goes up, stalls go down
   (campaign: WebRTC 4.8% → 1.5% stalls, HTTP-FLV 14.4% → 2.6%).
7. Click **Apply `baseline`** at the end so the server is left clean.

If a player shows ERROR, click *Start / restart players*. If the dashboard can't reach the agent, restart the
server (step 0.2).

## 2. "All runs" data and comparison

- **Show this in the demo:** `deliverables/new_final_two_machine/Results_Explorer_All_Runs.html` (double-click it;
  it works offline). Pick a condition to see mean ± 95% CI for all three protocols, sort the all-runs table,
  and click any run to show its latency trace with stalls.
- Setup figure for the "physical setup" question: `analysis/fig0_physical_setup.png` (drawn from the measured
  link data of that campaign).
- Raw data: `results/campaigns/<campaign>/runs/*.json` (one file per run: per-frame latency samples, stall
  events, buffer levels, WebRTC stats, player error events, tc counters, clock calibration).
- Flat table of every protocol × run: `results/campaigns/<campaign>/analysis/runs_all.csv`
- Aggregated (mean ± 95% CI) and paired tests: `summary_by_condition.csv`, `pairwise.csv`, `summary.md`
- Figures: `analysis/fig1…fig7*.png`

Regenerate everything from the raw files: `python scripts/analyze_campaign.py <campaign>`

## 3. Re-running measurements

```powershell
# full campaign: 20 conditions x 5 repetitions (~1 h 45 min), resumable
python scripts/run_campaign.py --plan full --reps 5 --campaign final_run
# resume after an interruption (same name)
python scripts/run_campaign.py --campaign final_run
python scripts/analyze_campaign.py final_run
```

Keep the laptop plugged in, with sleep disabled, on the same network for the whole campaign.

## 4. Likely questions

- **How is latency measured across two machines with different clocks?** Every frame carries its capture time
  (server clock) as a 32-bit barcode. The browser converts its own display time to the server clock using
  an offset measured with NTP-style probes over an unshaped channel (min-RTT sample, error ≤ RTT/2, typically
  ±1–3 ms). Offset is measured before and after every run; drift within a run is reported.
- **Why play all three at once?** Each run is a paired comparison: same moment, same physical path. Each
  protocol has its own identically-configured netem queue, so they don't compete for the emulated bottleneck.
- **Is a stall defined the same way for all three?** Yes: a gap > 200 ms between presented frames, measured at
  the renderer (`requestVideoFrameCallback`), not from player-specific events.
- **Why repetitions?** Real networks vary; each condition is repeated in a freshly shuffled order (randomized
  blocks), and we report the mean ± 95% confidence interval and paired t-tests between protocols.
