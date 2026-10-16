#!/usr/bin/env python3
"""Verify fresh op11-only CLI output vs c9 capture and local .lc1 records."""
import csv, struct, zlib
from collections import Counter
from pathlib import Path
LAB=Path(__file__).resolve().parent
CAPDIR=LAB/'out'/'rec_20261015T235945Z'
CSV=LAB/'out'/'op11_minimal_login_1m_10.csv'
CODES=['000001','000002','000006','000007','000009','000010','000011','000012','000014','000016']

rq=(CAPDIR/'c9_c2s.bin').read_bytes();rs=(CAPDIR/'c9_s2c.bin').read_bytes()
reqs=[];o=0
while o+12<=len(rq):
 if rq[o]!=0x0c:o+=1;continue
 n=10+struct.unpack_from('<H',rq,o+6)[0]
 if n<12 or o+n>len(rq):o+=1;continue
 f=rq[o:o+n]
 if struct.unpack_from('<H',f,10)[0]==0x0fcd and len(f)==30:
  reqs.append((f[1],f[14:20].decode('ascii')))
 o+=n
responses=[];o=0;magic=bytes.fromhex('b1 cb 74 00')
while True:
 i=rs.find(magic,o)
 if i<0 or i+16>len(rs):break
 n=16+struct.unpack_from('<H',rs,i+12)[0]
 if i+n>len(rs):break
 f=rs[i:i+n]
 if struct.unpack_from('<H',f,10)[0]==0x0fcd:
  p=f[16:]
  try: body=zlib.decompress(p)
  except zlib.error:body=p
  responses.append((f[5],body))
 o=i+n
captured={}
for (seq,code),(rseq,body) in zip(reqs,responses):
 if seq==rseq and code in CODES:
  captured[code]=Counter(body[j:j+32] for j in range(6,len(body)-31,32))
live={c:Counter() for c in CODES}
with CSV.open(newline='',encoding='utf-8') as f:
 for row in csv.DictReader(f):
  code=row['code']
  if code not in live:continue
  rec=struct.pack('<HH5fII',int(row['day_marker']),int(row['minute']),float(row['open']),float(row['high']),float(row['low']),float(row['close']),float(row['amount']),int(row['volume']),int(row['reserved']))
  live[code][rec]+=1
for code in CODES:
 market='sz' if code.startswith(('0','2','3')) else 'sh'
 path=Path(r'D:\tdx-node\tdx-tq-v773\vipdoc')/market/'minline'/f'{market}{code}.lc1'
 data=path.read_bytes();local=Counter(data[i:i+32] for i in range(0,len(data)-31,32))
 cap_hits=sum((live[code]&captured.get(code,Counter())).values())
 local_hits=sum((live[code]&local).values())
 print(f'{code}: {sum(live[code].values())} bars; capture={cap_hits}/960; local={local_hits}/960')
 if sum(live[code].values())!=960 or cap_hits!=960 or local_hits!=960:raise SystemExit(f'FAIL {code}')
print(f'PASS {len(CODES)} stocks × 960 records exact vs authentic capture and local cache')
