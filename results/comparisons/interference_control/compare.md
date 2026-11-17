# Comparison: all_three_together vs webrtc_alone vs llhls_alone vs httpflv_alone

| Condition | Protocol | all_three_together: latency (ms) | webrtc_alone: latency (ms) | llhls_alone: latency (ms) | httpflv_alone: latency (ms) | all_three_together: stall (%) | webrtc_alone: stall (%) | llhls_alone: stall (%) | httpflv_alone: stall (%) |
|---|---|---|---|---|---|---|---|---|---|
| baseline @ 1s | WebRTC | 1087 ± 4 | 1085 ± 6 | - | - | 0.0 ± 0.0 | 0.0 ± 0.0 | - | - |
| baseline @ 1s | LL-HLS | 1423 ± 17 | - | 1233 ± 727 | - | 0.0 ± 0.0 | - | 1.6 ± 6.7 | - |
| baseline @ 1s | HTTP-FLV | 1215 ± 46 | - | - | 1209 ± 85 | 0.0 ± 0.0 | - | - | 0.0 ± 0.0 |
| cellular_4g @ 1s | WebRTC | 1209 ± 32 | 1186 ± 57 | - | - | 1.1 ± 1.3 | 0.0 ± 0.0 | - | - |
| cellular_4g @ 1s | LL-HLS | 5262 ± 1191 | - | 5005 ± 926 | - | 47.9 ± 38.0 | - | 30.7 ± 48.3 | - |
| cellular_4g @ 1s | HTTP-FLV | 3584 ± 3098 | - | - | 1452 ± 143 | 9.1 ± 7.4 | - | - | 0.0 ± 0.0 |
