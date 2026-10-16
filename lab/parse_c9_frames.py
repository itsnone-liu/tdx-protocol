#!/usr/bin/env python3
"""Walk c9 client stream by declared envelope length and dump first N frames."""
import struct,sys
from collections import Counter
from pathlib import Path
p=Path(sys.argv[1]);limit=int(sys.argv[2]) if len(sys.argv)>2 else 80;b=p.read_bytes();o=0;frames=[]
while o+12<=len(b):
 if b[o]!=0x0c:
  # old zero-prefixed frame or resync
  n=b.find(b'\x0c',o+1)
  if n<0:break
  o=n;continue
 ln=struct.unpack_from('<H',b,o+6)[0]
 total=10+ln
 if ln<2 or o+total>len(b):
  print('bad at',o,'ln',ln);o+=1;continue
 op=struct.unpack_from('<H',b,o+10)[0]
 frames.append((o,total,b[o+1],b[o+2],op,b[o+12:o+total]))
 o+=total
print('parsed',len(frames),'remaining',len(b)-o,'bytes',len(b),'ops',Counter(x[4] for x in frames))
for j,(off,total,seq,flag,op,pay) in enumerate(frames[:limit]):
 text=''.join(chr(x) if 32<=x<127 else '.' for x in pay[:100])
 print(f'#{j:04} off={off:6} n={total:5} seq={seq:02x} flag={flag:02x} op={op:04x} payload={len(pay):4} {pay[:48].hex(" ")} |{text}')
