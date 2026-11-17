# Campaign `val_hls_default` - results summary

- Created: 2026-11-13T01:56:03  |  plan: `pilot`  |  repetitions: 2  |  45 s per run, first 10 s excluded (warm-up)
- Runs completed: 6 of 6 planned; protocol-runs analysed: 18
- All three protocols play simultaneously in each run, each through its own identically configured tc/netem pipe on the server's egress -> paired comparisons.

## Physical setup

| Role | Machine | Details |
|---|---|---|
| Media server + source + emulator | `vijay425` (10.21.232.54) | Intel(R) Core(TM) i7-14700, Linux 7.0.0-38-generic, SRS 5.0.225, MediaMTX bluenviron/mediamtx:1.21.3 |
| Viewer + campaign runner | `balaji_k` | Windows-10-10.0.26200-SP0, browser 157.0.8103.51 |

## Results per condition (mean ± 95% CI over repetitions)

| Condition | Protocol | OK runs | Mean latency (ms) | p95 latency (ms) | Stall ratio (%) | Stalls/run | Start-up (ms) | FPS | Wire (kbps) |
|---|---|---|---|---|---|---|---|---|---|
| baseline @ 0.5s | WebRTC | 2/2 | 605 ± 8 | 628 ± 44 | 0.0 ± 0.0 | 0.0 ± 0.0 | 1175 ± 966 | 29.9 | 1646 |
| baseline @ 0.5s | LL-HLS | 2/2 | 2854 ± 6013 | 4824 ± 1908 | 48.9 ± 190.2 | 7.0 ± 50.8 | 1142 ± 654 | 13.8 | 1774 |
| baseline @ 0.5s | HTTP-FLV | 2/2 | 703 ± 68 | 713 ± 51 | 0.0 ± 0.0 | 0.0 ± 0.0 | 1428 ± 19 | 29.6 | 1545 |
| cellular_4g @ 0.5s | WebRTC | 2/2 | 724 ± 104 | 753 ± 47 | 1.8 ± 3.3 | 1.5 ± 6.4 | 2150 ± 775 | 28.2 | 1677 |
| cellular_4g @ 0.5s | LL-HLS | 2/2 | 5822 ± 8704 | 6908 ± 7605 | 41.9 ± 73.2 | 16.5 ± 19.1 | 2862 ± 692 | 17.1 | 1510 |
| cellular_4g @ 0.5s | HTTP-FLV | 2/2 | 2686 ± 6925 | 3657 ± 5476 | 9.5 ± 2.6 | 5.5 ± 6.4 | 1680 ± 978 | 26.8 | 1493 |
| rtt_160ms @ 0.5s | WebRTC | 2/2 | 769 ± 97 | 788 ± 76 | 0.8 ± 1.8 | 1.0 ± 0.0 | 3129 ± 0 | 28.7 | 1689 |
| rtt_160ms @ 0.5s | LL-HLS | 2/2 | 4460 ± 459 | 4885 ± 3647 | 48.6 ± 414.9 | 8.0 ± 38.1 | 4425 ± 12630 | 15.2 | 1507 |
| rtt_160ms @ 0.5s | HTTP-FLV | 2/2 | 838 ± 300 | 853 ± 305 | 0.0 ± 0.0 | 0.0 ± 0.0 | 2397 ± 2795 | 29.5 | 1527 |

## Which protocol wins, per condition

Winner = lowest mean. 'clear' = paired t-test p < 0.05 against the runner-up (needs >= 3 repetitions); otherwise the difference is within run-to-run noise.

| Condition | Lowest latency | Fewest stalls |
|---|---|---|
| baseline @ 0.5s | WebRTC (clear) | WebRTC (tie) |
| cellular_4g @ 0.5s | WebRTC (not significant) | WebRTC (clear) |
| rtt_160ms @ 0.5s | WebRTC (not significant) | HTTP-FLV (not significant) |

**Scoreboard over 3 conditions** (wins / of which statistically clear):

| Protocol | Lowest latency | Fewest stalls |
|---|---|---|
| WebRTC | 3 / 1 | 1 / 1 |
| LL-HLS | 0 / 0 | 0 / 0 |
| HTTP-FLV | 0 / 0 | 1 / 0 |

1 condition(s) had a tie for fewest stalls (all within 0.05 percentage points).

## Data quality

- Barcode decode success on sampled frames: median 100.0%, min 100.0%.
- Clock-offset uncertainty per run (± RTT/2): median 1.7 ms, max 1.9 ms; offset drift start->end of run: median |0.3| ms, max |0.5| ms.
- Protocol-runs that never rendered a frame: 0.

## Metric definitions

- **Latency**: display time of a frame (viewer clock converted to the server clock via the measured offset) minus the capture time encoded in that frame's 32-bit barcode. Sampled ~10x per second per player.
- **Stall**: any gap > 200 ms between consecutively presented frames (requestVideoFrameCallback), identical for all players. Stall ratio = stalled time / measurement window.
- **Start-up**: from creating the player to the first presented frame, in a fresh browser profile.
- **Wire rate**: bytes leaving the server's per-protocol tc queue during the measurement window (includes headers, retransmissions, playlist/segment requests).
