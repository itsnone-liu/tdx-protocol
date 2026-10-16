#!/usr/bin/env python3
"""Test the smallest captured login prefix that enables live 1m requests."""
import socket, struct, zlib
from pathlib import Path
CAP=Path(__file__).resolve().parent/'out'/'rec_20261016T072253Z'/'c1_c2s.bin'
HOST,PORT='175.178.112.197',7709
START,END=0x01352764,0x01352769

def frames():
 b=CAP.read_bytes();out=[];o=0
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
  z=s.recv(n-len(b))
  if not z:raise ConnectionError('closed')
  b.extend(z)
 return bytes(b)
def recv(s):
 h=recv_exact(s,16);n=struct.unpack_from('<H',h,12)[0];p=recv_exact(s,n)
 try:d=zlib.decompress(p) if p[:1]==b'\x78' else p
 except:d=p
 return h,d

def run(label,fs,zero=False):
 try:
  with socket.create_connection((HOST,PORT),timeout=10) as s:
   s.settimeout(20)
   for i,orig in enumerate(fs):
    f=bytearray(orig)
    if zero and i==0:f[-8:]=b'\0'*8
    s.sendall(f);h,d=recv(s)
    if h[5]!=f[1] or struct.unpack_from('<H',h,10)[0]!=struct.unpack_from('<H',f,10)[0]:
     print(label,'init-mismatch',i);return
   q=bytes([0x0c,1,0x38,0x8d,0,1])+struct.pack('<HHH',0x14,0x14,0x0fcd)+b'\0\0'+'000001'.encode()+struct.pack('<IIH',START,END,7)
   s.sendall(q);h,d=recv(s)
   bars=(len(d)-6)//32 if len(d)>=6 and (len(d)-6)%32==0 else None
   print(label,'prefix_frames',len(fs),'nonce_zero',zero,'status_len',len(d),'head',d[:6].hex(' '),'bars',bars)
 except Exception as e:print(label,'ERROR',type(e).__name__,str(e))

if __name__=='__main__':
 f=frames()
 for n in range(0,6):run(f'prefix-{n}',f[:n])
 run('prefix-5-zero-nonce',f[:5],True)
