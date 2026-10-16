#!/usr/bin/env python3
"""1016 lab · analyze_frames.py — frame-level dump of recproxy captures.

Walks a direction stream with u16le length-prefix framing (TDX HQ style),
validates the walk end-to-end, and prints a frame table with timing, hex head
and ASCII extraction. Falls back to raw segmentation by events when the prefix
walk fails.

Usage: python analyze_frames.py <bin> <events.jsonl> [--head N] [--prefix-walk]
"""
import json
import re
import sys
from pathlib import Path


def ascii_of(b: bytes) -> str:
    s = re.sub(rb"[^\x20-\x7e]", b".", b)
    return s.decode("ascii")


def walk_u16_prefix(data: bytes):
    """Yield (off, frame_len_including_prefix) if the whole stream walks cleanly."""
    frames = []
    off = 0
    n = len(data)
    while off < n:
        if off + 2 > n:
            return None
        ln = int.from_bytes(data[off:off + 2], "little")
        if ln < 2 or off + ln > n:
            return None
        frames.append((off, ln))
        off += ln
    return frames


def main() -> int:
    bin_path = Path(sys.argv[1])
    ev_path = Path(sys.argv[2])
    head = 80
    if "--head" in sys.argv:
        head = int(sys.argv[sys.argv.index("--head") + 1])
    data = bin_path.read_bytes()
    events = [json.loads(x) for x in ev_path.read_text(encoding="utf-8").splitlines() if x.strip()]
    t_of_off = {}
    for e in events:
        if e["dir"] == ("c2s" if "_c2s" in bin_path.name else "s2c"):
            t_of_off.setdefault(e["off"], e["t_ms"])

    print(f"file={bin_path.name} bytes={len(data)} events={len(events)}")
    frames = walk_u16_prefix(data)
    if frames:
        print(f"u16-prefix walk OK: {len(frames)} frames")
        show = frames if len(frames) <= head else frames[:head]
        for i, (off, ln) in enumerate(show):
            payload = data[off:off + ln]
            t = t_of_off.get(off, "?")
            hx = payload[:40].hex(" ")
            print(f"#{i:03d} off={off:6d} t={t:>7} len={ln:5d} | {hx}")
            asc = ascii_of(payload)
            frag = "".join(c for c in asc if c != ".")
            if len(frag) >= 3:
                print(f"      ascii: {frag[:100]}")
    else:
        print("u16-prefix walk FAILED; segment stats by length histogram of events")
        from collections import Counter
        c = Counter(e["len"] for e in events)
        for ln, cnt in c.most_common(20):
            print(f"  seg len={ln}: {cnt}x")
    return 0


if __name__ == "__main__":
    sys.exit(main())
