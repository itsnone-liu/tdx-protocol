#!/usr/bin/env python3
"""Test whether 143B op16 rows embed/refer to .lc1 records."""
import struct,zlib
from pathlib import Path
D=Path(__file__).resolve().parent/'out'/'rec_20261015T235945Z'
b=(D/'c10_s2c.bin').read_bytes(); M=bytes.fromhex('b1 cb 74 00')
rows=[]; pos=0
while 1:
 i=b.find(M,pos)
 if i<0 or i+16>len(b):break
 op=struct.unpack_from('<H',b,i+10)[0]; z=struct.unpack_from('<H',b,i+12)[0]
 if op==16 and i+16+z<=len(b):
  p=b[i+16:i+16+z]
  try:r=zlib.decompress(p) if p[:2]==b'\x78\x9c' else p
  except:r=p
  if len(r)>=143 and (len(r)-2)%143==0:
   cnt=struct.unpack_from('<H',r,0)[0]
   for j in range(cnt): rows.append(r[2+j*143:2+(j+1)*143])
 pos=i+4
print('rows',len(rows))
for row in rows[:5]:
 market=row[0]; code=row[1:7].decode('ascii','replace'); print('\n',market,code,'rowlen',len(row))
 fname=Path(r'D:\tdx-node\tdx-tq-v773\vipdoc\sz\minline')/f'sz{code}.lc1'
 if not fname.exists(): fname=Path(r'D:\tdx-node\tdx-tq-v773\vipdoc\sh\minline')/f'sh{code}.lc1'
 if fname.exists():
  lc=fname.read_bytes(); print('lc1',fname.name,len(lc))
  for sh in range(0,12):
   hits=[]
   for off in range(sh,len(row)-31,32):
    q=row[off:off+32]
    if lc.find(q)>=0:hits.append(off)
   if hits: print(' exact aligned stride hits shift',sh,hits)
  # all sliding 32B exact matches
  hits=[]
  for off in range(len(row)-31):
   ix=lc.find(row[off:off+32])
   if ix>=0:hits.append((off,ix))
  print('any 32B exact matches',hits[:8])
 else: print('no local file')
 print('hex:',row.hex(' '))
