# Comparison: maxlat_0.8_all3 vs hls_default_all3 vs hls_default_alone

| Condition | Protocol | maxlat_0.8_all3: latency (ms) | hls_default_all3: latency (ms) | hls_default_alone: latency (ms) | maxlat_0.8_all3: stall (%) | hls_default_all3: stall (%) | hls_default_alone: stall (%) |
|---|---|---|---|---|---|---|---|
| baseline @ 0.5s | WebRTC | 584 ± 4 | 605 ± 8 | - | 0.0 ± 0.0 | 0.0 ± 0.0 | - |
| baseline @ 0.5s | LL-HLS | 1355 ± 461 | 2854 ± 6013 | 2000 ± 1985 | 33.4 ± 265.2 | 48.9 ± 190.2 | 26.4 ± 145.8 |
| baseline @ 0.5s | HTTP-FLV | 840 ± 476 | 703 ± 68 | - | 0.0 ± 0.0 | 0.0 ± 0.0 | - |
| cellular_4g @ 0.5s | WebRTC | 693 ± 382 | 724 ± 104 | - | 1.5 ± 0.6 | 1.8 ± 3.3 | - |
| cellular_4g @ 0.5s | LL-HLS | 2167 ± 1886 | 5822 ± 8704 | 5247 ± 517 | 93.3 ± 57.2 | 41.9 ± 73.2 | 55.7 ± 96.3 |
| cellular_4g @ 0.5s | HTTP-FLV | 866 ± 771 | 2686 ± 6925 | - | 0.5 ± 6.4 | 9.5 ± 2.6 | - |
| rtt_160ms @ 0.5s | WebRTC | 759 ± 53 | 769 ± 97 | - | 0.0 ± 0.0 | 0.8 ± 1.8 | - |
| rtt_160ms @ 0.5s | LL-HLS | 2123 ± 3618 | 4460 ± 459 | 4985 ± 6187 | 97.5 ± 32.4 | 48.6 ± 414.9 | 10.5 ± 18.2 |
| rtt_160ms @ 0.5s | HTTP-FLV | 925 ± 1040 | 838 ± 300 | - | 0.0 ± 0.0 | 0.0 ± 0.0 | - |
