#!/usr/bin/env python3
"""1016 prototype/testing harness for TDX 7709 1-minute K-line CLI.

Portable Python stdlib only. The 1m request/bar layout is validated against
captured TDXW 7.73 traffic and local .lc1 files. This independent live CLI is
NOT yet working: current attempts receive a 6-byte status response, likely
because some live session state is missing. It currently replays the captured
setup prefix and uses a known cursor window; do not treat it as successful
unauthenticated retrieval. Example:
  python tdx_min_cli.py 000001 000002 000006 ... --out bars.csv
"""
import argparse
import csv
import socket
import struct
import zlib
from pathlib import Path

HOST_DEFAULT = "175.178.112.197"
PORT_DEFAULT = 7709
CURSOR_START = 0x01352764
CURSOR_END = 0x01352769
PERIOD_1M = 0x0007

HELLO = bytes.fromhex(
    "00 00 00 00 00 00 10 00 10 00 52 04 00 00 00 00"
    "d0 07 00 00 00 00 00 00 00 00")
OP13 = bytes.fromhex("0c 02 18 94 00 01 03 00 03 00 0d 00 01")
OP4059 = bytes.fromhex(
    "0c 03 18 99 00 01 20 00 20 00 db 0f"
    "74 64 78 6c 65 76 65 6c 00 00 00 29 5c f7 40 11"
    "00 00 00 00 00 00 00 00 00 00 00 00 00 05")


def recv_exact(sock: socket.socket, n: int) -> bytes:
    out = bytearray()
    while len(out) < n:
        chunk = sock.recv(n - len(out))
        if not chunk:
            raise ConnectionError(f"peer closed with {n-len(out)} bytes outstanding")
        out.extend(chunk)
    return bytes(out)


def recv_response(sock: socket.socket) -> tuple[bytes, bytes]:
    """Read response header (16B) and declared compressed/raw payload."""
    hdr = recv_exact(sock, 16)
    zlen, rawlen = struct.unpack_from("<HH", hdr, 12)
    payload = recv_exact(sock, zlen)
    if len(payload) >= 2 and payload[:2] in (b"\x78\x9c", b"\x78\x01", b"\x78\xda"):
        try:
            return hdr, zlib.decompress(payload)
        except zlib.error:
            pass
    return hdr, payload


def request_1m(seq: int, code: str, c1: int, c2: int) -> bytes:
    if len(code) != 6 or not code.isdigit():
        raise ValueError(f"stock code must be six digits: {code!r}")
    # Length fields (0x14) count opcode(2)+18-byte operation payload.
    return (bytes((0x0C, seq & 0xFF, 0x38, 0x8E, 0x00, 0x01))
            + struct.pack("<HHH", 0x14, 0x14, 0x0FCD)
            + b"\x00\x00" + code.encode("ascii")
            + struct.pack("<IIH", c1, c2, PERIOD_1M))


def parse_bars(raw: bytes):
    if len(raw) < 6 or (len(raw) - 6) % 32:
        raise ValueError(f"unexpected raw K-line payload length {len(raw)}")
    bars = []
    for off in range(6, len(raw), 32):
        day, minute = struct.unpack_from("<HH", raw, off)
        opn, high, low, close, amount = struct.unpack_from("<5f", raw, off + 4)
        volume, reserved = struct.unpack_from("<II", raw, off + 24)
        bars.append({"day_marker": day, "minute": minute,
                     "open": opn, "high": high, "low": low,
                     "close": close, "amount": amount,
                     "volume": volume, "reserved": reserved})
    return bars


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("codes", nargs="+", help="six-digit stock codes, e.g. 000001 600519")
    ap.add_argument("--host", default=HOST_DEFAULT)
    ap.add_argument("--port", type=int, default=PORT_DEFAULT)
    ap.add_argument("--cursor-start", type=lambda x: int(x, 0), default=CURSOR_START)
    ap.add_argument("--cursor-end", type=lambda x: int(x, 0), default=CURSOR_END)
    ap.add_argument("--out", default="tdx_1m.csv")
    args = ap.parse_args()

    rows = []
    with socket.create_connection((args.host, args.port), timeout=10) as s:
        s.settimeout(15)
        # Replay the recorded c9 session's exact prelude as an experimental
        # protocol reconstruction. The ticket and op44d/op44e exchanges are
        # copied from an older capture; this is not fresh-session auth proof.
        cap_path = Path(__file__).resolve().parent / "out" / "rec_20261015T235945Z" / "c9_c2s.bin"
        if not cap_path.exists():
            raise FileNotFoundError(f"missing captured setup reference: {cap_path}")
        cap = cap_path.read_bytes()
        prelude = []
        off = 0
        while off < 3035:
            if cap[off] != 0x0C:
                raise ValueError(f"bad captured frame at {off}")
            frame_len = 10 + struct.unpack_from("<H", cap, off + 6)[0]
            if frame_len < 12 or off + frame_len > 3035:
                raise ValueError(f"bad captured frame length at {off}")
            prelude.append(cap[off:off + frame_len])
            off += frame_len
        for frame in prelude:
            s.sendall(frame)
            recv_response(s)
        print(f"replayed {len(prelude)} static old 1m prelude frames (negative-baseline only)")
        # The capture's first op4045 seq is in the first request frame.
        seq = cap[off + 1]
        for code in args.codes:
            s.sendall(request_1m(seq, code, args.cursor_start, args.cursor_end))
            h, body = recv_response(s)
            op = struct.unpack_from("<H", h, 10)[0]
            rseq = h[5]
            if op != 0x0FCD or rseq != (seq & 0xFF):
                raise RuntimeError(f"response mismatch code={code} op=0x{op:04x} seq={rseq}")
            bars = parse_bars(body) if len(body) > 6 else []
            if not bars:
                print(f"{code}: empty/status response; header={h.hex(' ')} body={body[:32].hex(' ')}")
                seq = (seq + 1) & 0xFF
                continue
            print(f"{code}: {len(bars)} bars, day markers {bars[0]['day_marker']}..{bars[-1]['day_marker']}")
            for bar in bars:
                rows.append({"code": code, **bar})
            seq = (seq + 1) & 0xFF

    out = Path(args.out)
    with out.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["code", "day_marker", "minute", "open", "high", "low", "close", "amount", "volume", "reserved"])
        w.writeheader(); w.writerows(rows)
    print(f"saved {len(rows)} bars for {len(args.codes)} stocks -> {out.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
