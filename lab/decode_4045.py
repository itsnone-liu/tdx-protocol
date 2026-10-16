#!/usr/bin/env python3
"""1016 lab · decode_4045.py — crack the op4045 K-line payload layout.

Ground truth: vipdoc sz minline 399001.lc1 (last records). Brute-force the
wire payload: scan float alignments until .lc1 OHLC values appear as f32.
"""
import struct
import sys
from pathlib import Path

PAY = Path(__file__).resolve().parent / "out" / "e3b_op4045-399001_0.bin"
LC1 = Path(r"D:\tdx-node\tdx-tq-v773\vipdoc\sz\minline\399001.lc1")

data = PAY.read_bytes()
print(f"payload {len(data)}B")

# --- .lc1 ground truth (last 5 records, 32B each) ---
lc1 = LC1.read_bytes()
n = len(lc1) // 32
print(f"lc1 records: {n}")
truth = []
for i in range(n - 5, n):
    rec = lc1[i * 32:(i + 1) * 32]
    date, time_ = struct.unpack_from("<HH", rec, 0)
    o, h, l, c, amt = struct.unpack_from("<5f", rec, 4)
    vol, = struct.unpack_from("<I", rec, 24)
    # date decode: y = date//2048 + 2004, m = date%2048//100, d = date%100
    y = date // 2048 + 2004
    m = (date % 2048) // 100
    d = date % 100
    hh, mm = time_ // 60, time_ % 60
    truth.append((f"{y}-{m:02d}-{d:02d} {hh:02d}:{mm:02d}", o, h, l, c, vol, amt))
    print(f"  lc1: {y}-{m:02d}-{d:02d} {hh:02d}:{mm:02d} O={o:.2f} H={h:.2f} "
          f"L={l:.2f} C={c:.2f} vol={vol}")

# --- brute-force scan wire payload for a float equal to a truth close ---
targets = [t[4] for t in truth]  # closes
print("\nscanning payload for close-price floats...")
hits = {}
for off in range(0, len(data) - 4):
    v, = struct.unpack_from("<f", data, off)
    for ti, tv in enumerate(targets):
        if abs(v - tv) < 0.01:
            hits.setdefault(ti, []).append((off, v))
for ti in sorted(hits):
    print(f"  truth[{ti}] close={targets[ti]:.2f} found at offsets: "
          f"{[o for o, _ in hits[ti][:6]]}")

# --- try structured decode around first hit ---
if hits:
    ti = min(hits)
    off = hits[ti][0][0]
    print(f"\ncontext around first hit (truth idx {ti}, off {off}):")
    lo = max(0, off - 40)
    seg = data[lo:off + 40]
    for i in range(0, len(seg) - 3, 4):
        f, = struct.unpack_from("<f", seg, i)
        u, = struct.unpack_from("<I", seg, i)
        print(f"    +{lo + i:6d}: f32={f:12.3f}  u32={u:10d}  {seg[i:i+4].hex(' ')}")
