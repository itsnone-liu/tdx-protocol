#!/usr/bin/env python3
"""1016 lab · granularity_probe.py — find the 1-min stream variant of op4045.

op4045 payload starts with 2 unknown bytes before the code (captured: 00 00 =
5-min stream). Sweep those bytes; classify each response by bars-per-day:
240 => 1-min, 48 => 5-min, 16 => 15-min, 8 => 30-min, 4 => hour.
"""
import socket
import struct
import sys
import zlib

HOST, PORT = "175.178.112.197", 7709
HELLO = bytes.fromhex("00 00 00 00 00 00 10 00 10 00 52 04 00 00 00 00"
                      "d0 07 00 00 00 00 00 00 00 00")
OP13 = bytes.fromhex("0c 02 18 94 00 01 03 00 03 00 0d 00 01")
OP4059 = bytes.fromhex("0c 03 18 99 00 01 20 00 20 00 db 0f"
                       "74 64 78 6c 65 76 65 6c 00 00 00 29 5c f7 40 11"
                       "00 00 00 00 00 00 00 00 00 00 00 00 00 05")


def drain(sock, settle=1.0):
    sock.settimeout(settle)
    buf = b""
    try:
        while True:
            c = sock.recv(65536)
            if not c:
                break
            buf += c
    except socket.timeout:
        pass
    return buf


def req4045(m1, m2, code, c1, c2):
    return (b"\x0c\x01\x38\x8d\x00\x01\x14\x00\x14\x00\xcd\x0f"
            + bytes([m1, m2]) + code + struct.pack("<II", c1, c2) + b"\x00\x00")


def bars_of(buf):
    idx = buf.find(b"\xcd\x0f")
    if idx < 0:
        return None
    zlen, rawlen = struct.unpack_from("<HH", buf, idx + 2)
    payload = buf[idx + 6: idx + 6 + zlen]
    if payload[:2] not in (b"\x78\x9c", b"\x78\x01", b"\x78\xda"):
        return []
    raw = zlib.decompress(payload)
    out = []
    for off in range(6, len(raw) - 31, 32):
        mark, tmin = struct.unpack_from("<HH", raw, off)
        out.append((mark, tmin))
    return out


def main() -> int:
    # 4-day window keeps every granularity within 768-bar cap except 1-min
    C1, C2 = 0x01352774, 0x01352779
    s = socket.create_connection((HOST, PORT), timeout=8)
    s.sendall(HELLO); drain(s)
    s.sendall(OP13); drain(s)
    s.sendall(OP4059); drain(s)
    found = []
    for m1 in (0x00, 0x01, 0x02, 0x03):
        for m2 in (0x00, 0x01, 0x02, 0x03, 0x04, 0x05, 0x06, 0x07, 0x08):
            s.sendall(req4045(m1, m2, b"000001", C1, C2))
            bars = bars_of(drain(s))
            if not bars:
                print(f"m=({m1:02x},{m2:02x}): no/empty")
                continue
            days = {}
            for mark, t in bars:
                days.setdefault(mark, set()).add(t)
            ndays = len(days)
            per_day = sorted({len(v) for v in days.values()})
            tt = sorted({t for _, t in bars})
            print(f"m=({m1:02x},{m2:02x}): {len(bars)} bars / {ndays} days "
                  f"(~{len(bars)//max(ndays,1)}/day), tmin {tt[0]}..{tt[-1]}")
            found.append((m1, m2, len(bars) // max(ndays, 1)))
    s.close()
    for m1, m2, pd in found:
        if pd >= 200:
            print(f"*** 1-MIN CANDIDATE: ({m1:02x},{m2:02x}) {pd} bars/day")
    return 0


if __name__ == "__main__":
    sys.exit(main())
