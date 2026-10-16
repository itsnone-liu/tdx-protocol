#!/usr/bin/env python3
"""Compare exact c2/c9 request/response frames before first op4045."""
from pathlib import Path
import struct, collections, zlib
D=Path(__file__).resolve().parent/'out'/'rec_20261015T235945Z'

def req_frames(buf):
 out=[];o=0
 while o+12<=len(buf):
  if buf[o]!=12:o+=1;continue
  n=10+struct.unpack_from('<H',buf,o+6)[0]
  if n<12 or o+n>len(buf):o+=1;continue
  f=buf[o:o+n];op=struct.unpack_from('<H',f,10)[0]
  if op==0x0fcd:break
  out.append((f[1],op,o,f));o+=n
 return out

def resp_frames(buf):
 out=[];o=0
 while o+16<=len(buf):
  i=buf.find(bytes.fromhex('b1 cb 74 00'),o)
  if i<0 or i+16>len(buf):break
  n=16+struct.unpack_from('<H',buf,i+12)[0]
  if n<16 or i+n>len(buf):o=i+4;continue
  f=buf[i:i+n];out.append((f[5],struct.unpack_from('<H',f,10)[0],f[16:]));o=i+n
 return out

for name in ('c2','c9'):
 req=(D/f'{name}_c2s.bin').read_bytes();res=(D/f'{name}_s2c.bin').read_bytes()
 fs=req_frames(req);rs=resp_frames(res);bykey={(s,o):p for s,o,p in rs}
 print(f'[{name}] pre4045={len(fs)} ops={dict(collections.Counter(hex(op) for _,op,_,_ in fs))}; responses={len(rs)}')
 for seq,op,off,f in fs:
  if op not in (0x44d,0x44e):continue
  p=bykey.get((seq,op),b''); raw=zlib.decompress(p) if p[:2] in (b'\x78\x9c',b'\x78\x01',b'\x78\xda') else p
  print(f' seq={seq:3} op={op:04x} req={f[12:].hex(" ")} resp_comp={len(p)} resp_raw={len(raw)} rawhead={raw[:16].hex(" ")}')
