# Campaign `main_20261113` - results summary

- Created: 2026-11-13T02:09:48  |  plan: `full`  |  repetitions: 5  |  45 s per run, first 10 s excluded (warm-up)
- Runs completed: 100 of 100 planned; protocol-runs analysed: 300
- All three protocols play simultaneously in each run, each through its own identically configured tc/netem pipe on the server's egress -> paired comparisons.

## Physical setup

| Role | Machine | Details |
|---|---|---|
| Media server + source + emulator | `vijay425` (10.21.232.54) | Intel(R) Core(TM) i7-14700, Linux 7.0.0-38-generic, SRS 5.0.225, MediaMTX bluenviron/mediamtx:1.21.3 |
| Viewer + campaign runner | `balaji_k` | Windows-10-10.0.26200-SP0, browser 157.0.8103.51 |

Path between them (before any emulation): ICMP RTT min/median/p95 = 2.0/16.5/132.0 ms, jitter 39.69 ms, loss 0.0%; single-TCP downlink ~31.1 Mbps; clock offset viewer-server +71376.8 ms (± 1.1 ms).
Viewer link: 802.11n 2.4 GHz channel 5, signal 91%, rx/tx 300/300 Mbps.

## Results per condition (mean ± 95% CI over repetitions)

| Condition | Protocol | OK runs | Mean latency (ms) | p95 latency (ms) | Stall ratio (%) | Stalls/run | Start-up (ms) | FPS | Wire (kbps) |
|---|---|---|---|---|---|---|---|---|---|
| baseline @ 0.2s | WebRTC | 5/5 | 284 ± 14 | 310 ± 19 | 1.6 ± 4.5 | 1.4 ± 3.9 | 1247 ± 367 | 29.0 | 1656 |
| baseline @ 0.2s | LL-HLS | 5/5 | 1931 ± 1211 | 2487 ± 1384 | 22.3 ± 44.8 | 2.4 ± 4.2 | 1182 ± 187 | 23.8 | 1744 |
| baseline @ 0.2s | HTTP-FLV | 5/5 | 550 ± 78 | 604 ± 101 | 1.9 ± 5.3 | 1.0 ± 2.8 | 1408 ± 444 | 29.4 | 1538 |
| baseline @ 0.5s | WebRTC | 5/5 | 586 ± 15 | 613 ± 18 | 0.0 ± 0.0 | 0.0 ± 0.0 | 1136 ± 193 | 29.6 | 1652 |
| baseline @ 0.5s | LL-HLS | 5/5 | 2840 ± 2081 | 3733 ± 2483 | 18.2 ± 15.9 | 4.0 ± 7.7 | 1128 ± 146 | 24.7 | 2101 |
| baseline @ 0.5s | HTTP-FLV | 5/5 | 693 ± 42 | 714 ± 35 | 0.3 ± 0.7 | 0.2 ± 0.6 | 1360 ± 117 | 28.7 | 1550 |
| baseline @ 1s | WebRTC | 5/5 | 1087 ± 4 | 1097 ± 6 | 0.0 ± 0.0 | 0.0 ± 0.0 | 1222 ± 208 | 29.9 | 1649 |
| baseline @ 1s | LL-HLS | 5/5 | 1423 ± 17 | 1467 ± 17 | 0.0 ± 0.0 | 0.0 ± 0.0 | 1102 ± 87 | 29.6 | 1683 |
| baseline @ 1s | HTTP-FLV | 5/5 | 1215 ± 46 | 1226 ± 48 | 0.0 ± 0.0 | 0.0 ± 0.0 | 1473 ± 180 | 29.8 | 1541 |
| baseline @ 2s | WebRTC | 5/5 | 2083 ± 3 | 2112 ± 22 | 0.0 ± 0.0 | 0.0 ± 0.0 | 1349 ± 419 | 29.8 | 1654 |
| baseline @ 2s | LL-HLS | 5/5 | 3064 ± 677 | 3781 ± 1276 | 8.9 ± 10.1 | 0.6 ± 0.7 | 1316 ± 531 | 28.2 | 2697 |
| baseline @ 2s | HTTP-FLV | 5/5 | 2250 ± 83 | 2262 ± 88 | 0.0 ± 0.0 | 0.0 ± 0.0 | 1532 ± 272 | 29.6 | 1548 |
| baseline @ 3.5s | WebRTC | 5/5 | 3580 ± 11 | 3594 ± 10 | 0.0 ± 0.0 | 0.0 ± 0.0 | 1180 ± 515 | 29.0 | 1647 |
| baseline @ 3.5s | LL-HLS | 5/5 | 4406 ± 569 | 5069 ± 928 | 6.9 ± 9.0 | 0.8 ± 0.6 | 1256 ± 422 | 28.6 | 2007 |
| baseline @ 3.5s | HTTP-FLV | 5/5 | 3766 ± 33 | 3772 ± 33 | 0.0 ± 0.0 | 0.0 ± 0.0 | 1456 ± 128 | 29.3 | 1547 |
| bw_1.6m @ 1s | WebRTC | 5/5 | 3654 ± 250 | 4947 ± 228 | 81.3 ± 9.9 | 25.0 ± 5.8 | 1722 ± 571 | 5.3 | 1600 |
| bw_1.6m @ 1s | LL-HLS | 5/5 | 6017 ± 258 | 6951 ± 236 | 27.1 ± 15.5 | 12.2 ± 6.8 | 3342 ± 362 | 21.6 | 1545 |
| bw_1.6m @ 1s | HTTP-FLV | 5/5 | 1440 ± 174 | 1456 ± 173 | 0.0 ± 0.0 | 0.0 ± 0.0 | 1517 ± 184 | 29.8 | 1522 |
| bw_2.2m @ 1s | WebRTC | 5/5 | 1144 ± 9 | 1171 ± 19 | 0.0 ± 0.0 | 0.0 ± 0.0 | 1640 ± 354 | 29.5 | 1698 |
| bw_2.2m @ 1s | LL-HLS | 5/5 | 2407 ± 512 | 3050 ± 868 | 7.8 ± 14.0 | 1.6 ± 3.8 | 2245 ± 754 | 28.4 | 1728 |
| bw_2.2m @ 1s | HTTP-FLV | 5/5 | 1329 ± 138 | 1342 ± 140 | 0.0 ± 0.0 | 0.0 ± 0.0 | 1419 ± 150 | 29.9 | 1525 |
| bw_3m @ 1s | WebRTC | 5/5 | 1125 ± 12 | 1146 ± 9 | 0.0 ± 0.0 | 0.0 ± 0.0 | 1487 ± 245 | 29.5 | 1759 |
| bw_3m @ 1s | LL-HLS | 5/5 | 3075 ± 1870 | 3808 ± 2034 | 10.7 ± 7.9 | 1.8 ± 3.0 | 2725 ± 1324 | 27.5 | 1735 |
| bw_3m @ 1s | HTTP-FLV | 5/5 | 1299 ± 51 | 1309 ± 49 | 0.0 ± 0.0 | 0.0 ± 0.0 | 1527 ± 332 | 29.9 | 1528 |
| bw_5m @ 1s | WebRTC | 5/5 | 1118 ± 10 | 1145 ± 15 | 0.0 ± 0.0 | 0.0 ± 0.0 | 1628 ± 520 | 29.4 | 1722 |
| bw_5m @ 1s | LL-HLS | 5/5 | 2615 ± 1095 | 3688 ± 1580 | 25.6 ± 22.0 | 3.6 ± 4.4 | 1600 ± 534 | 22.3 | 2138 |
| bw_5m @ 1s | HTTP-FLV | 5/5 | 1299 ± 127 | 1313 ± 125 | 0.0 ± 0.0 | 0.0 ± 0.0 | 1489 ± 151 | 29.7 | 1526 |
| cellular_4g @ 0.2s | WebRTC | 5/5 | 420 ± 23 | 469 ± 38 | 4.8 ± 7.7 | 4.8 ± 7.2 | 2250 ± 233 | 26.1 | 1896 |
| cellular_4g @ 0.2s | LL-HLS | 5/5 | 5601 ± 1234 | 6252 ± 1611 | 57.6 ± 25.1 | 16.8 ± 13.4 | 3013 ± 587 | 12.9 | 1434 |
| cellular_4g @ 0.2s | HTTP-FLV | 5/5 | 1654 ± 1434 | 3083 ± 2592 | 14.4 ± 13.2 | 10.0 ± 7.4 | 1514 ± 315 | 25.3 | 1467 |
| cellular_4g @ 0.5s | WebRTC | 5/5 | 709 ± 18 | 739 ± 20 | 1.3 ± 2.7 | 1.2 ± 2.7 | 2398 ± 622 | 27.9 | 1732 |
| cellular_4g @ 0.5s | LL-HLS | 5/5 | 6089 ± 1438 | 6768 ± 1562 | 27.9 ± 23.7 | 11.4 ± 8.4 | 3660 ± 710 | 21.6 | 1542 |
| cellular_4g @ 0.5s | HTTP-FLV | 5/5 | 2536 ± 2000 | 4690 ± 2972 | 13.0 ± 11.0 | 5.8 ± 4.8 | 1634 ± 176 | 26.0 | 1423 |
| cellular_4g @ 1s | WebRTC | 5/5 | 1209 ± 32 | 1232 ± 30 | 1.1 ± 1.3 | 1.2 ± 1.6 | 2126 ± 372 | 27.9 | 1825 |
| cellular_4g @ 1s | LL-HLS | 5/5 | 5262 ± 1191 | 6302 ± 1965 | 47.9 ± 38.0 | 12.4 ± 9.5 | 3586 ± 742 | 15.6 | 1491 |
| cellular_4g @ 1s | HTTP-FLV | 5/5 | 3584 ± 3098 | 4666 ± 3147 | 9.1 ± 7.4 | 3.2 ± 1.6 | 1680 ± 128 | 27.2 | 1434 |
| cellular_4g @ 2s | WebRTC | 5/5 | 2213 ± 23 | 2245 ± 23 | 1.5 ± 0.9 | 1.6 ± 0.7 | 2231 ± 432 | 27.8 | 1782 |
| cellular_4g @ 2s | LL-HLS | 5/5 | 5947 ± 1105 | 7252 ± 1247 | 38.4 ± 20.2 | 17.6 ± 7.3 | 4500 ± 2568 | 19.0 | 1517 |
| cellular_4g @ 2s | HTTP-FLV | 5/5 | 3061 ± 1162 | 3390 ± 1476 | 2.6 ± 4.4 | 1.2 ± 1.6 | 1540 ± 71 | 29.2 | 1496 |
| cellular_4g @ 3.5s | WebRTC | 5/5 | 3702 ± 12 | 3748 ± 18 | 2.5 ± 4.7 | 2.4 ± 5.3 | 2141 ± 527 | 27.7 | 1694 |
| cellular_4g @ 3.5s | LL-HLS | 5/5 | 6040 ± 1069 | 7075 ± 1104 | 34.1 ± 20.5 | 15.4 ± 11.1 | 2748 ± 176 | 20.8 | 1545 |
| cellular_4g @ 3.5s | HTTP-FLV | 5/5 | 4299 ± 1223 | 4761 ± 1984 | 3.1 ± 6.1 | 1.2 ± 2.2 | 1679 ± 306 | 29.0 | 1450 |
| loss_1pct @ 1s | WebRTC | 5/5 | 1109 ± 8 | 1131 ± 15 | 0.8 ± 1.0 | 0.6 ± 0.7 | 1617 ± 320 | 29.3 | 1656 |
| loss_1pct @ 1s | LL-HLS | 5/5 | 2498 ± 1974 | 2988 ± 1912 | 22.6 ± 41.2 | 4.0 ± 6.5 | 1993 ± 837 | 23.2 | 1725 |
| loss_1pct @ 1s | HTTP-FLV | 5/5 | 1256 ± 100 | 1426 ± 451 | 0.9 ± 2.5 | 0.4 ± 1.1 | 1629 ± 192 | 29.7 | 1514 |
| loss_3pct @ 1s | WebRTC | 5/5 | 1112 ± 10 | 1144 ± 20 | 0.6 ± 1.0 | 0.4 ± 0.7 | 1501 ± 463 | 28.7 | 1709 |
| loss_3pct @ 1s | LL-HLS | 5/5 | 3574 ± 996 | 4283 ± 646 | 21.7 ± 9.6 | 10.8 ± 8.9 | 1641 ± 360 | 24.6 | 1665 |
| loss_3pct @ 1s | HTTP-FLV | 5/5 | 1631 ± 820 | 2241 ± 1837 | 0.7 ± 1.3 | 0.4 ± 0.7 | 1452 ± 189 | 29.4 | 1560 |
| loss_5pct @ 1s | WebRTC | 5/5 | 1104 ± 14 | 1124 ± 24 | 1.8 ± 0.6 | 1.4 ± 0.7 | 1610 ± 427 | 28.4 | 1682 |
| loss_5pct @ 1s | LL-HLS | 5/5 | 5348 ± 1085 | 6031 ± 1336 | 32.4 ± 16.0 | 14.0 ± 6.0 | 2361 ± 1193 | 19.9 | 1547 |
| loss_5pct @ 1s | HTTP-FLV | 5/5 | 3014 ± 2906 | 4203 ± 3481 | 9.3 ± 11.5 | 3.6 ± 3.9 | 1581 ± 186 | 27.3 | 1507 |
| rtt_160ms @ 1s | WebRTC | 5/5 | 1254 ± 7 | 1281 ± 13 | 0.4 ± 0.6 | 0.4 ± 0.7 | 2495 ± 144 | 29.7 | 1662 |
| rtt_160ms @ 1s | LL-HLS | 5/5 | 5222 ± 885 | 5338 ± 849 | 26.6 ± 47.7 | 4.8 ± 7.0 | 4711 ± 1143 | 22.2 | 1588 |
| rtt_160ms @ 1s | HTTP-FLV | 5/5 | 1486 ± 139 | 1494 ± 142 | 0.0 ± 0.0 | 0.0 ± 0.0 | 1772 ± 115 | 30.0 | 1523 |
| rtt_300ms @ 1s | WebRTC | 5/5 | 1390 ± 5 | 1423 ± 11 | 0.9 ± 0.7 | 0.8 ± 0.6 | 3560 ± 426 | 28.6 | 1670 |
| rtt_300ms @ 1s | LL-HLS | 5/5 | 6090 ± 686 | 6834 ± 1169 | 20.9 ± 26.8 | 5.4 ± 5.2 | 7585 ± 2043 | 23.7 | 1508 |
| rtt_300ms @ 1s | HTTP-FLV | 5/5 | 1672 ± 285 | 1932 ± 890 | 1.7 ± 4.3 | 1.0 ± 2.2 | 2162 ± 190 | 29.3 | 1522 |
| rtt_80ms @ 1s | WebRTC | 5/5 | 1233 ± 162 | 1494 ± 815 | 5.8 ± 16.0 | 2.2 ± 6.1 | 2099 ± 384 | 27.9 | 1695 |
| rtt_80ms @ 1s | LL-HLS | 4/5 | 4024 ± 1322 | 4486 ± 843 | 46.5 ± 60.7 | 2.4 ± 3.1 | 3717 ± 1601 | 17.0 | 1021 |
| rtt_80ms @ 1s | HTTP-FLV | 5/5 | 1740 ± 1013 | 3272 ± 5238 | 4.4 ± 12.3 | 0.8 ± 2.2 | 1638 ± 268 | 28.7 | 1607 |

## Which protocol wins, per condition

Winner = lowest mean. 'clear' = paired t-test p < 0.05 against the runner-up (needs >= 3 repetitions); otherwise the difference is within run-to-run noise.

| Condition | Lowest latency | Fewest stalls |
|---|---|---|
| baseline @ 0.2s | WebRTC (clear) | WebRTC (not significant) |
| baseline @ 0.5s | WebRTC (clear) | WebRTC (not significant) |
| baseline @ 1s | WebRTC (clear) | WebRTC (tie) |
| baseline @ 2s | WebRTC (clear) | WebRTC (tie) |
| baseline @ 3.5s | WebRTC (clear) | WebRTC (tie) |
| bw_1.6m @ 1s | HTTP-FLV (clear) | HTTP-FLV (clear) |
| bw_2.2m @ 1s | WebRTC (clear) | WebRTC (tie) |
| bw_3m @ 1s | WebRTC (clear) | WebRTC (tie) |
| bw_5m @ 1s | WebRTC (clear) | WebRTC (tie) |
| cellular_4g @ 0.2s | WebRTC (not significant) | WebRTC (not significant) |
| cellular_4g @ 0.5s | WebRTC (not significant) | WebRTC (clear) |
| cellular_4g @ 1s | WebRTC (not significant) | WebRTC (clear) |
| cellular_4g @ 2s | WebRTC (not significant) | WebRTC (not significant) |
| cellular_4g @ 3.5s | WebRTC (not significant) | WebRTC (not significant) |
| loss_1pct @ 1s | WebRTC (clear) | WebRTC (not significant) |
| loss_3pct @ 1s | WebRTC (not significant) | WebRTC (not significant) |
| loss_5pct @ 1s | WebRTC (not significant) | WebRTC (not significant) |
| rtt_160ms @ 1s | WebRTC (clear) | HTTP-FLV (not significant) |
| rtt_300ms @ 1s | WebRTC (not significant) | WebRTC (not significant) |
| rtt_80ms @ 1s | WebRTC (not significant) | HTTP-FLV (not significant) |

**Scoreboard over 20 conditions** (wins / of which statistically clear):

| Protocol | Lowest latency | Fewest stalls |
|---|---|---|
| WebRTC | 19 / 10 | 11 / 2 |
| LL-HLS | 0 / 0 | 0 / 0 |
| HTTP-FLV | 1 / 1 | 3 / 1 |

6 condition(s) had a tie for fewest stalls (all within 0.05 percentage points).

## Data quality

- Barcode decode success on sampled frames: median 100.0%, min 100.0%.
- Clock-offset uncertainty per run (± RTT/2): median 1.6 ms, max 8.4 ms; offset drift start->end of run: median |0.5| ms, max |6.7| ms.
- Protocol-runs that never rendered a frame: 1: r03_rtt_80ms_b1.0/llhls

## Metric definitions

- **Latency**: display time of a frame (viewer clock converted to the server clock via the measured offset) minus the capture time encoded in that frame's 32-bit barcode. Sampled ~10x per second per player.
- **Stall**: any gap > 200 ms between consecutively presented frames (requestVideoFrameCallback), identical for all players. Stall ratio = stalled time / measurement window.
- **Start-up**: from creating the player to the first presented frame, in a fresh browser profile.
- **Wire rate**: bytes leaving the server's per-protocol tc queue during the measurement window (includes headers, retransmissions, playlist/segment requests).
