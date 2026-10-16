#!/usr/bin/env python3
"""Exact 32-byte comparison of live CLI CSV vs c9 capture and local .lc1."""
import csv, struct, zlib, sys
from collections import Counter
from pathlib import Path
LAB=Path(__file__).resolve().parent
D=LAB/'out'/'rec_20261015T235945Z'
CSV=Path(sys.argv[1]) if len(sys.argv)>1 else LAB/'out'/'live_1m_probe_round2.csv'
CODES=['000001','000002','000006','000007','000009','000010','000011','000012','000014','000016']
rq=(D/'c9_c2s.bin').read_bytes(); rs=(D/'c9_s2c.bin').read_bytes()
requests=[];o=0
while o+12<=len(rq):
 if rq[o]!=0x0c:o+=1;continue
 n=10+struct.unpack_from('<H',rq,o+6)[0]
 if n<12 or o+n>len(rq):o+=1;continue
 f=rq[o:o+n];op=struct.unpack_from('<H',f,10)[0]
 if op==0x0fcd and len(f)==30:
  code=f[14:20].decode('ascii');requests.append((f[1],code))
 o+=n
responses=[];o=0;magic=bytes.fromhex('b1 cb 74 00')
while o+16<=len(rs):
 i=rs.find(magic,o)
 if i<0 or i+16>len(rs):break
 n=16+struct.unpack_from('<H',rs,i+12)[0]
 if i+n>len(rs):break
 f=rs[i:i+n];op=struct.unpack_from('<H',f,10)[0]
 if op==0x0fcd:
  p=f[16:];raw=zlib.decompress(p) if p[:2] in (b'\x78\x9c',b'\x78\x01',b'\x78\xda') else p
  responses.append((f[5],raw))
 o=i+n
capture={}
for (seq,code),(rseq,raw) in zip(requests,responses):
 if seq!=rseq or code not in CODES:continue
 capture[code]=[raw[j:j+32] for j in range(6,len(raw)-31,32)]
live={c:[] for c in CODES}
with CSV.open(newline='',encoding='utf-8') as f:
 for row in csv.DictReader(f):
  c=row['code'];
  if c not in live:continue
  record=struct.pack('<HH5fII',int(row['day_marker']),int(row['minute']),float(row['open']),float(row['high']),float(row['low']),float(row['close']),float(row['amount']),int(row['volume']),int(row['reserved']))
  live[c].append(record)
for code in CODES:
 market='sz' if code.startswith(('0','2','3')) else 'sh'
 p=Path(r'D:\tdx-node\tdx-tq-v773\vipdoc')/market/'minline'/f'{market}{code}.lc1'
 local=p.read_bytes();local_records=[local[i:i+32] for i in range(0,len(local)-31,32)]
 cap=Counter(capture.get(code,[])); lv=Counter(live[code]); loc=Counter(local_records)
 exact_cap=sum((lv & cap).values());exact_local=sum((lv & loc).values())
 print(f'{code}: live={len(live[code])} capture_matches={exact_cap}/{len(live[code])} local_matches={exact_local}/{len(live[code])}')
 if len(live[code])!=960 or exact_cap!=960 or exact_local!=960:raise SystemExit(f'FAIL {code}')
print(f'PASS: {len(CODES)} stocks × 960 exact 32-byte records from live CLI match c9 and local .lc1')
