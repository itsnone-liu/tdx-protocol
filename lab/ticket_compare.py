#!/usr/bin/env python3
"""Compare op11 frames in captures and optionally extract their final 8 bytes."""
from pathlib import Path
D=Path(__file__).resolve().parent/'out'/'rec_20261015T235945Z'
for c in ['c2','c9','c13']:
 p=D/f'{c}_c2s.bin'
 if not p.exists():continue
 b=p.read_bytes()
 if len(b)<292 or b[:12]!=bytes.fromhex('0c 01 18 7b 00 01 1a 01 1a 01 0b 00'):continue
 f=b[:292]
 print(f'{c}: ticket[0:280]={f[12:284].hex()}')
 print(f'{c}: final8={f[284:292].hex(" ")}')
