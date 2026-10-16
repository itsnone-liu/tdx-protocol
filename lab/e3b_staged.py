#!/usr/bin/env python3
"""1016 lab · e3b_staged.py — staged replay: drain-then-send, original order.

Stages (exact captured bytes, c2/c3):
  1. hello (26B, from c3)            -> drain
  2. op13 capability (13B, c2)       -> drain
  3. op4059 tdxlevel (42B, c2)       -> drain
  4. op4045 399001 cursor (30B, c2)  -> drain
Prints each response; searches buffers for frame magic B1CB7400 and CD0F echo.
"""
import socket
import struct
import sys
import zlib
from pathlib import Path

HOST = "175.178.112.197"
PORT = 7709

def frame4045(code: bytes, cur1: int, cur2: int) -> bytes:
    return (b"\x0c\x01\x38\x8d\x00\x01\x14\x00\x14\x00\xcd\x0f\x00\x00"
            + code + struct.pack("<II", cur1, cur2) + b"\x00\x00")


CODE = (sys.argv[1] if len(sys.argv) > 1 else "399001").encode()
C1 = int(sys.argv[2], 0) if len(sys.argv) > 2 else 0x01352764
C2 = int(sys.argv[3], 0) if len(sys.argv) > 3 else 0x01352779

STAGES = [
    ("hello", bytes.fromhex(
        "00 00 00 00 00 00 10 00 10 00 52 04 00 00 00 00"
        "d0 07 00 00 00 00 00 00 00 00")),
    ("op13-cap", bytes.fromhex(
        "0c 02 18 94 00 01 03 00 03 00 0d 00 01")),
    ("op4059-tdxlevel", bytes.fromhex(
        "0c 03 18 99 00 01 20 00 20 00 db 0f"
        "74 64 78 6c 65 76 65 6c 00 00 00 29 5c f7 40 11"
        "00 00 00 00 00 00 00 00 00 00 00 00 00 05")),
    (f"op4045-{CODE.decode()}", frame4045(CODE, C1, C2)),
]

MAGIC = bytes.fromhex("b1 cb 74 00")


def drain(sock, settle=1.5, cap=2_000_000):
    sock.settimeout(settle)
    buf = b""
    try:
        while len(buf) < cap:
            chunk = sock.recv(65536)
            if not chunk:
                break
            buf += chunk
    except socket.timeout:
        pass
    return buf


def report(tag: str, buf: bytes):
    print(f"[{tag}] {len(buf)}B")
    if not buf:
        return
    print(f"  head: {buf[:32].hex(' ')}")
    pos = []
    off = buf.find(MAGIC)
    while off >= 0 and len(pos) < 8:
        pos.append(off)
        off = buf.find(MAGIC, off + 1)
    print(f"  magic B1CB7400 at: {pos}")
    cd = buf.find(b"\xcd\x0f")
    print(f"  CD0F at: {cd}")
    for off in pos:
        # layout: MAGIC[0:4] 0C[4] seq[5] flag[6] magic2[7:9] dir[9] op[10:12]
        #         zlen[12:14] rawlen[14:16] payload[16:]  (hello-resp lacks 0C
        #         but keeps zlen/rawlen at 12/14 with req-magic at 10)
        hdr = buf[off:off + 16]
        if len(hdr) < 16:
            continue
        seq, flag = hdr[5], hdr[6]
        op, = struct.unpack_from("<H", hdr, 10)
        zlen, rawlen = struct.unpack_from("<HH", hdr, 12)
        print(f"  @off {off}: 0C={hdr[4]:02x} seq={seq:02x} flag={flag:02x} "
              f"op=0x{op:04x} zlen={zlen} rawlen={rawlen}")
        payload = buf[off + 16: off + 16 + zlen]
        if payload[:2] in (b"\x78\x9c", b"\x78\x01", b"\x78\xda"):
            try:
                raw = zlib.decompress(payload)
                print(f"    => zlib OK, {len(raw)}B raw; first 48B: {raw[:48].hex(' ')}")
                outp = Path(__file__).resolve().parent / "out" / f"e3b_{tag.replace(' ', '_')}_{off}.bin"
                outp.write_bytes(raw)
                print(f"    saved {outp}")
            except zlib.error as e:
                print(f"    zlib partial: {e}")
        else:
            print(f"    payload head: {payload[:16].hex(' ')}")


def main() -> int:
    print(f"connect {HOST}:{PORT}")
    s = socket.create_connection((HOST, PORT), timeout=8)
    for tag, frame in STAGES:
        s.sendall(frame)
        print(f"sent [{tag}] {len(frame)}B")
        buf = drain(s)
        report(tag, buf)
    s.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
