#!/usr/bin/env python3
"""Pair c9 1m requests/responses by stream order; compare bars with .lc1 by day/time."""
import struct,zlib
from collections import Counter
from pathlib import Path
D=Path(__file__).resolve().parent/'out'/'rec_20261015T235945Z'
rq=(D/'c9_c2s.bin').read_bytes(); rs=(D/'c9_s2c.bin').read_bytes(); M=bytes.fromhex('b1 cb 74 00')
requests=[]
for i in range(len(rq)-32):
 if rq[i]==0x0c and rq[i+10:i+12]==b'\xcd\x0f':
  ln=struct.unpack_from('<H',rq,i+6)[0]
  if ln==20 and i+32<=len(rq):
   p=rq[i+12:i+32]
   code=p[2:8].decode('ascii','replace'); c1,c2=struct.unpack_from('<II',p,8)
   if code.isdigit(): requests.append((rq[i+1],code,c1,c2,i))
responses=[];pos=0
while 1:
 i=rs.find(M,pos)
 if i<0 or i+16>len(rs):break
 op=struct.unpack_from('<H',rs,i+10)[0];z,raw=struct.unpack_from('<HH',rs,i+12)
 if op==0x0fcd and i+16+z<=len(rs):
  p=rs[i+16:i+16+z]
  try: body=zlib.decompress(p)
  except:body=b''
  bars=[]
  for o in range(6,len(body)-31,32):
   day,t=struct.unpack_from('<HH',body,o)
   if 500<=t<=1000:
    vals=struct.unpack_from('<5f',body,o+4); vol,res=struct.unpack_from('<II',body,o+24)
    bars.append((day,t,*vals,vol,res,body[o:o+32]))
  responses.append((rs[i+5],body,bars,i))
 pos=i+4
print('requests',len(requests),'responses',len(responses))
# Pair sequentially and find 10 stocks with local file
paired=[]
for idx,(r,resp) in enumerate(zip(requests,responses)):
 paired.append((r,resp))
# Select first 10 non-index stocks that have local .lc1 ground truth.
wanted=[];seen=set()
for r,resp in paired:
 code=r[1]
 if code in seen or code.startswith('399') or not resp[2]: continue
 market='sz' if code.startswith(('0','2','3')) else 'sh'
 f=Path(r'D:\tdx-node\tdx-tq-v773\vipdoc')/market/'minline'/f'{market}{code}.lc1'
 if f.exists():
  wanted.append((r,resp,f));seen.add(code)
 if len(wanted)>=10:break
print('selected',len(wanted),'stocks:',[x[0][1] for x in wanted])
for r,resp,f in wanted:
 seq,code,c1,c2,reqoff=r; rseq,body,bars,roff=resp
 lc=f.read_bytes(); lookup={}
 for o in range(0,len(lc)-31,32):
  day,t=struct.unpack_from('<HH',lc,o)
  lookup.setdefault((day,t),[]).append(lc[o:o+32])
 exact=0; oh=0;matched=[]
 for bar in bars:
  day,t=bar[:2]; vals=bar[2:6]
  candidates=lookup.get((day,t),[])
  if candidates:
   exact+=any(c==bar[9] for c in candidates)
   for c in candidates:
    v=struct.unpack_from('<4f',c,4)
    if tuple(round(x,2) for x in v)==tuple(round(x,2) for x in vals):oh+=1;matched.append((day,t,vals,v));break
 print(f'{code}: reqseq={seq} respseq={rseq} raw={len(body)} bars={len(bars)} local_records={len(lc)//32} daytime_hits={sum(1 for b in bars if (b[0],b[1]) in lookup)} exact={exact} OHLC_match={oh}')
 if matched:print('  match sample',matched[0])
 if bars:print('  first',bars[0][:6],'last',bars[-1][:6])
