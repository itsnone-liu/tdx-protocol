#!/usr/bin/env python3
"""1016 lab · fetch_chunk.py — replay/forge op1721 chunked file fetch.

First: byte-exact replay of the captured 320B 1721 frame (specetfdata.txt).
Second: forged 1721 for bi/bigdata_1.zip at offset 0 (30000B chunk).
"""
import socket
import struct
import sys
import time
from pathlib import Path

HOST, PORT = "175.178.112.197", 7709
HELLO = bytes.fromhex("00 00 00 00 00 00 10 00 10 00 52 04 00 00 00 00"
                      "d0 07 00 00 00 00 00 00 00 00")
OP13 = bytes.fromhex("0c 02 18 94 00 01 03 00 03 00 0d 00 01")
OP4059 = bytes.fromhex("0c 03 18 99 00 01 20 00 20 00 db 0f"
                       "74 64 78 6c 65 76 65 6c 00 00 00 29 5c f7 40 11"
                       "00 00 00 00 00 00 00 00 00 00 00 00 00 05")
CAP = Path(__file__).resolve().parent / "out" / "rec_20261015T235945Z" / "c3_c2s.bin"


def drain(sock, settle=3.0, cap=8_000_000):
    sock.settimeout(settle)
    buf = b""
    idle = 0
    while len(buf) < cap:
        try:
            c = sock.recv(262144)
            if not c:
                break
            buf += c
            idle = 0
        except socket.timeout:
            idle += 1
            if idle >= 2 or len(buf) > 0:
                break
    return buf


def forge1721(fname: bytes, offset: int, chunk: int) -> bytes:
    # captured layout: 00×6 | len | len | 0x06B9 | offset:u32 | chunk:u32 | fname pad→300
    padded = fname + b"\x00" * (300 - len(fname))
    body = struct.pack("<HIII", 0x06B9, offset, chunk, 0)[:10] + b""
    body = struct.pack("<HI", 0x06B9, offset) + struct.pack("<I", chunk) + padded
    ln = len(body)
    return b"\x00" * 6 + struct.pack("<HH", ln, ln) + body


def main() -> int:
    cap = CAP.read_bytes()
    frame_1721 = cap[338:338 + 320]  # exact captured chunk request
    print(f"captured 1721 frame ({len(frame_1721)}B): {frame_1721[:28].hex(' ')}")

    for tag, req in [
        ("replay-captured-1721", frame_1721),
        ("forge bigdata_1 off0", forge1721(b"bi/bigdata_1.zip", 0, 30000)),
        ("forge zd off0", forge1721(b"zd.zip", 0, 30000)),
    ]:
        s = socket.create_connection((HOST, PORT), timeout=8)
        s.sendall(HELLO); drain(s, 1.0)
        s.sendall(OP13); drain(s, 1.0)
        s.sendall(OP4059); drain(s, 1.0)
        s.sendall(req)
        t0 = time.time()
        buf = drain(s, 4.0)
        print(f"\n[{tag}] {len(buf)}B in {time.time()-t0:.1f}s")
        if buf:
            print(f"  head: {buf[:48].hex(' ')}")
            pk = buf.find(b"PK")
            if 0 <= pk <= 64:
                print("  => ZIP payload!")
                out = Path(__file__).resolve().parent / "out" / f"e3_{tag.replace(' ', '_')}.zip"
                out.write_bytes(buf[pk:])
                print(f"  saved {len(buf)-pk}B -> {out}")
        s.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
