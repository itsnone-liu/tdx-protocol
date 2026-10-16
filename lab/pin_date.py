#!/usr/bin/env python3
"""1016 lab · pin_date.py — pin the exact date encoding of the u16 day field.

Reads sz000001.lc1, extracts the ordered distinct day-field sequence,
assumes the LAST day == 2026-10-16 (client refreshed through today), derives
the epoch, then validates: every day decodes to a Mon-Fri, and gaps between
days equal weekend/holiday gaps. Prints candidate formulas and validation.
"""
import struct
from datetime import date, timedelta
from pathlib import Path

LC1 = Path(r"D:\tdx-node\tdx-tq-v773\vipdoc\sz\minline\sz000001.lc1")
ASSUMED_LAST = date(2026, 10, 16)

lc1 = LC1.read_bytes()
n = len(lc1) // 32
days = []
for i in range(n):
    d16, t16 = struct.unpack_from("<HH", lc1, i * 32)
    if not days or days[-1] != d16:
        days.append(d16)

first, last = days[0], days[-1]
print(f"records={n} distinct days={len(days)} first={first}(0x{first:04x}) "
      f"last={last}(0x{last:04x})")

# candidate A: day = epoch + u16 (calendar days)
epoch = ASSUMED_LAST - timedelta(days=last)
print(f"\ncandidate A (calendar-day counter): epoch = {epoch}")
ok = bad = 0
samples = []
for d16 in days:
    dt = epoch + timedelta(days=d16)
    if dt.weekday() < 5:
        ok += 1
    else:
        bad += 1
    if d16 in (first, days[len(days)//2], last) or len(samples) < 3:
        samples.append((d16, dt.isoformat(), dt.strftime("%a")))
for s in samples[:8]:
    print(f"  {s[0]} -> {s[1]} {s[2]}")
print(f"  weekday check: Mon-Fri {ok}/{len(days)}, weekend {bad}")

# candidate B: (y-2004)*2048 + m*100 + d
def cand_b(d16):
    y = d16 // 2048 + 2004
    rem = d16 % 2048
    return y, rem // 100, rem % 100
v = cand_b(last)
print(f"\ncandidate B ((y-2004)*2048+m*100+d): last {last} -> {v}"
      f" {'INVALID' if not (1 <= v[1] <= 12 and 1 <= v[2] <= 31) else 'valid'}")

# candidate C: trading-day counter
# if days were a pure trading-day sequence, consecutive d16 would always +1;
# check deltas
deltas = {}
for a, b in zip(days, days[1:]):
    deltas[b - a] = deltas.get(b - a, 0) + 1
print(f"\nday-field deltas histogram: {deltas}")
print("(all +1 => pure trading-day counter; 1/3 mix => calendar days)")
