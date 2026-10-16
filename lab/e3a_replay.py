#!/usr/bin/env python3
"""1016 lab · e3a_replay.py — E3a: guest direct-pull validation.

Fresh TCP to a TDX 7709 host. Send captured hello (26B) then ONE captured
op4045 cursor request (30B, stock 399001). If the server answers with a zlib
K-line payload, minute-data pull needs NO account login -> Ubuntu CLI viable.

No ticket (op11) is sent. This tests the weakest-privilege path.
"""
import socket
import sys
import zlib
from pathlib import Path

HOST = "175.178.112.197"
PORT = 7709
REC = Path(__file__).resolve().parent / "out" / "rec_20261015T235945Z"

HELLO = bytes.fromhex(
    "00 00 00 00 00 00 10 00 10 00 52 04 00 00 00 00"
    "d0 07 00 00 00 00 00 00 00 00")
REQ_4045 = bytes.fromhex(
    "0c 01 38 8d 00 01 14 00 14 00 cd 0f"
    "00 00 33 39 39 30 30 31 64 27 35 01 79 27 35 01 00 00")


def recv_frame(sock, tag, want=8, timeout=8.0):
    sock.settimeout(timeout)
    try:
        head = sock.recv(want)
    except socket.timeout:
        print(f"[{tag}] timeout (no response)")
        return None
    if not head:
        print(f"[{tag}] connection closed by server")
        return None
    print(f"[{tag}] got {len(head)}B head: {head.hex(' ')}")
    return head


def main() -> int:
    print(f"connecting {HOST}:{PORT} ...")
    s = socket.create_connection((HOST, PORT), timeout=8)
    print("connected")

    s.sendall(HELLO)
    print("hello sent (26B)")
    r1 = recv_frame(s, "hello-resp")
    if r1 is None:
        return 1
    # drain rest of negotiate
    s.settimeout(2.0)
    try:
        rest = s.recv(65536)
        print(f"[hello-resp] +{len(rest)}B (total head+rest), zlib@?: "
              f"{rest[:2].hex() if len(rest) >= 2 else '?'}")
    except socket.timeout:
        print("[hello-resp] no extra bytes")

    s.sendall(REQ_4045)
    print("op4045 sent (30B, 399001 cursor 0x01352764..0x01352779)")
    s.settimeout(8.0)
    buf = b""
    try:
        while True:
            chunk = s.recv(65536)
            if not chunk:
                break
            buf += chunk
            if len(buf) > 40000:
                break
    except socket.timeout:
        pass
    print(f"[4045-resp] {len(buf)}B")
    if not buf:
        print("=> E3a NEGATIVE: server ignored guest op4045")
        return 2
    print(f"[4045-resp] head: {buf[:24].hex(' ')}")
    # find opcode echo CD 0F and following lengths
    idx = buf.find(b"\xcd\x0f")
    if idx < 0:
        print("=> no op echo found; full hex head only")
        return 3
    import struct
    z_len, raw_len = struct.unpack_from("<HH", buf, idx + 2)
    print(f"[4045-resp] z_len={z_len} raw_len={raw_len}")
    payload = buf[idx + 6: idx + 6 + z_len]
    if payload[:2] in (b"\x78\x9c", b"\x78\x01", b"\x78\xda"):
        try:
            raw = zlib.decompress(payload)
            print(f"=> E3a POSITIVE: zlib K-line payload {len(raw)}B!")
            print(f"   first 64B: {raw[:64].hex(' ')}")
            out = Path(__file__).resolve().parent / "out" / "e3a_4045_payload.bin"
            out.write_bytes(raw)
            print(f"   saved -> {out}")
            return 0
        except zlib.error as e:
            print(f"zlib failed (partial frame?): {e}; need full {z_len}B")
            print("=> likely POSITIVE but truncated read; rerun with longer drain")
            return 4
    print("payload not zlib-prefixed at expected offset")
    return 5


if __name__ == "__main__":
    sys.exit(main())
