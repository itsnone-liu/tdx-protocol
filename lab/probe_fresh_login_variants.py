#!/usr/bin/env python3
"""Test which parts of the fresh TdxW prelude are needed for live 1m access."""
import socket, struct, zlib
from pathlib import Path

CAP=Path(__file__).resolve().parent/'out'/'rec_20261016T072253Z'/'c1_c2s.bin'
HOST,PORT='175.178.112.197',7709
START,END=0x01352764,0x01352769

def get_init():
 b=CAP.read_bytes(); out=[];o=0
 while o+12<=len(b):
  if b[o]!=12:o+=1;continue
  n=10+struct.unpack_from('<H',b,o+6)[0]
  if n<12 or o+n>len(b):o+=1;continue
  f=b[o:o+n];op=struct.unpack_from('<H',f,10)[0]
  if op in (0x0547,0x054c,0x0fcd):break
  out.append(f);o+=n
 return out

def recv_exact(s,n):
 b=bytearray()
 while len(b)<n:
  x=s.recv(n-len(b))
  if not x:raise ConnectionError('server closed')
  b.extend(x)
 return bytes(b)

def recv(s):
 h=recv_exact(s,16);z=struct.unpack_from('<H',h,12)[0];p=recv_exact(s,z)
 try:d=zlib.decompress(p) if p[:1]==b'\x78' else p
 except:d=p
 return h,d

def query(label, init, alter_ticket=False):
 print('\n###',label,'frames',len(init),'alter_ticket',alter_ticket)
 try:
  with socket.create_connection((HOST,PORT),timeout=12) as s:
   s.settimeout(25)
   for i,orig in enumerate(init):
    f=bytearray(orig)
    if alter_ticket and i==0:f[-8:]=b'\0'*8
    s.sendall(f);h,d=recv(s)
    op=struct.unpack_from('<H',h,10)[0]
    if h[5]!=f[1] or op!=struct.unpack_from('<H',f,10)[0]:
     print(' init mismatch',i,'req',f[1],hex(struct.unpack_from('<H',f,10)[0]),'resp',h[5],hex(op));return
   print(' init accepted')
   q=(bytes([0x0c,1,0x38,0x8d,0,1])+struct.pack('<HHH',0x14,0x14,0x0fcd)+b'\0\0'+'000001'.encode()+struct.pack('<IIH',START,END,7))
   s.sendall(q);h,d=recv(s)
   op=struct.unpack_from('<H',h,10)[0]
   bars=(len(d)-6)//32 if len(d)>=6 and (len(d)-6)%32==0 else None
   print(' response op',hex(op),'seq',h[5],'body',len(d),'head',d[:12].hex(' '),'bars',bars)
 except Exception as e: print(' ERROR',type(e).__name__,str(e))

if __name__=='__main__':
 init=get_init()
 query('first-five-control-frames',init[:5])
 query('full-fresh-prelude-zero-last8',init,True)
 query('full-fresh-prelude-exact',init)
