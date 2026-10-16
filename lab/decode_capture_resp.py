#!/usr/bin/env python3
"""1016 lab · decode_capture_resp.py — decompress captured op4045 responses
from c2_s2c and classify granularity (bars/day, time pattern)."""
import struct
import sys
import zlib
from collections import Counter
from pathlib import Path

D = Path(__file__).resolve().parent / "out" / "rec_20261015T235945Z"
data = (D / "c2_s2c.bin").read_bytes()

MAGIC = bytes.fromhex("b1 cb 74 00")
frames = []
off = 0
while True:
    idx = data.find(MAGIC, off)
    if idx < 0 or idx + 16 > len(data):
        break
    op, = struct.unpack_from("<H", data, idx + 10)
    zlen, rawlen = struct.unpack_from("<HH", data, idx + 12)
    if op == 0x0FCD and zlen > 100 and idx + 16 + zlen <= len(data):
        frames.append((idx, zlen, rawlen))
    off = idx + 1

print(f"captured 4045 responses: {len(frames)}")
gran = Counter()
samples = []
for idx, zlen, rawlen in frames[:400]:
    payload = data[idx + 16: idx + 16 + zlen]
    if payload[:2] not in (b"\x78\x9c", b"\x78\x01", b"\x78\xda"):
        continue
    try:
        raw = zlib.decompress(payload)
    except zlib.error:
        continue
    bars = []
    for o in range(6, len(raw) - 31, 32):
        mark, tmin = struct.unpack_from("<HH", raw, o)
        bars.append((mark, tmin))
    if not bars:
        continue
    days = {}
    for mark, t in bars:
        days.setdefault(mark, set()).add(t)
    per_day = round(len(bars) / max(len(days), 1))
    tt = sorted({t for _, t in bars})
    gran[(per_day, tt[0], tt[-1])] += 1
    if len(samples) < 4:
        samples.append((idx, len(bars), len(days), per_day, tt[0], tt[-1],
                        bars[0], bars[-1]))

for (pd, t0, t1), cnt in gran.most_common(10):
    print(f"  {pd} bars/day, tmin {t0}..{t1}: {cnt} responses")
for s in samples:
    idx, nb, nd, pd, t0, t1, first, last = s
    print(f"  sample @{idx}: {nb} bars/{nd}d={pd}/day t {t0}..{t1} "
          f"first={first} last={last}")
