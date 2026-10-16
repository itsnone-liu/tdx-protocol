#!/usr/bin/env python3
"""Analyze actual 1-minute bulk c9 stream: locate op4045 responses, decompress."""
import re,struct,zlib
from collections import Counter
from pathlib import Path
D=Path(__file__).resolve().parent/'out'/'rec_20261015T235945Z'
req=(D/'c9_c2s.bin').read_bytes(); resp=(D/'c9_s2c.bin').read_bytes(); MAGIC=bytes.fromhex('b1 cb 74 00')
# Find all server response envelopes in direction stream
frames=[]; p=0
while True:
 i=resp.find(MAGIC,p)
 if i<0 or i+16>len(resp):break
 op=struct.unpack_from('<H',resp,i+10)[0]; z,raw=struct.unpack_from('<HH',resp,i+12)
 if z<65000 and i+16+z<=len(resp):
  pay=resp[i+16:i+16+z]
  body=pay
  if pay[:2] in (b'\x78\x9c',b'\x78\x01',b'\x78\xda'):
   try:body=zlib.decompress(pay)
   except:pass
  frames.append((i,op,z,raw,pay,body,resp[i+4:i+10]))
 p=i+4
print('response bytes',len(resp),'frames',len(frames),'opcodes',Counter(f[1] for f in frames))
# request scan for 0C envelopes and opcodes
ops=Counter(); reqs=[]
for i in range(len(req)-12):
 if req[i]==0x0c:
  op=struct.unpack_from('<H',req,i+10)[0]
  if op<0x2000:
   ops[op]+=1
   if op==0x0fcd:reqs.append((i,req[i+1],req[i+2],req[i+3:i+6],req[i+12:i+30]))
print('request 0C op counts',ops.most_common(15),'4045',len(reqs))
print('req first',[(i,s,f,m.hex(),pay[:18].hex()) for i,s,f,m,pay in reqs[:4]])
# inspect 4045 response bodies as 32B rows, classify bars/day
ok=0; hist=Counter(); samples=[]
for i,op,z,raw,pay,body,echo in frames:
 if op!=0x0fcd:continue
 bars=[]
 for off in range(6,len(body)-31,32):
  d,t=struct.unpack_from('<HH',body,off)
  if 500<=t<=1000:bars.append((d,t))
 if not bars:continue
 days={}
 for d,t in bars:days.setdefault(d,set()).add(t)
 pd=round(len(bars)/max(1,len(days))); ts=sorted({t for d,t in bars})
 hist[(pd,ts[0],ts[-1])]+=1;ok+=1
 if len(samples)<5:samples.append((i,z,raw,len(body),len(bars),len(days),pd,ts[0],ts[-1],bars[:2],bars[-2:]))
print('4045 data responses',ok,'granularity',hist.most_common(10))
for s in samples:print('sample',s)
