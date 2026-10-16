#!/usr/bin/env python3
"""Parse legacy TDX frames: 6-byte prefix + u16 len*2 + u16 opcode + payload."""
import struct
import sys
from collections import Counter
from pathlib import Path

p = Path(sys.argv[1])
data = p.read_bytes()
off = 0
frames = []
while off + 12 <= len(data):
    # old style header has 6 zero bytes
    if data[off:off+6] != b"\x00"*6:
        nxt = data.find(b"\x00"*6, off+1)
        if nxt < 0: break
        off = nxt
        continue
    ln1, ln2, op = struct.unpack_from("<HHH", data, off+6)
    if ln1 != ln2 or off + 12 + ln1 > len(data):
        off += 1
        continue
    frames.append((off, ln1, op, data[off+12:off+12+ln1]))
    off += 12 + ln1
print(f"{p.name}: {len(data)}B, parsed {len(frames)} frames")
for op,n in Counter(f[2] for f in frames).most_common():
    lens=[f[1] for f in frames if f[2]==op]
    print(f"op 0x{op:04x}({op}) x{n} payload {min(lens)}..{max(lens)}")
for i,(off,ln,op,pay) in enumerate(frames[:80]):
    ascii=''.join(chr(b) if 32<=b<127 else '.' for b in pay[:100])
    print(f"#{i:03d} off={off} op={op:04x} len={ln} head={pay[:32].hex(' ')} ascii={ascii}")
