# Campaign `pilot1` - results summary

- Created: 2026-11-13T01:49:38  |  plan: `pilot`  |  repetitions: 2  |  45 s per run, first 10 s excluded (warm-up)
- Runs completed: 6 of 6 planned; protocol-runs analysed: 18
- All three protocols play simultaneously in each run, each through its own identically configured tc/netem pipe on the server's egress -> paired comparisons.

## Physical setup

| Role | Machine | Details |
|---|---|---|
| Media server + source + emulator | `vijay425` (10.21.232.54) | Intel(R) Core(TM) i7-14700, Linux 7.0.0-38-generic, SRS 5.0.225, MediaMTX bluenviron/mediamtx:1.21.3 |
| Viewer + campaign runner | `balaji_k` | Windows-10-10.0.26200-SP0, browser 157.0.8103.51 |

Path between them (before any emulation): ICMP RTT min/median/p95 = 3.0/5.0/55.0 ms, jitter 7.21 ms, loss 0.0%; single-TCP downlink ~53.8 Mbps; clock offset viewer-server +71378.4 ms (± 1.7 ms).
Viewer link: 802.11n 2.4 GHz channel 5, signal 91%, rx/tx 300/300 Mbps.

## Results per condition (mean ± 95% CI over repetitions)

| Condition | Protocol | OK runs | Mean latency (ms) | p95 latency (ms) | Stall ratio (%) | Stalls/run | Start-up (ms) | FPS | Wire (kbps) |
|---|---|---|---|---|---|---|---|---|---|
| baseline @ 0.5s | WebRTC | 2/2 | 584 ± 4 | 612 ± 51 | 0.0 ± 0.0 | 0.0 ± 0.0 | 2844 ± 20851 | 29.2 | 1648 |
| baseline @ 0.5s | LL-HLS | 2/2 | 1355 ± 461 | 1661 ± 161 | 33.4 ± 265.2 | 9.5 ± 82.6 | 3159 ± 25641 | 19.4 | 2001 |
| baseline @ 0.5s | HTTP-FLV | 2/2 | 840 ± 476 | 855 ± 534 | 0.0 ± 0.0 | 0.0 ± 0.0 | 3056 ± 19116 | 29.2 | 1541 |
| cellular_4g @ 0.5s | WebRTC | 2/2 | 693 ± 382 | 735 ± 354 | 1.5 ± 0.6 | 1.0 ± 0.0 | 2506 ± 762 | 26.9 | 1755 |
| cellular_4g @ 0.5s | LL-HLS | 2/2 | 2167 ± 1886 | 2399 ± 1043 | 93.3 ± 57.2 | 30.5 ± 108.0 | 2476 ± 1226 | 1.9 | 1361 |
| cellular_4g @ 0.5s | HTTP-FLV | 2/2 | 866 ± 771 | 1047 ± 1449 | 0.5 ± 6.4 | 0.5 ± 6.4 | 1777 ± 1830 | 28.9 | 1524 |
| rtt_160ms @ 0.5s | WebRTC | 2/2 | 759 ± 53 | 772 ± 108 | 0.0 ± 0.0 | 0.0 ± 0.0 | 2892 ± 553 | 29.7 | 1744 |
| rtt_160ms @ 0.5s | LL-HLS | 2/2 | 2123 ± 3618 | 2421 ± 542 | 97.5 ± 32.4 | 13.5 ± 95.3 | 7453 ± 11372 | 0.8 | 1198 |
| rtt_160ms @ 0.5s | HTTP-FLV | 2/2 | 925 ± 1040 | 1590 ± 9422 | 0.0 ± 0.0 | 0.0 ± 0.0 | 2085 ± 2668 | 29.9 | 1561 |

## Which protocol wins, per condition

Winner = lowest mean. 'clear' = paired t-test p < 0.05 against the runner-up (needs >= 3 repetitions); otherwise the difference is within run-to-run noise.

| Condition | Lowest latency | Fewest stalls |
|---|---|---|
| baseline @ 0.5s | WebRTC | WebRTC (tie) |
| cellular_4g @ 0.5s | WebRTC | HTTP-FLV |
| rtt_160ms @ 0.5s | WebRTC | WebRTC (tie) |

**Scoreboard over 3 conditions** (wins / of which statistically clear):

| Protocol | Lowest latency | Fewest stalls |
|---|---|---|
| WebRTC | 3 / 0 | 0 / 0 |
| LL-HLS | 0 / 0 | 0 / 0 |
| HTTP-FLV | 0 / 0 | 1 / 0 |

2 condition(s) had a tie for fewest stalls (all within 0.05 percentage points).

## Data quality

- Barcode decode success on sampled frames: median 100.0%, min 100.0%.
- Clock-offset uncertainty per run (± RTT/2): median 1.5 ms, max 2.4 ms; offset drift start->end of run: median |0.4| ms, max |0.9| ms.
- Protocol-runs that never rendered a frame: 0.

## Metric definitions

- **Latency**: display time of a frame (viewer clock converted to the server clock via the measured offset) minus the capture time encoded in that frame's 32-bit barcode. Sampled ~10x per second per player.
- **Stall**: any gap > 200 ms between consecutively presented frames (requestVideoFrameCallback), identical for all players. Stall ratio = stalled time / measurement window.
- **Start-up**: from creating the player to the first presented frame, in a fresh browser profile.
- **Wire rate**: bytes leaving the server's per-protocol tc queue during the measurement window (includes headers, retransmissions, playlist/segment requests).
