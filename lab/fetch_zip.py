#!/usr/bin/env python3
"""1016 lab · fetch_zip.py — replay captured op709 file requests (bigdata zips)
and save whatever the server returns. Checks PK zip magic / zlib."""
import socket
import struct
import sys
import time
import zipfile
import zlib
from io import BytesIO
from pathlib import Path

HOST, PORT = "175.178.112.197", 7709
HELLO = bytes.fromhex("00 00 00 00 00 00 10 00 10 00 52 04 00 00 00 00"
                      "d0 07 00 00 00 00 00 00 00 00")
OP13 = bytes.fromhex("0c 02 18 94 00 01 03 00 03 00 0d 00 01")
OP4059 = bytes.fromhex("0c 03 18 99 00 01 20 00 20 00 db 0f"
                       "74 64 78 6c 65 76 65 6c 00 00 00 29 5c f7 40 11"
                       "00 00 00 00 00 00 00 00 00 00 00 00 00 05")


def op709(fname: bytes) -> bytes:
    payload = fname + b"\x00" * (42 - len(fname))
    ln = len(payload)
    return (bytes([0x0C, 0x07, 0x18, 0x69, 0x00, 0x01])
            + struct.pack("<HH", ln, ln) + struct.pack("<H", 0x02C5) + payload)


def drain(sock, settle=3.0, cap=64_000_000):
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


def main() -> int:
    targets = sys.argv[1:] or ["bi/bigdata_1.zip", "zd.zip", "zhb.zip"]
    outdir = Path(__file__).resolve().parent / "out"
    for fname in targets:
        s = socket.create_connection((HOST, PORT), timeout=8)
        s.sendall(HELLO); drain(s, 1.0)
        s.sendall(OP13); drain(s, 1.0)
        s.sendall(OP4059); drain(s, 1.0)
        req = op709(fname.encode())
        s.sendall(req)
        t0 = time.time()
        buf = drain(s, 4.0)
        dt = time.time() - t0
        print(f"\n[{fname}] {len(buf)}B in {dt:.1f}s")
        if buf:
            print(f"  head: {buf[:32].hex(' ')}")
            m = buf.find(bytes.fromhex("b1 cb 74 00"))
            if m >= 0:
                op, = struct.unpack_from("<H", buf, m + 10)
                zlen, rawlen = struct.unpack_from("<HH", buf, m + 12)
                print(f"  frame@{m}: op=0x{op:04x} zlen={zlen} rawlen={rawlen}")
                payload = buf[m + 16: m + 16 + zlen]
                print(f"  payload head: {payload[:16].hex(' ')}")
                if payload[:2] == b"PK":
                    out = outdir / f"e3_{fname.replace('/', '_')}"
                    out.write_bytes(payload)
                    print(f"  ZIP! saved {len(payload)}B -> {out}")
                    try:
                        z = zipfile.ZipFile(BytesIO(payload))
                        names = z.namelist()[:10]
                        print(f"  entries({len(z.namelist())}): {names}")
                    except Exception as e:  # noqa: BLE001
                        print(f"  zip parse: {e}")
                elif payload[:2] in (b"\x78\x9c", b"\x78\x01", b"\x78\xda"):
                    try:
                        raw = zlib.decompress(payload)
                        print(f"  zlib -> {len(raw)}B; head {raw[:24].hex(' ')}")
                        asc = raw[:120]
                        print(f"  ascii: {asc}")
                    except zlib.error as e:
                        print(f"  zlib fail: {e}")
        s.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
