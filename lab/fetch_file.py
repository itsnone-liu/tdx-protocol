#!/usr/bin/env python3
"""1016 lab · fetch_file.py — full chunked file fetch via op1721, assemble, unzip.

Usage: python fetch_file.py <remote-name> <local-out>
"""
import socket
import struct
import sys
import time
import zipfile
import zlib
from pathlib import Path

HOST, PORT = "175.178.112.197", 7709
HELLO = bytes.fromhex("00 00 00 00 00 00 10 00 10 00 52 04 00 00 00 00"
                      "d0 07 00 00 00 00 00 00 00 00")
OP13 = bytes.fromhex("0c 02 18 94 00 01 03 00 03 00 0d 00 01")
OP4059 = bytes.fromhex("0c 03 18 99 00 01 20 00 20 00 db 0f"
                       "74 64 78 6c 65 76 65 6c 00 00 00 29 5c f7 40 11"
                       "00 00 00 00 00 00 00 00 00 00 00 00 00 05")
CHUNK = 30000


def drain(sock, settle=2.5, cap=8_000_000):
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
    padded = fname + b"\x00" * (300 - len(fname))
    body = struct.pack("<HI", 0x06B9, offset) + struct.pack("<I", chunk) + padded
    ln = len(body)
    return b"\x00" * 6 + struct.pack("<HH", ln, ln) + body


def parse1721resp(buf: bytes, offset: int = -1):
    """return raw payload bytes of one 1721 response, or None."""
    m = buf.find(bytes.fromhex("b1 cb 74 00"))
    if m < 0:
        return None
    op, = struct.unpack_from("<H", buf, m + 10)
    if op != 0x06B9:
        return None
    zlen, rawlen = struct.unpack_from("<HH", buf, m + 12)
    payload = buf[m + 16: m + 16 + zlen]
    if zlen != rawlen and payload[:2] in (b"\x78\x9c", b"\x78\x01", b"\x78\xda"):
        try:
            payload = zlib.decompress(payload)
        except zlib.error:
            pass
    # payload begins with <this-chunk byte count u32> echo; strip it
    if len(payload) >= 4 and payload[:4] == struct.pack("<I", CHUNK):
        payload = payload[4:]
    return payload


def main() -> int:
    fname = sys.argv[1].encode()
    out = Path(sys.argv[2])
    s = socket.create_connection((HOST, PORT), timeout=8)
    s.sendall(HELLO); drain(s, 1.0)
    s.sendall(OP13); drain(s, 1.0)
    s.sendall(OP4059); drain(s, 1.0)
    blob = b""
    off = 0
    t0 = time.time()
    while True:
        s.sendall(forge1721(fname, off, CHUNK))
        buf = drain(s)
        piece = parse1721resp(buf, off)
        if not piece:
            print(f"chunk@{off}: no payload (stop)")
            break
        blob += piece
        print(f"chunk@{off}: +{len(piece)}B (total {len(blob)}B, "
              f"{time.time()-t0:.1f}s)")
        if len(piece) < CHUNK:
            break
        off += CHUNK
    s.close()
    out.write_bytes(blob)
    print(f"saved {len(blob)}B -> {out}")
    if blob[:2] == b"PK":
        try:
            z = zipfile.ZipFile(out)
            for i in z.infolist()[:20]:
                print(f"  {i.filename} {i.file_size}B")
            print(f"  total entries: {len(z.infolist())}")
        except Exception as e:  # noqa: BLE001
            print(f"zip parse: {e}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
