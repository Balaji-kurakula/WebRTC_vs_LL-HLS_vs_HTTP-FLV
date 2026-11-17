# Comparison: all_three_together vs httpflv_alone

| Condition | Protocol | all_three_together: latency (ms) | httpflv_alone: latency (ms) | all_three_together: stall (%) | httpflv_alone: stall (%) |
|---|---|---|---|---|---|
| cellular_4g @ 0.5s | WebRTC | 709 ± 18 | - | 1.3 ± 2.7 | - |
| cellular_4g @ 0.5s | LL-HLS | 6089 ± 1438 | - | 27.9 ± 23.7 | - |
| cellular_4g @ 0.5s | HTTP-FLV | 2536 ± 2000 | 1025 ± 737 | 13.0 ± 11.0 | 3.7 ± 14.1 |
| loss_5pct @ 1s | WebRTC | 1104 ± 14 | - | 1.8 ± 0.6 | - |
| loss_5pct @ 1s | LL-HLS | 5348 ± 1085 | - | 32.4 ± 16.0 | - |
| loss_5pct @ 1s | HTTP-FLV | 3014 ± 2906 | 1666 ± 1022 | 9.3 ± 11.5 | 1.5 ± 4.7 |
