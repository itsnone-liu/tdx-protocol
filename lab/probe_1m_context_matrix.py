#!/usr/bin/env python3
"""Controlled c9/c2 ticket × magic × period matrix for op4045 status."""
import socket,struct,sys,json
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
from tdx_min_cli import recv_response
D=Path(__file__).resolve().parent/'out'/'rec_20261015T235945Z'
streams={k:(D/f'{k}_c2s.bin').read_bytes() for k in ('c2','c9')}
# c9 prelude through last setup request just before first op4045; offset 3035.
cap=streams['c9'];prefix=cap[:3035]
frames=[];o=0
while o<len(prefix):
 n=10+struct.unpack_from('<H',prefix,o+6)[0]
 if prefix[o]!=12 or o+n>len(prefix):raise ValueError(f'bad frame at {o}')
 frames.append(prefix[o:o+n]);o+=n

def query(ticket_name, magic, period):
 s=socket.create_connection(('175.178.112.197',7709),timeout=10);s.settimeout(8)
 try:
  s.sendall(streams[ticket_name][:292]);h,b=recv_response(s)
  s.sendall(b''.join(frames[1:]))
  for _ in frames[1:]:
   try:h,b=recv_response(s)
   except (ConnectionError,TimeoutError,OSError):return print(f'ticket={ticket_name} magic={magic:02x} period={period:04x}: setup connection closed')
  body=b'\x00\x00'+b'399001'+struct.pack('<IIH',0x01352764,0x01352769,period)
  q=bytes([12,1,0x38,magic,0,1])+struct.pack('<HHH',20,20,0x0fcd)+body
  s.sendall(q);h,b=recv_response(s)
  op=struct.unpack_from('<H',h,10)[0]
  print(f'ticket={ticket_name} magic={magic:02x} period={period:04x}: op={op:04x} rflag={h[6]:02x} raw={len(b)} status={b[:12].hex(" ")}')
 finally:s.close()
for tk in ('c2','c9'):
 for mg in (0x8d,0x8e):
  for per in (0,7):query(tk,mg,per)
