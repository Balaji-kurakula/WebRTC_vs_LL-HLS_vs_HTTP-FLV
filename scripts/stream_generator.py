#!/usr/bin/env python3
"""
Real-time 720p30 YUV420p test stream generator with:
1. 32-bit binary wall-clock millisecond barcode (top strip) for zero-error JS canvas latency measurement.
2. Large human-readable digital clock (HH:MM:SS.mmm, epoch ms, and frame counter).
3. Smooth horizontal motion bar + radar sweep for visual stall/smoothness inspection.
Pipes raw YUV420p frames directly to FFmpeg -> RTMP ingest.
"""

import sys
import time
import datetime
import subprocess
import signal
import numpy as np

WIDTH = 1280
HEIGHT = 720
FPS = 30
FRAME_DURATION = 1.0 / FPS

# 5x7 bitmap font for fast, zero-dependency human-readable overlay
FONT_5X7 = {
    '0': ["01110", "10001", "10011", "10101", "11001", "10001", "01110"],
    '1': ["00100", "01100", "00100", "00100", "00100", "00100", "01110"],
    '2': ["01110", "10001", "00001", "00010", "00100", "01000", "11111"],
    '3': ["11111", "00010", "00100", "00010", "00001", "10001", "01110"],
    '4': ["00010", "00110", "01010", "10010", "11111", "00010", "00010"],
    '5': ["11111", "10000", "11110", "00001", "00001", "10001", "01110"],
    '6': ["00110", "01000", "10000", "11110", "10001", "10001", "01110"],
    '7': ["11111", "00001", "00010", "00100", "01000", "01000", "01000"],
    '8': ["01110", "10001", "10001", "01110", "10001", "10001", "01110"],
    '9': ["01110", "10001", "10001", "01111", "00001", "00010", "01100"],
    ':': ["00000", "00100", "00100", "00000", "00100", "00100", "00000"],
    '.': ["00000", "00000", "00000", "00000", "00000", "01100", "01100"],
    '-': ["00000", "00000", "00000", "11111", "00000", "00000", "00000"],
    '|': ["00100", "00100", "00100", "00100", "00100", "00100", "00100"],
    ' ': ["00000", "00000", "00000", "00000", "00000", "00000", "00000"],
    'A': ["01110", "10001", "10001", "11111", "10001", "10001", "10001"],
    'B': ["11110", "10001", "10001", "11110", "10001", "10001", "11110"],
    'C': ["01110", "10001", "10000", "10000", "10000", "10001", "01110"],
    'D': ["11100", "10010", "10001", "10001", "10001", "10010", "11100"],
    'E': ["11111", "10000", "10000", "11110", "10000", "10000", "11111"],
    'F': ["11111", "10000", "10000", "11110", "10000", "10000", "10000"],
    'G': ["01110", "10001", "10000", "10111", "10001", "10001", "01111"],
    'H': ["10001", "10001", "10001", "11111", "10001", "10001", "10001"],
    'I': ["01110", "00100", "00100", "00100", "00100", "00100", "01110"],
    'K': ["10001", "10010", "10100", "11000", "10100", "10010", "10001"],
    'L': ["10000", "10000", "10000", "10000", "10000", "10000", "11111"],
    'M': ["10001", "11011", "10101", "10101", "10001", "10001", "10001"],
    'N': ["10001", "11001", "10101", "10011", "10001", "10001", "10001"],
    'O': ["01110", "10001", "10001", "10001", "10001", "10001", "01110"],
    'P': ["11110", "10001", "10001", "11110", "10000", "10000", "10000"],
    'R': ["11110", "10001", "10001", "11110", "10100", "10010", "10001"],
    'S': ["01111", "10000", "10000", "01110", "00001", "00001", "11110"],
    'T': ["11111", "00100", "00100", "00100", "00100", "00100", "00100"],
    'U': ["10001", "10001", "10001", "10001", "10001", "10001", "01110"],
    'V': ["10001", "10001", "10001", "10001", "10001", "01010", "00100"],
    'W': ["10001", "10001", "10001", "10101", "10101", "10101", "01010"],
}

GLYPHS = {}
for ch, rows in FONT_5X7.items():
    arr = np.array([[1 if c == '1' else 0 for c in r] for r in rows], dtype=np.uint8)
    GLYPHS[ch] = arr


def draw_text(y_plane, text, x0, y0, scale=4, fg=240):
    x = x0
    for ch in text.upper():
        glyph = GLYPHS.get(ch, GLYPHS[' '])
        scaled = np.repeat(np.repeat(glyph, scale, axis=0), scale, axis=1)
        h, w = scaled.shape
        if y0 + h <= HEIGHT and x + w <= WIDTH:
            region = y_plane[y0:y0+h, x:x+w]
            region[scaled == 1] = fg
        x += (5 + 1) * scale


def build_base_frame():
    """Creates a clean dark dashboard background in YUV420p."""
    y = np.full((HEIGHT, WIDTH), 24, dtype=np.uint8)
    u = np.full((HEIGHT // 2, WIDTH // 2), 128, dtype=np.uint8)
    v = np.full((HEIGHT // 2, WIDTH // 2), 128, dtype=np.uint8)

    # Top barcode panel background (rows 10..74)
    y[10:74, 20:WIDTH-20] = 16

    # Title banner
    draw_text(y, "CS6048 LIVE TESTBED: WEBRTC VS LL-HLS VS HTTP-FLV", 60, 110, scale=4, fg=220)

    # Clock box background
    y[165:340, 60:WIDTH-60] = 36
    # Motion track background
    y[400:500, 60:WIDTH-60] = 40

    # Color reference bars at bottom for visual quality check
    bar_w = (WIDTH - 120) // 6
    uv_colors = [
        (180, 90, 200),   # Red-ish
        (170, 80, 80),    # Green-ish
        (120, 200, 100),  # Blue-ish
        (200, 60, 140),   # Yellow-ish
        (150, 170, 180),  # Magenta-ish
        (180, 160, 70),   # Cyan-ish
    ]
    for i, (yv, uv, vv) in enumerate(uv_colors):
        bx1 = 60 + i * bar_w
        bx2 = bx1 + bar_w
        y[550:660, bx1:bx2] = yv
        u[275:330, bx1//2:bx2//2] = uv
        v[275:330, bx1//2:bx2//2] = vv

    return y, u, v


def encode_barcode(y_plane, timestamp_ms):
    """
    Encodes the lower 32 bits of `timestamp_ms` (covers ~49.7 days in ms)
    into 36 cells at y=[20..60]:
    - Cell 0: Start marker = 1 (White)
    - Cell 1: Start marker = 0 (Black)
    - Cells 2..33: 32 bits of (timestamp_ms & 0xFFFFFFFF), MSB first
    - Cell 34: End marker = 1 (White)
    - Cell 35: Parity bit (XOR of 32 bits)
    Each cell is 32px wide x 40px tall, starting at x=64.
    """
    val = int(timestamp_ms) & 0xFFFFFFFF
    bits = [(val >> (31 - i)) & 1 for i in range(32)]
    parity = sum(bits) & 1
    cells = [1, 0] + bits + [1, parity]

    cell_w = 32
    x_start = 64
    y_top, y_bot = 20, 60

    for idx, bit in enumerate(cells):
        x1 = x_start + idx * cell_w
        x2 = x1 + cell_w - 2  # 2px border between cells
        y_plane[y_top:y_bot, x1:x2] = 245 if bit else 16


def main():
    rtmp_url = sys.argv[1] if len(sys.argv) > 1 else "rtmp://127.0.0.1:1935/live/stream"

    ffmpeg_cmd = [
        "ffmpeg",
        "-hide_banner", "-loglevel", "warning",
        "-fflags", "+nobuffer+flush_packets",
        "-flags", "low_delay",
        # Video input: raw YUV420p from stdin
        "-thread_queue_size", "4",
        "-f", "rawvideo",
        "-pix_fmt", "yuv420p",
        "-s", f"{WIDTH}x{HEIGHT}",
        "-r", str(FPS),
        "-i", "pipe:0",
        # Audio input: real-time paced sine wave
        "-thread_queue_size", "16",
        "-re",
        "-f", "lavfi",
        "-i", "sine=frequency=440:sample_rate=44100",
        # Video encoding: strictly CBR, zero B-frames, 0.5s GOP (15 frames), ultrafast, zerolatency
        "-c:v", "libx264",
        "-preset", "ultrafast",
        "-tune", "zerolatency",
        "-profile:v", "baseline",
        "-x264-params", "sliced-threads=1:sync-lookahead=0:rc-lookahead=0:bframes=0",
        "-b:v", "1800k",
        "-maxrate", "1800k",
        "-bufsize", "900k",
        "-pix_fmt", "yuv420p",
        "-g", "15",
        "-keyint_min", "15",
        "-sc_threshold", "0",
        "-bf", "0",
        # Audio encoding: AAC 96k
        "-c:a", "aac",
        "-b:a", "96k",
        "-ar", "44100",
        "-ac", "2",
        "-af", "volume=0.08",
        "-flush_packets", "1",
        # Output to RTMP
        "-f", "flv",
        rtmp_url,
    ]

    print(f"[Ingest] Starting FFmpeg -> {rtmp_url}")
    proc = subprocess.Popen(ffmpeg_cmd, stdin=subprocess.PIPE)

    def cleanup(signum, frame):
        print("\n[Ingest] Stopping stream generator...")
        try:
            proc.stdin.close()
        except Exception:
            pass
        proc.terminate()
        sys.exit(0)

    signal.signal(signal.SIGINT, cleanup)
    signal.signal(signal.SIGTERM, cleanup)

    base_y, base_u, base_v = build_base_frame()
    uv_bytes = base_u.tobytes() + base_v.tobytes()

    frame_idx = 0
    start_perf = time.perf_counter()
    # Pacing health (logged every 10 s): frames written more than one frame-interval late
    win_late, win_max_lag, win_start = 0, 0.0, start_perf

    while True:
        now_ms = int(time.time() * 1000)
        dt = datetime.datetime.fromtimestamp(now_ms / 1000.0)
        clock_str = dt.strftime("%H:%M:%S") + f".{now_ms % 1000:03d}"

        y = base_y.copy()

        # 1. Draw 32-bit binary barcode at top
        encode_barcode(y, now_ms)

        # 2. Draw human-readable timestamps
        draw_text(y, f"TIME {clock_str}", 90, 190, scale=6, fg=250)
        draw_text(y, f"MS {now_ms}   FRAME {frame_idx:07d}", 90, 270, scale=5, fg=210)

        # 3. Draw smooth horizontal motion indicator (sweeps across every 2 seconds = 60 frames)
        track_w = WIDTH - 200
        pos_x = 60 + int(((frame_idx % 60) / 60.0) * track_w)
        y[410:490, pos_x:pos_x+80] = 245

        try:
            proc.stdin.write(y.tobytes())
            proc.stdin.write(uv_bytes)
        except BrokenPipeError:
            print("[Ingest] FFmpeg pipe closed.")
            break

        lag = time.perf_counter() - (start_perf + frame_idx * FRAME_DURATION)
        win_max_lag = max(win_max_lag, lag)
        if lag > FRAME_DURATION:
            win_late += 1

        frame_idx += 1
        target_time = start_perf + frame_idx * FRAME_DURATION
        sleep_time = target_time - time.perf_counter()
        if sleep_time > 0:
            time.sleep(sleep_time)

        if target_time - win_start >= 10.0:
            print(f"[Ingest] {datetime.datetime.now().isoformat(timespec='seconds')} frames={frame_idx} "
                  f"late_frames_10s={win_late} max_lag_ms={win_max_lag * 1000:.1f}", flush=True)
            win_late, win_max_lag, win_start = 0, 0.0, target_time


if __name__ == "__main__":
    main()
