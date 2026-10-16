#!/usr/bin/env python3
"""1016 lab · sweep2.py — opcode/flag sweep with auto-reconnect.

Server resets on invalid opcode; reconnect + re-handshake for each probe.
Phase 1: flag 0x30..0x3f with op 4045. Phase 2: ops 0x0FC0..0x0FE0 (skip CD).
Classify responses by bars/day: 240 => 1-min.
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
PAYLOAD = (b"\x00\x00" + b"000001"
           + struct.pack("<II", 0x01352774, 0x01352779) + b"\x00\x00")


class Conn:
    def __init__(self):
        self.s = socket.create_connection((HOST, PORT), timeout=8)
        self.s.sendall(HELLO); self.drain()
        self.s.sendall(OP13); self.drain()
        self.s.sendall(OP4059); self.drain()

    def drain(self, settle=0.6):
        self.s.settimeout(settle)
        buf = b""
        try:
            while True:
                c = self.s.recv(65536)
                if not c:
                    break
                buf += c
        except socket.timeout:
            pass
        except OSError:
            pass
        return buf

    def probe(self, flag, op):
        ln = len(PAYLOAD)
        self.s.sendall(bytes([0x0C, 0x01, flag, 0x8D, 0x00, 0x01])
                       + struct.pack("<HH", ln, ln) + struct.pack("<H", op)
                       + PAYLOAD)
        return self.drain(1.0)

    def close(self):
        try:
            self.s.close()
        except OSError:
            pass


def classify(buf):
    idx = buf.find(b"\xcd\x0f")
    if idx >= 0:
        zlen, rawlen = struct.unpack_from("<HH", buf, idx + 2)
        payload = buf[idx + 6: idx + 6 + zlen]
        if payload[:2] in (b"\x78\x9c", b"\x78\x01", b"\x78\xda"):
            try:
                raw = zlib.decompress(payload)
            except zlib.error:
                return None
            bars = []
            for o in range(6, len(raw) - 31, 32):
                mark, tmin = struct.unpack_from("<HH", raw, o)
                bars.append((mark, tmin))
            if bars:
                days = {}
                for mark, t in bars:
                    days.setdefault(mark, set()).add(t)
                pd = round(len(bars) / max(len(days), 1))
                tt = sorted({t for _, t in bars})
                return (len(bars), len(days), pd, tt[0], tt[-1])
        return None
    # non-4045 echo: any framed response?
    m = buf.find(bytes.fromhex("b1 cb 74 00"))
    if m >= 0 and len(buf) > m + 16:
        op, = struct.unpack_from("<H", buf, m + 10)
        zlen, rawlen = struct.unpack_from("<HH", buf, m + 12)
        return f"echo-op-0x{op:04x} z={zlen} raw={rawlen}"
    return None


def main() -> int:
    c = Conn()
    print("=== phase 1: flag sweep on op 4045 ===")
    for flag in range(0x30, 0x40):
        try:
            r = c.probe(flag, 0x0FCD)
        except OSError:
            c = Conn()
            continue
        res = classify(r)
        if res:
            print(f"flag 0x{flag:02x}: {res}")
        if not isinstance(res, str) and res and res[2] >= 200:
            print(f"*** 1-MIN via flag 0x{flag:02x}")
    c.close()

    print("=== phase 2: opcode sweep (flag 0x38) ===")
    for op in range(0x0FC0, 0x0FE0):
        if op == 0x0FCD:
            continue
        c = Conn()
        try:
            r = c.probe(0x38, op)
        except OSError as e:
            print(f"op 0x{op:04x}: conn error {e}")
            c.close()
            continue
        res = classify(r)
        c.close()
        if res:
            print(f"op 0x{op:04x}: {res}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
