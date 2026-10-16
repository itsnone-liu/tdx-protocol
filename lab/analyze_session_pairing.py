#!/usr/bin/env python3
"""Report c9 request/response sequence/opcode pairing, excluding TCP segmentation."""
import json,struct
from pathlib import Path
D=Path(__file__).resolve().parent/'out'/'rec_20261015T235945Z'
rq=(D/'c9_c2s.bin').read_bytes();rs=(D/'c9_s2c.bin').read_bytes()
requests=[];responses=[]
for line in (D/'c9_events.jsonl').read_text(encoding='utf-8').splitlines():
 e=json.loads(line); b=(rq if e['dir']=='c2s' else rs)[e['off']:e['off']+e['len']]
 if e['dir']=='c2s':
  # Events are TCP segments, not guaranteed frame boundaries; later stream parser is authoritative.
  continue
# Stream parser: c2s legacy envelopes have total length = 10 + declared len.
o=0
while o+12<=len(rq):
 if rq[o]!=0x0c:o+=1;continue
 n=struct.unpack_from('<H',rq,o+6)[0];total=10+n
 if total<12 or o+total>len(rq):o+=1;continue
 requests.append((rq[o+1],struct.unpack_from('<H',rq,o+10)[0]));o+=total
# Response stream comprises framed responses; data can arrive split across TCP events.
o=0;magic=bytes.fromhex('b1 cb 74 00')
while True:
 i=rs.find(magic,o)
 if i<0 or i+16>len(rs):break
 n=struct.unpack_from('<H',rs,i+12)[0]
 if i+16+n<=len(rs):responses.append((rs[i+5],struct.unpack_from('<H',rs,i+10)[0]))
 o=i+4
print('requests',len(requests),'responses',len(responses))
print('sequence/opcode aligned',requests==responses)
print('first mismatch',next(((i,a,b) for i,(a,b) in enumerate(zip(requests,responses)) if a!=b),None))
print('4045 counts',sum(op==0x0fcd for _,op in requests),sum(op==0x0fcd for _,op in responses))
