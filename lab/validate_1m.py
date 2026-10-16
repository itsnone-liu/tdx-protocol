#!/usr/bin/env python3
"""Validate 10 1-minute op4045 request/response pairs from c9 against vipdoc .lc1.

Requests and responses are sent in order on a single connection; associate by
sequence byte. Parse response bars as 32B records and match exact bytes/prices
against existing .lc1 data. Report 10-stock PASS/partial counts.
"""
import struct,zlib
from pathlib import Path
D=Path(__file__).resolve().parent/'out'/'rec_20261015T235945Z'
req=(D/'c9_c2s.bin').read_bytes(); resp=(D/'c9_s2c.bin').read_bytes(); M=bytes.fromhex('b1 cb 74 00')
# Request envelopes
requests=[]
for i in range(len(req)-30):
 if req[i]==0x0c and req[i+2]==0x38 and req[i+10:i+12]==b'\xcd\x0f':
  ln=struct.unpack_from('<H',req,i+6)[0]
  if ln==20 and i+30<=len(req):
   pay=req[i+12:i+32]
   code=pay[2:8].decode('ascii','replace')
   c1,c2=struct.unpack_from('<II',pay,8)
   requests.append((req[i+1],code,c1,c2,i,pay))
# Responses
responses={}
pos=0
while 1:
 i=resp.find(M,pos)
 if i<0 or i+16>len(resp):break
 op=struct.unpack_from('<H',resp,i+10)[0];z,raw=struct.unpack_from('<HH',resp,i+12)
 if op==0x0fcd and i+16+z<=len(resp):
  pay=resp[i+16:i+16+z]
  try:body=zlib.decompress(pay)
  except:body=b''
  responses[resp[i+5]]=body
 pos=i+4
# pick 10 familiar SZ stocks in request list
wanted=['000001','000002','000333','000651','000858','002415','002594','300750','600000','600519']
sel=[]
for code in wanted:
 r=next((x for x in requests if x[1]==code),None)
 if r:
  body=responses.get(r[0],b''); bars=[]
  for off in range(6,len(body)-31,32):
   day,t=struct.unpack_from('<HH',body,off); o,h,l,c,amt=struct.unpack_from('<5f',body,off+4); vol,res=struct.unpack_from('<II',body,off+24)
   if 500<=t<=1000: bars.append((day,t,o,h,l,c,amt,vol,res,body[off:off+32]))
  sel.append((code,r,body,bars))
print(f"requests={len(requests)} responses={len(responses)} selected={len(sel)}/{len(wanted)}")
for code,r,body,bars in sel:
 market='sz' if code.startswith(('0','3')) else 'sh'
 f=Path(r'D:\tdx-node\tdx-tq-v773\vipdoc')/market/'minline'/f'{market}{code}.lc1'
 exact=0; pricehits=0
 if f.exists():
  lc=f.read_bytes(); recs=[lc[j:j+32] for j in range(0,len(lc)-31,32)]
  s=set(recs)
  exact=sum(1 for b in bars if b[9] in s)
  sig=set()
  for rec in recs:
   try:sig.add(tuple(round(v,2) for v in struct.unpack_from('<4f',rec,4)))
   except:pass
  pricehits=sum(1 for b in bars if tuple(round(v,2) for v in b[2:6]) in sig)
 print(f"{code}: bytes={len(body)} bars={len(bars)} first={bars[0][0:6] if bars else None} "
       f"last={bars[-1][0:6] if bars else None} local={'yes' if f.exists() else 'no'} "
       f"exact_records={exact} OHLC_hits={pricehits}")
