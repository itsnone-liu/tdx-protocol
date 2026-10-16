#!/usr/bin/env python3
"""1016 lab · cursor_map.py — extract all op4045 (code, c1, c2) from capture.
Shows cursor-space layout: min/max, span distribution, top codes.
"""
import struct
from collections import Counter
from pathlib import Path

CAP = Path(__file__).resolve().parent / "out" / "rec_20261015T235945Z" / "c2_c2s.bin"

data = CAP.read_bytes()
rows = []
off = 0
while off + 30 <= len(data):
    if (data[off] == 0x0C and data[off + 10] == 0xCD and data[off + 11] == 0x0F
            and data[off + 6:off + 8] == b"\x14\x00"):
        code = data[off + 14:off + 20].decode("ascii", "replace")
        c1, c2 = struct.unpack_from("<II", data, off + 20)
        rows.append((code, c1, c2))
        off += 30
    else:
        off += 1

print(f"4045 requests: {len(rows)}")
codes = Counter(r[0] for r in rows)
print(f"distinct codes: {len(codes)}; top: {codes.most_common(5)}")
c1s = [r[1] for r in rows]
c2s = [r[2] for r in rows]
spans = Counter(r[2] - r[1] for r in rows)
print(f"c1 range: 0x{min(c1s):08x}..0x{max(c1s):08x}")
print(f"c2 range: 0x{min(c2s):08x}..0x{max(c2s):08x}")
print(f"span histogram (top): {spans.most_common(8)}")
zero = [r for r in rows if r[1] == 0]
print(f"c1==0 requests: {len(zero)} (full-history pulls?)")
if zero:
    zc = Counter(r[0] for r in zero)
    print(f"  codes: {zc.most_common(5)}")
big = sorted(rows, key=lambda r: -r[2])[:5]
print("largest c2:", [(c, hex(a), hex(b)) for c, a, b in big])
same = [r for r in rows if r[1] == r[2]]
print(f"c1==c2 requests: {len(same)}")
# sample 10 rows
for r in rows[:6]:
    print(f"  {r[0]}  0x{r[1]:08x}..0x{r[2]:08x} span={r[2]-r[1]}")
