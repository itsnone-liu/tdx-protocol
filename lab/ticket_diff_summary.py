#!/usr/bin/env python3
"""Small, non-sensitive summary of c2/c9 op11 differences and response dates."""
from pathlib import Path
import struct
D=Path(__file__).resolve().parent/'out'/'rec_20261015T235945Z'
for side in ('c2','c9'):
 b=(D/f'{side}_c2s.bin').read_bytes(); f=b[:292]
 print(side,'ticket bytes',len(f),'payload280_sha_not_printed','final8',f[284:292].hex(' '))
 r=(D/f'{side}_s2c.bin').read_bytes(); i=r.find(bytes.fromhex('b1 cb 74 00 0c 01 18 7b'))
 if i>=0:
  z=struct.unpack_from('<H',r,i+12)[0]; p=r[i+16:i+16+z]
  print(side,'op11 server response length',len(p),'u32 offset 52..',struct.unpack_from('<I',p,52)[0], 'u16@56',struct.unpack_from('<H',p,56)[0], 'u32@58',hex(struct.unpack_from('<I',p,58)[0]))
a=(D/'c2_c2s.bin').read_bytes()[12:284]; b=(D/'c9_c2s.bin').read_bytes()[12:284]
print('first-280-body-identical',a==b,'differing-payload-byte-count',sum(x!=y for x,y in zip(a,b)))
