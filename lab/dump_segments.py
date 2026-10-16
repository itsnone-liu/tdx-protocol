#!/usr/bin/env python3
"""1016 lab · dump_segments.py — hex-dump every TCP segment (event) of one direction."""
import json
import re
import sys
from pathlib import Path


def asc(b: bytes) -> str:
    return re.sub(rb"[^\x20-\x7e]", b".", b).decode()


def main() -> int:
    bin_path, ev_path = Path(sys.argv[1]), Path(sys.argv[2])
    direction = "c2s" if "_c2s" in bin_path.name else "s2c"
    max_show = int(sys.argv[4]) if len(sys.argv) > 4 else 48
    data = bin_path.read_bytes()
    events = [json.loads(x) for x in ev_path.read_text(encoding="utf-8").splitlines()
              if x.strip() and json.loads(x)["dir"] == direction]
    shown = 0
    for e in events:
        off, ln, t = e["off"], e["len"], e["t_ms"]
        seg = data[off:off + ln]
        hx = seg[:64].hex(" ")
        line = f"t={t:>7} off={off:7d} len={ln:5d} | {hx}"
        if ln > 64:
            line += " ..."
        print(line)
        frag = "".join(c for c in asc(seg) if c != ".")
        if len(frag) >= 3:
            print(f"{'':>28}ascii: {frag[:90]}")
        shown += 1
        if shown >= max_show:
            print(f"... ({len(events)} events total)")
            break
    return 0


if __name__ == "__main__":
    sys.exit(main())
