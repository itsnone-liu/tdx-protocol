#!/usr/bin/env python3
"""1016 lab · opcode_sweep.py — find granularity by opcode/flag byte sweep."""
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


def drain(sock, settle=0.8):
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


def frame(flag, op, payload):
    ln = len(payload)
    return (bytes([0x0C, 0x01, flag, 0x8D, 0x00, 0x01])
            + struct.pack("<HH", ln, ln) + struct.pack("<H", op) + payload)


PAYLOAD = (b"\x00\x00" + b"000001"
           + struct.pack("<II", 0x01352774, 0x01352779) + b"\x00\x00")


def bars_of(buf):
    idx = buf.find(b"\xcd\x0f")
    if idx < 0:
        return None, buf[:20]
    zlen, rawlen = struct.unpack_from("<HH", buf, idx + 2)
    payload = buf[idx + 6: idx + 6 + zlen]
    if payload[:2] not in (b"\x78\x9c", b"\x78\x01", b"\x78\xda"):
        return [], payload[:12].hex(" ")
    raw = zlib.decompress(payload)
    out = []
    for off in range(6, len(raw) - 31, 32):
        mark, tmin = struct.unpack_from("<HH", raw, off)
        out.append((mark, tmin))
    return out, raw[:6].hex(" ")


def main() -> int:
    s = socket.create_connection((HOST, PORT), timeout=8)
    s.sendall(HELLO); drain(s)
    s.sendall(OP13); drain(s)
    s.sendall(OP4059); drain(s)

    print("=== opcode sweep (flag 0x38) ===")
    for op in range(0x0FC0, 0x0FE0):
        if op == 0x0FC8:
            continue
        s.sendall(frame(0x38, op, PAYLOAD))
        buf = drain(s)
        bars, note = bars_of(buf) if b"\xcd\x0f" in buf else (None, buf[:20].hex(" ") if buf else "timeout")
        if bars is None:
            continue  # no echo => not this op; skip quietly
        if not bars:
            print(f"op 0x{op:04x}: status/payload {note}")
            continue
        days = {}
        for mark, t in bars:
            days.setdefault(mark, set()).add(t)
        per_day = len(bars) // max(len(days), 1)
        tt = sorted({t for _, t in bars})
        print(f"op 0x{op:04x}: {len(bars)} bars / {len(days)}d = {per_day}/day "
              f"t {tt[0]}..{tt[-1]}")
    s.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
