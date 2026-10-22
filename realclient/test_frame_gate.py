#!/usr/bin/env python3
"""Frame/record-count gates replayed on the real 2026-10-22 R4 capture bytes.

Every assertion below runs on the bytes the client actually received at the five
successful auction capture points (09:24:55 ... 09:30:06), so both halves of the
gate (byte count + declared-vs-parsed record count) are verified against reality
instead of a synthetic frame. The sixth scheduled point (09:27:55) is the one that
died client-side with "truncated response"; it produced no response/clear pair and
is therefore absent from the manifest -- the shortened-stream cases below are what
that failure looks like to `exact()`/`unwrap()`.

Origin: R4/R5 diff list D8/C-1/C-3, see docs/R4R5_DIFF_LIST_20261022.md.
"""
import json, struct, sys, unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from cli import exact, unwrap, recv, check_quote_count  # noqa: E402
from tdxpy.parser.std.get_security_quotes import GetSecurityQuotesCmd  # noqa: E402

FX = Path(__file__).resolve().parent / 'test_fixtures' / 'r4_20261022'
MAN = json.loads((FX / 'manifest.json').read_text())
FAILED_POINT = '09_27_55_092755_000'  # client-side truncation, no pair captured


def load(tag):
    return ((FX / f'{tag}_response.bin').read_bytes(), (FX / f'{tag}_clear.bin').read_bytes())


def parse_quotes(clear, stocks):
    """Decode the real response body with the production decoder (socket unused)."""
    cmd = GetSecurityQuotesCmd(None)
    cmd.setParams([(m, c) for m, c in stocks])
    return cmd.parseResponse(clear) or []


class Stream:
    """Minimal socket stand-in: hands out bytes and then reports EOF."""

    def __init__(self, data):
        self.buf = bytearray(data)

    def recv(self, n):
        out = bytes(self.buf[:n])
        del self.buf[:n]
        return out


class FrameGate(unittest.TestCase):
    def test_fixture_set_is_the_five_ok_points(self):
        self.assertEqual(len(MAN), 5)
        self.assertNotIn(FAILED_POINT, MAN)

    def test_byte_count_identity_holds_at_every_point(self):
        for tag, m in MAN.items():
            resp, clear = load(tag)
            packed, raw = struct.unpack_from('<HH', resp, 12)
            with self.subTest(tag=tag):
                self.assertEqual(packed, len(resp) - 16, 'header packed != actual body bytes')
                self.assertEqual(raw, len(clear), 'header raw_len != clear length')
                self.assertEqual(packed, m['packed'])
                self.assertEqual(len(clear), m['clear_bytes'])
                self.assertEqual(unwrap(resp[16:], packed, raw), clear)

    def test_declared_count_equals_parsed_records(self):
        for tag, m in MAN.items():
            clear = load(tag)[1]
            rows = parse_quotes(clear, m['stocks'])
            with self.subTest(tag=tag):
                declared = check_quote_count(clear, rows)
                self.assertEqual(declared, m['declared'])
                self.assertEqual(declared, len(rows))
                self.assertEqual(struct.unpack_from('<H', clear, 2)[0], len(m['stocks']))

    def test_every_returned_key_is_whitelisted(self):
        for tag, m in MAN.items():
            clear = load(tag)[1]
            rows = parse_quotes(clear, m['stocks'])
            expected = {(mm, cc) for mm, cc in m['stocks']}
            with self.subTest(tag=tag):
                self.assertEqual({(r['market'], r['code']) for r in rows}, expected)

    def test_preopen_records_exist_with_zero_price(self):
        """C-1 counter-example, frozen: absence is the halt signal, not price<=0.

        09:24:55 returns all five requested records while every one of them reports
        price=0/vol=0 -- yet bid1/ask1 already carry real prices. So a parser that
        treats price<=0 as "suspended" would mislabel the entire pre-open market.
        """
        clear = load('09_24_55_092455_001')[1]
        rows = parse_quotes(clear, MAN['09_24_55_092455_001']['stocks'])
        self.assertEqual(len(rows), 5)
        self.assertEqual([r['price'] for r in rows], [0.0] * 5)
        self.assertEqual([r['vol'] for r in rows], [0] * 5)
        self.assertTrue(all(r['bid1'] > 0 for r in rows))
        self.assertNotIn(FAILED_POINT, MAN)  # no record at all == the real halt signal

    def test_recv_replays_real_frame_from_stream(self):
        for tag in MAN:
            resp, clear = load(tag)
            with self.subTest(tag=tag):
                hdr, body = recv(Stream(resp))
                self.assertEqual(hdr, resp[:16])
                self.assertEqual(body, clear)

    def test_short_stream_fails_closed(self):
        resp = load('09_24_55_092455_001')[0]
        with self.assertRaises(ConnectionError):
            recv(Stream(resp[:-1]))

    def test_packed_larger_than_stream_fails_closed(self):
        resp = bytearray(load('09_24_55_092455_001')[0])
        packed = struct.unpack_from('<H', resp, 12)[0]
        struct.pack_into('<H', resp, 12, packed + 1)
        with self.assertRaises(ConnectionError):
            recv(Stream(bytes(resp)))

    def test_exact_reports_byte_counts(self):
        with self.assertRaises(ConnectionError) as cm:
            exact(Stream(b'abc'), 5)
        self.assertIn('got 3 of 5 bytes', str(cm.exception))

    def test_raw_len_mismatch_fails_closed(self):
        resp, clear = load('09_30_06_093006_000')
        packed, raw = struct.unpack_from('<HH', resp, 12)
        for bad_raw in (raw + 1, raw - 1, 0):
            with self.subTest(bad_raw=bad_raw):
                with self.assertRaises(ValueError):
                    unwrap(resp[16:], packed, bad_raw)

    def test_zlib_trailing_bytes_fail_closed(self):
        resp = load('09_30_06_093006_000')[0]
        packed, raw = struct.unpack_from('<HH', resp, 12)
        with self.assertRaises(ValueError):
            unwrap(resp[16:] + b'\0' * 4, packed + 4, raw)

    def test_truncated_compressed_stream_fails_closed(self):
        resp = load('09_30_06_093006_000')[0]
        packed, raw = struct.unpack_from('<HH', resp, 12)
        with self.assertRaises(ValueError):
            unwrap(resp[16:packed - 6], packed - 6, raw)

    def test_count_shortfall_fails_closed(self):
        for tag, m in MAN.items():
            clear = load(tag)[1]
            rows = parse_quotes(clear, m['stocks'])
            with self.subTest(tag=tag):
                with self.assertRaises(ValueError) as cm:
                    check_quote_count(clear, rows[:-1])
                self.assertIn('shortfall', str(cm.exception))

    def test_over_declared_count_is_not_fatal(self):
        """More parsed rows than declared is redundant, not corruption (D8 note)."""
        clear = bytearray(load('09_30_06_093006_000')[1])
        struct.pack_into('<H', clear, 2, 3)
        rows = parse_quotes(bytes(clear), MAN['09_30_06_093006_000']['stocks'])
        self.assertEqual(check_quote_count(bytes(clear), rows), 3)

    def test_tampered_declared_count_fails_closed(self):
        """声明数被抬高时，解码器或闸门必须有一环报错，绝不静默通过。"""
        clear = bytearray(load('09_30_06_093006_000')[1])
        struct.pack_into('<H', clear, 2, 99)
        with self.assertRaises((ValueError, struct.error)):
            check_quote_count(bytes(clear), parse_quotes(bytes(clear), MAN['09_30_06_093006_000']['stocks']))

    def test_count_gate_tolerates_absent_body(self):
        self.assertIsNone(check_quote_count(None, []))
        self.assertIsNone(check_quote_count(b'\x01', []))


if __name__ == '__main__':
    unittest.main()