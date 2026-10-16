#!/usr/bin/env python3
"""1016 lab · frame_stats.py — opcode/size histogram + largest frames + zlib probe.

Assumes envelope: 0c <seq8> <f8> <u16> <u16 len> <u16 len> <u16 op> <payload...>
Frames are reassembled from events (direction-filtered), since TCP segments
may split/join frames: we rebuild the byte stream and walk it.
"""
import json
import re
import sys
import zlib
from collections import Counter
from pathlib import Path


def asc(b: bytes) -> str:
    return re.sub(rb"[^\x20-\x7e]", b".", b).decode()


def reassemble(bin_path: Path, ev_path: Path, direction: str) -> bytes:
    data = bin_path.read_bytes()
    events = [json.loads(x) for x in ev_path.read_text(encoding="utf-8").splitlines()
              if x.strip()]
    events = [e for e in events if e["dir"] == direction]
    events.sort(key=lambda e: e["off"])
    out = bytearray()
    for e in events:
        out += data[e["off"]:e["off"] + e["len"]]
    return bytes(out)


def walk(data: bytes):
    frames = []
    off = 0
    n = len(data)
    while off + 13 <= n:
        if data[off] != 0x0C:
            # resync: scan for next 0c with plausible len
            nxt = data.find(b"\x0c", off + 1)
            if nxt < 0:
                frames.append((off, n - off, None, "NOSYNC"))
                break
            frames.append((off, nxt - off, None, "SKIP"))
            off = nxt
            continue
        ln = int.from_bytes(data[off + 6:off + 8], "little")
        if ln < 2 or off + 10 + ln > n:
            frames.append((off, n - off, None, "TRUNC"))
            break
        op = int.from_bytes(data[off + 10:off + 12], "little")
        frames.append((off, 10 + ln, op, data[off + 2]))
        off += 10 + ln
    return frames


def main() -> int:
    d = Path(sys.argv[1])
    for conn in ("c2", "c3"):
        for direction in ("c2s", "s2c"):
            stream = reassemble(d / f"{conn}_{direction}.bin", d / f"{conn}_events.jsonl", direction)
            frames = walk(stream)
            ok = [f for f in frames if f[2] is not None]
            bad = [f for f in frames if f[2] is None]
            print(f"\n===== {conn}_{direction}: {len(stream)}B, {len(frames)} frames "
                  f"({len(ok)} ok / {len(bad)} bad) =====")
            ops = Counter(f[2] for f in ok)
            for op, cnt in ops.most_common(12):
                lens = sorted(f[1] for f in ok if f[2] == op)
                print(f"  op=0x{op:04x}({op:5d}) x{cnt:4d}  len {lens[0]}..{lens[-1]}"
                      f" (median {lens[len(lens)//2]})")
            big = sorted(ok, key=lambda f: -f[1])[:3]
            for off, ln, op, fl in big:
                payload = stream[off + 10:off + ln]
                print(f"  BIG op=0x{op:04x} len={ln} flag=0x{fl:02x} head: {payload[:48].hex(' ')}")
                fr = "".join(c for c in asc(payload[:200]) if c != ".")
                if len(fr) >= 3:
                    print(f"       ascii: {fr[:110]}")
            # zlib probe on s2c payload starts
            if direction == "s2c":
                z = sum(1 for f in ok[:50]
                        if stream[f[0] + 10:f[0] + 12] in (b"\x78\x9c", b"\x78\x01", b"\x78\xda"))
                print(f"  zlib-header frames in first 50: {z}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
