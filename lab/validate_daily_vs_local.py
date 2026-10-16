#!/usr/bin/env python3
"""Validate CLI daily output against local TDX .day files (byte-level field match)."""
import csv, struct, sys
from pathlib import Path

CSV_PATH = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).parent / 'out' / 'tdx_cli_final_test.csv'
VIPDOC = Path(r'D:\tdx-node\tdx-tq-v773\vipdoc')


def market_dir(code):
    return 'sh' if code[0] in '56' else 'sz'


def load_local_day(code):
    """Load local .day file → dict {date: (o,h,l,c,amt,vol)}."""
    p = VIPDOC / market_dir(code) / 'lday' / f'{market_dir(code)}{code}.day'
    if not p.exists():
        return None
    raw = p.read_bytes()
    out = {}
    for i in range(0, len(raw) - 31, 32):
        date, o, h, l, c = struct.unpack_from('<5I', raw, i)
        amt, = struct.unpack_from('<f', raw, i + 20)
        vol, = struct.unpack_from('<I', raw, i + 24)
        out[date] = (o / 100, h / 100, l / 100, c / 100, amt, vol)
    return out


# Load CLI daily output
cli_daily = {}
with CSV_PATH.open(newline='', encoding='utf-8') as f:
    for row in csv.DictReader(f):
        if row['period'] != 'daily':
            continue
        code = row['code']
        date = int(float(row['time_key']))
        cli_daily.setdefault(code, {})[date] = (
            float(row['open']), float(row['high']), float(row['low']),
            float(row['close']), float(row['amount']), int(float(row['volume'])))

total_match = total_check = 0
for code, bars in sorted(cli_daily.items()):
    local = load_local_day(code)
    if local is None:
        print(f'{code}: no local .day file, skip')
        continue
    match = mismatch = 0
    for date, cli_vals in sorted(bars.items()):
        if date not in local:
            continue  # date not in local file (could be today's not-yet-written data)
        local_vals = local[date]
        total_check += 1
        # Compare OHLC (allow float rounding tolerance)
        if all(abs(a - b) < 0.005 for a, b in zip(cli_vals[:4], local_vals[:4])):
            match += 1
            total_match += 1
        else:
            mismatch += 1
            if mismatch <= 2:
                print(f'  MISMATCH {code} {date}: CLI={cli_vals[:4]} local={local_vals[:4]}')
    print(f'{code}: {match}/{match + mismatch} daily bars match local .day')

print(f'\nTotal: {total_match}/{total_check} daily records match ({100 * total_match / max(total_check, 1):.1f}%)')
if total_check == 0:
    print('No overlapping dates to compare (CLI may return older history than local file)')
