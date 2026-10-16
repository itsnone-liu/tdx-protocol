#!/usr/bin/env python3
"""Test captured client ticket on fresh TCP for 1m op4045 access."""
import socket,struct,zlib,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
from tdx_min_cli import OP13,OP4059,recv_response,request_1m,parse_bars
cap=Path(__file__).resolve().parent/'out'/'rec_20261015T235945Z'/'c9_c2s.bin'
ticket=cap.read_bytes()[:292]
s=socket.create_connection(('175.178.112.197',7709),timeout=10);s.settimeout(15)
s.sendall(ticket); h,b=recv_response(s);print('ticket response',h.hex(' '),len(b),b[:32].hex(' '))
s.sendall(OP13);h,b=recv_response(s);print('op13',len(b))
s.sendall(OP4059);h,b=recv_response(s);print('tdxlevel',len(b))
s.sendall(request_1m(1,'399001',0x01352764,0x01352769));h,b=recv_response(s)
print('4045 response',h.hex(' '),len(b),b[:32].hex(' '))
try:bars=parse_bars(b);print('bars',len(bars),bars[:1],bars[-1:] if bars else [])
except Exception as e:print('not bars',e)
s.close()
