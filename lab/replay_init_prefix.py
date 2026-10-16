#!/usr/bin/env python3
"""Replay old c9 pre-4045 requests to characterize its static baseline only."""
import socket,struct,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
from tdx_min_cli import recv_response,request_1m,parse_bars
D=Path(__file__).resolve().parent/'out'/'rec_20261015T235945Z'
cap=(D/'c9_c2s.bin').read_bytes();prefix=cap[:3035]
frames=[];o=0
while o<len(prefix):
 if prefix[o]!=0x0c:raise ValueError(f'bad request prefix at {o}')
 total=10+struct.unpack_from('<H',prefix,o+6)[0]
 if total<12 or o+total>len(prefix):raise ValueError(f'bad frame at {o}')
 frames.append(prefix[o:o+total]);o+=total
s=socket.create_connection(('175.178.112.197',7709),timeout=10);s.settimeout(10)
print('replaying',len(frames),'static c9 prelude frames; this is not fresh desktop state')
try:
 for j,f in enumerate(frames):
  op=struct.unpack_from('<H',f,10)[0]
  s.sendall(f);h,b=recv_response(s)
  if j<8 or j==len(frames)-1 or op in (0x044d,0x044e):
   print(f'#{j} op={op:04x} -> {struct.unpack_from("<H",h,10)[0]:04x} body={len(b)} prefix={b[:8].hex(" ")}')
 for seq,code in enumerate(['000001','000002','000006','000007','000009','000010','000011','000012','000014','000016'],1):
  s.sendall(request_1m(seq,code,0x01352764,0x01352769));h,b=recv_response(s)
  bars=parse_bars(b) if len(b)>6 and (len(b)-6)%32==0 else []
  print(f'{code}: response={len(b)}B bars={len(bars)} status={b[:8].hex(" ")}')
finally:s.close()
