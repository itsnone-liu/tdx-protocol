#!/usr/bin/env python3
"""1016 lab · cursor_probe.py — probe cursor->data-window mapping.

For each (c1,c2) probe on stock 000001: pull, decompress, report the day-marker
range and bar counts. Day markers assumed = calendar-day counters; relative
movement of markers vs cursor movement reveals the mapping.
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


def drain(sock, settle=1.2):
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


def req4045(code: bytes, c1: int, c2: int) -> bytes:
    return (b"\x0c\x01\x38\x8d\x00\x01\x14\x00\x14\x00\xcd\x0f\x00\x00"
            + code + struct.pack("<II", c1, c2) + b"\x00\x00")


def parse_bars(payload: bytes):
    bars = []
    for off in range(6, len(payload) - 31, 32):
        mark, tmin = struct.unpack_from("<HH", payload, off)
        o, h, l, c = struct.unpack_from("<4f", payload, off + 4)
        bars.append((mark, tmin, c))
    return bars


def probe(sock, c1, c2, code=b"000001"):
    sock.sendall(req4045(code, c1, c2))
    buf = drain(sock)
    idx = buf.find(b"\xcd\x0f")
    if idx < 0:
        return None
    zlen, rawlen = struct.unpack_from("<HH", buf, idx + 2)
    payload = buf[idx + 6: idx + 6 + zlen]
    if payload[:2] not in (b"\x78\x9c", b"\x78\x01", b"\x78\xda"):
        return {"zlen": zlen, "rawlen": rawlen, "bars": None,
                "head": payload[:16].hex(" ")}
    raw = zlib.decompress(payload)
    return {"zlen": zlen, "rawlen": rawlen, "bars": parse_bars(raw),
            "head": raw[:6].hex(" ")}


def main() -> int:
    probes = [
        (0x01352764, 0x01352779, "captured baseline"),
        (0x01352764, 0x01352766, "short span"),
        (0x01352770, 0x01352779, "late sub-window"),
        (0x01352700, 0x01352779, "wider start"),
        (0x01352000, 0x01352779, "much wider"),
        (0x01352800, 0x01352900, "beyond head"),
        (0x01352890, 0x01352897, "near server-now"),
    ]
    s = socket.create_connection((HOST, PORT), timeout=8)
    s.sendall(HELLO); drain(s)
    s.sendall(OP13); drain(s)
    s.sendall(OP4059); drain(s)
    for c1, c2, note in probes:
        r = probe(s, c1, c2)
        if r is None:
            print(f"0x{c1:08x}..0x{c2:08x} [{note}]: NO RESPONSE")
            continue
        if r["bars"] is None:
            print(f"0x{c1:08x}..0x{c2:08x} [{note}]: status frame "
                  f"z={r['zlen']} raw={r['rawlen']} head={r['head']}")
            continue
        bars = r["bars"]
        marks = sorted({b[0] for b in bars})
        print(f"0x{c1:08x}..0x{c2:08x} [{note}]: {len(bars)} bars, "
              f"days {marks[0]:#x}..{marks[-1]:#x} ({len(marks)} days), "
              f"t {bars[0][1]}..{bars[-1][1]} C0={bars[0][2]:.2f} "
              f"Cl={bars[-1][2]:.2f}")
    s.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
