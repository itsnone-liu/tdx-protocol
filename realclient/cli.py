#!/usr/bin/env python3
"""Experimental real-client-bootstrap TDX CLI. Python3 + tdxpy (decode only).
No TdxW IPC required. Bootstrap supplied explicitly; not bundled as credentials.
Desktop-exited quotes/xdxr smoke passed; Ubuntu execution is not yet tested.
"""
import argparse,json,socket,struct,zlib
from pathlib import Path
from tdxpy.parser.std.get_security_quotes import GetSecurityQuotesCmd
from tdxpy.parser.std.get_xdxr_info import GetXdXrInfo

def exact(s,n):
 b=bytearray()
 while len(b)<n:
  chunk=s.recv(n-len(b))
  if not chunk:raise ConnectionError('truncated response')
  b.extend(chunk)
 return bytes(b)

def recv(s):
 h=exact(s,16)
 if h[:4]!=bytes.fromhex('b1 cb 74 00'):raise ValueError('unexpected header')
 packed,raw=struct.unpack_from('<HH',h,12)
 body=exact(s,packed)
 if packed!=raw:body=zlib.decompress(body)
 if len(body)!=raw:raise ValueError('response size mismatch')
 return h,body

def symbol(value):
 market={'sz':0,'sh':1,'bj':2}.get(value[:2].lower())
 code=value[2:]
 if market is None or len(code)!=6 or not code.isdigit():raise ValueError('expected sh600125 / sz000001 / bj920002')
 return market,code

class Session:
 def __init__(self,host,port,template):
  prefix=Path(template).read_bytes()
  if len(prefix)!=284:raise ValueError('expected observed 284-byte bootstrap prefix')
  self.sock=socket.create_connection((host,port),timeout=10);self.sock.settimeout(15)
  self.sock.sendall(prefix+b'\0'*8)
  h,b=recv(self.sock)
  if struct.unpack_from('<H',h,10)[0]!=11:raise ValueError('bootstrap opcode mismatch')
 def call(self,cmd):
  self.sock.sendall(cmd.send_pkg);h,b=recv(self.sock)
  if struct.unpack_from('<H',h,10)[0]!=struct.unpack_from('<H',cmd.send_pkg,10)[0]:raise ValueError('response opcode mismatch')
  return cmd.parseResponse(b)
 def quotes(self,stocks):
  result=[];missing=[];unexpected=[]
  for start in range(0,len(stocks),80):
   chunk=stocks[start:start+80];cmd=GetSecurityQuotesCmd(self.sock);cmd.setParams(chunk)
   rows=self.call(cmd) or [];expected=set(chunk);seen=set()
   for r in rows:
    key=(r['market'],r['code'])
    if key not in expected:unexpected.append(key);continue
    if key in seen:raise ValueError('duplicate returned quote')
    seen.add(key);result.append(r)
   missing.extend(sorted(expected-seen))
  return {'rows':result,'missing':missing,'unexpected':unexpected,'complete':not missing and not unexpected}
 def xdxr(self,market,code):
  cmd=GetXdXrInfo(self.sock);cmd.setParams(market,code)
  return self.call(cmd)
 def xdxr_batch(self,stocks):
  """Actual client op15 format. Batches <=60; response overflow fails closed.
  Return all categories and four raw floats without guessing unknown meanings.
  """
  result=[]
  for start in range(0,len(stocks),60):
   chunk=stocks[start:start+60]
   body=struct.pack('<HH',15,len(chunk))+b''.join(struct.pack('<B6s',m,c.encode('ascii')) for m,c in chunk)
   self.sock.sendall(b'\0'*6+struct.pack('<HH',len(body),len(body))+body)
   hdr,b=recv(self.sock)
   if struct.unpack_from('<H',hdr,10)[0]!=15:raise ValueError('batch xdxr opcode mismatch')
   n=struct.unpack_from('<H',b)[0];pos=2;seen=set()
   for _ in range(n):
    market,code,count=struct.unpack_from('<B6sH',b,pos);pos+=9;code=code.decode('ascii')
    key=(market,code)
    if key not in set(chunk) or key in seen:raise ValueError('batch xdxr stock identity mismatch')
    seen.add(key);events=[]
    for _ in range(count):
     em,ec,date,cat,f1,f2,f3,f4=struct.unpack_from('<B7sIBffff',b,pos);pos+=29
     if (em,ec.rstrip(b'\0').decode('ascii'))!=key:raise ValueError('event identity mismatch')
     events.append(dict(date=date,category=cat,f1=f1,f2=f2,f3=f3,f4=f4))
    result.append(dict(market=market,code=code,events=events))
   if pos!=len(b) or seen!=set(chunk):raise ValueError('incomplete batch xdxr response')
  return result
 def close(self):self.sock.close()

def adjust(bars,events,asof):
 """Client-grounded C2. bars sorted (ISO date,price); no future event leakage.
Same-day multiple cat1 records require upstream normalization; fail closed.
"""
 selected=[];seen=set()
 for e in events:
  if e['category']!=1:continue
  d='{:04d}-{:02d}-{:02d}'.format(e['year'],e['month'],e['day'])
  if d>asof:continue
  if d in seen:raise ValueError('multiple cat1 events same date require normalization')
  seen.add(d)
  fh=(e.get('fenhong') or 0)/10;pg=(e.get('peigu') or 0)/10
  selected.append((d,fh-(e.get('peigujia') or 0)*pg,1+(e.get('songzhuangu') or 0)/10+pg))
 selected.sort();i=len(selected);D=0.;K=1.;out=[]
 for d,p in sorted(bars,reverse=True):
  if d>asof:continue
  while i and selected[i-1][0]>d:
   _,cash,ke=selected[i-1];D=cash+D*ke;K*=ke;i-=1
  out.append((d,(p-D)/K))
 return list(reversed(out))

def main():
 ap=argparse.ArgumentParser(description=__doc__)
 ap.add_argument('command',choices=['quotes','xdxr','xdxr-batch']);ap.add_argument('symbols',nargs='+')
 ap.add_argument('--bootstrap',required=True);ap.add_argument('--host',default='123.60.164.122');ap.add_argument('--port',type=int,default=7709)
 ap.add_argument('--out');a=ap.parse_args();s=Session(a.host,a.port,a.bootstrap)
 try:
  stocks=[symbol(x) for x in a.symbols]
  if a.command=='quotes':result=s.quotes(stocks)
  elif a.command=='xdxr-batch':result=s.xdxr_batch(stocks)
  else:result={x:s.xdxr(*symbol(x)) for x in a.symbols}
  text=json.dumps(result,ensure_ascii=False,indent=2)
  if a.out:Path(a.out).write_text(text,encoding='utf8')
  else:print(text)
 finally:s.close()
if __name__=='__main__':main()
