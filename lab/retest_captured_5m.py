#!/usr/bin/env python3
"""Replay exact c2 hello/capability/tdxlevel/first-4045 frame as staged baseline."""
import socket,struct,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
from tdx_min_cli import recv_response
D=Path(__file__).resolve().parent/'out'/'rec_20261015T235945Z'
b=(D/'c2_c2s.bin').read_bytes()
def frame_at(offset):
 n=10+struct.unpack_from('<H',b,offset+6)[0]
 return b[offset:offset+n]
# c2 initial frames: op11 at 0, op13 at 292, op4059 at 305, first 4045 at 8935
stages=[('hello',bytes.fromhex('00 00 00 00 00 00 10 00 10 00 52 04 00 00 00 00 d0 07 00 00 00 00 00 00 00 00')),
        ('op11',frame_at(0)),('op13',frame_at(292)),('op4059',frame_at(305)),('first4045',frame_at(8935))]
s=socket.create_connection(('175.178.112.197',7709),timeout=10);s.settimeout(10)
try:
 for name,f in stages:
  s.sendall(f)
  try:h,p=recv_response(s);print(name,'sent',len(f),'op',hex(struct.unpack_from('<H',h,10)[0]),'bytes',len(p),'status',p[:8].hex(' '))
  except Exception as e:print(name,'response error',repr(e));break
finally:s.close()
