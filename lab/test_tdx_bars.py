#!/usr/bin/env python3
"""Offline regression tests for op052d turnover field decoding."""
import struct
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from tdx_bars import parse_052d


def enc_price(value):
    sign = value < 0
    n = abs(int(value))
    first = n & 0x3f
    n >>= 6
    out = bytearray([first | (0x40 if sign else 0) | (0x80 if n else 0)])
    while n:
        b = n & 0x7f
        n >>= 7
        out.append(b | (0x80 if n else 0))
    return bytes(out)


class Test052dTurnover(unittest.TestCase):
    def test_float32_turnover_fields(self):
        # Real 601298/2026-10-15 09:35 raw fields.  Legacy pytdx get_volume
        # misdecodes amount as 8,411,749; IEEE float32 is 13,851,237.
        zipday = ((2026 - 2004) << 11) + 10 * 100 + 15
        body = bytearray(struct.pack('<H', 1))
        body += struct.pack('<HH', zipday, 9 * 60 + 35)
        for delta in (10150, -160, 50, -170):
            body += enc_price(delta)
        body += struct.pack('<II', 0x49a87500, 0x4b535a65)
        bar = parse_052d(bytes(body), 0)[0]
        self.assertEqual(bar[0], '202610150935')
        self.assertEqual(bar[5], 13851237.0)
        self.assertEqual(bar[6], 1380000)

    def test_daily_lots_convert_to_shares(self):
        body = bytearray(struct.pack('<H', 1))
        body += struct.pack('<I', 20261015)
        for delta in (10150, -170, 50, -290):
            body += enc_price(delta)
        body += struct.pack('<ff', 127870.0, 127842216.0)
        bar = parse_052d(bytes(body), 9)[0]
        self.assertEqual(bar[5], 127842216.0)
        self.assertEqual(bar[6], 12787000)


if __name__ == '__main__':
    unittest.main()
