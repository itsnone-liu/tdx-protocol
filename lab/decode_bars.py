#!/usr/bin/env python3
"""1016 lab · decode_bars.py — parse 32B bars from op4045 payload, cross-match
times/OHLC/vol against 399-prefixed .lc1 ground truth to lock date encoding.
"""
import struct
import sys
from pathlib import Path

PAY = Path(__file__).resolve().parent / "out" / "e3b_op4045-000001_0.bin"
LC1 = Path(r"D:\tdx-node\tdx-tq-v773\vipdoc\sz\minline\sz000001.lc1")

data = PAY.read_bytes()
hdr = data[:6]
bars = []
for off in range(6, len(data) - 31, 32):
    rec = data[off:off + 32]
    mark, tmin = struct.unpack_from("<HH", rec, 0)
    o, h, l, c, amt = struct.unpack_from("<5f", rec, 4)
    vol, res = struct.unpack_from("<2I", rec, 24)
    bars.append((mark, tmin, o, h, l, c, amt, vol, res))

print(f"header: {hdr.hex(' ')}  bars: {len(bars)}")
marks = {}
for b in bars:
    marks.setdefault(b[0], []).append(b[1])
print(f"distinct markers: {len(marks)}")
for m, ts in sorted(marks.items()):
    print(f"  mark 0x{m:04x}({m}): {len(ts)} bars, tmin {min(ts)}..{max(ts)}")
print("\nfirst 3 / last 3 bars:")
for b in bars[:3] + bars[-3:]:
    print(f"  mark={b[0]:04x} t={b[1]:4d}({b[1]//60:02d}:{b[1]%60:02d}) "
          f"O={b[2]:.2f} H={b[3]:.2f} L={b[4]:.2f} C={b[5]:.2f} "
          f"amt={b[6]:,.0f} vol={b[7]:,} res={b[8]}")

# --- lc1 ground truth map: (o,h,l,c,vol,amt)-ish signature -> (date,time) ---
lc1 = LC1.read_bytes()
n = len(lc1) // 32
sig = {}
for i in range(n):
    rec = lc1[i * 32:(i + 1) * 32]
    d16, t16 = struct.unpack_from("<HH", rec, 0)
    o, h, l, c, amt = struct.unpack_from("<5f", rec, 4)
    vol, = struct.unpack_from("<I", rec, 24)
    y = d16 // 2048 + 2004
    mo = (d16 % 2048) // 100
    dd = d16 % 100
    hh, mm = t16 // 60, t16 % 60
    sig.setdefault((round(o, 2), round(h, 2), round(l, 2), round(c, 2)), []).append(
        (f"{y}-{mo:02d}-{dd:02d} {hh:02d}:{mm:02d}", vol, round(amt, 0)))

print(f"\nlc1 records: {n} (ground truth)")
hit = miss = 0
mark_to_date = {}
for b in bars:
    key = (round(b[2], 2), round(b[3], 2), round(b[4], 2), round(b[5], 2))
    if key in sig:
        hit += 1
        datestr = sig[key][0][0]
        mark_to_date.setdefault(b[0], set()).add(datestr[:10])
    else:
        miss += 1
print(f"OHLC-signature matches: {hit}/{len(bars)} (miss {miss})")
for m, dates in sorted(mark_to_date.items()):
    print(f"  mark 0x{m:04x} -> dates {sorted(dates)}")
