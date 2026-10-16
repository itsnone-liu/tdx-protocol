#!/usr/bin/env python3
"""Analyze fresh TDX login/data capture against historical c2/c9 sessions."""
import struct
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent / "out"
FRESH = ROOT / "rec_20261016T072253Z"
OLD = ROOT / "rec_20261015T235945Z"
MAGIC = bytes.fromhex("b1 cb 74 00")


def client_frames(path):
    data = path.read_bytes()
    frames = []
    off = 0
    while off + 12 <= len(data):
        if data[off] != 0x0C:
            off += 1
            continue
        n = 10 + struct.unpack_from("<H", data, off + 6)[0]
        if n < 12 or off + n > len(data):
            off += 1
            continue
        frames.append((off, data[off:off + n]))
        off += n
    return frames


def op11_ticket(path):
    frames = client_frames(path)
    off, frame = frames[0]
    assert off == 0 and struct.unpack_from("<H", frame, 10)[0] == 0x000B
    assert len(frame) == 292
    return frame


def op11_response(path):
    data = path.read_bytes()
    i = data.find(MAGIC)
    assert i == 0, f"first response frame not at stream start: {i}"
    zlen = struct.unpack_from("<H", data, i + 12)[0]
    op = struct.unpack_from("<H", data, i + 10)[0]
    assert op == 0x000B
    return data[i:i + 16 + zlen]


fresh_rq = FRESH / "c1_c2s.bin"
fresh_rs = FRESH / "c1_s2c.bin"
c2_rq = OLD / "c2_c2s.bin"
c2_rs = OLD / "c2_s2c.bin"
c9_rq = OLD / "c9_c2s.bin"
c9_rs = OLD / "c9_s2c.bin"

fresh_frames = client_frames(fresh_rq)
ops = [struct.unpack_from("<H", frame, 10)[0] for _, frame in fresh_frames]
first_4045 = next(((off, frame) for off, frame in fresh_frames
                   if struct.unpack_from("<H", frame, 10)[0] == 0x0FCD), None)
assert first_4045 is not None
first_4045_off, first_4045_frame = first_4045
period = first_4045_frame[-2:].hex()

fresh_ticket = op11_ticket(fresh_rq)
c2_ticket = op11_ticket(c2_rq)
c9_ticket = op11_ticket(c9_rq)
payload_start = 12
shared_len = 272
for name, ticket in (("c2", c2_ticket), ("c9", c9_ticket)):
    assert fresh_ticket[payload_start:payload_start + shared_len] == ticket[payload_start:payload_start + shared_len]
    diff = [i for i, (a, b) in enumerate(zip(fresh_ticket[payload_start:payload_start + 280],
                                              ticket[payload_start:payload_start + 280])) if a != b]
    assert diff == list(range(272, 280)), (name, diff)
    print(f"ticket fresh-vs-{name}: identical payload[0:272], differences only payload[272:280]")

assert op11_response(fresh_rs) == op11_response(c9_rs)
print("op11 response: fresh c1 exactly equals historical c9 response")
print(f"fresh c1: {len(fresh_frames)} parsed request frames; op counts={dict(Counter(hex(x) for x in ops))}")
print(f"first op4045 offset={first_4045_off}, request period tail={period} (daily=0400, 1m=0700)")
assert period == "0400", "expected this capture's first 4045 request to be daily data"
print("PASS: fresh login capture parsed and compared")
