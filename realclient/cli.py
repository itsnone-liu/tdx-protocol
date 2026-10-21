#!/usr/bin/env python3
"""Experimental real-client-bootstrap TDX CLI. Python3 + tdxpy (decode only).
No TdxW IPC required. Bootstrap supplied explicitly; not bundled as credentials.
Desktop-exited quotes/xdxr smoke passed; Ubuntu execution is not yet tested.
"""
import argparse,json,socket,struct,zlib,math,os,sys,tempfile
from pathlib import Path
from tdxpy.parser.std.get_security_quotes import GetSecurityQuotesCmd
from tdxpy.parser.std.get_xdxr_info import GetXdXrInfo
from tdxpy.parser.std.get_finance_info import GetFinanceInfo
from tdxpy.parser.std.get_security_bars import GetSecurityBarsCmd

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

def parse_capital_batch(body,stocks):
 """Decode only verified op16 offsets; reject identity/length corruption."""
 if len(body)<2:raise ValueError('capital count missing')
 n=struct.unpack_from('<H',body)[0]
 if len(body)!=2+n*143:raise ValueError('capital row length mismatch')
 expected=set(stocks);seen=set();rows=[]
 for off in range(2,len(body),143):
  r=body[off:off+143];market=r[0];code=r[1:7].decode('ascii');key=(market,code)
  if key not in expected or key in seen:raise ValueError('capital identity mismatch')
  seen.add(key);float_wan=struct.unpack_from('<f',r,7)[0];date,ipo=struct.unpack_from('<II',r,15);total_wan=struct.unpack_from('<f',r,23)[0]
  if not all(math.isfinite(x) and x>=0 for x in (float_wan,total_wan)):raise ValueError('invalid capital values')
  rows.append(dict(market=market,code=code,float_shares=float_wan*10000,total_shares=total_wan*10000,data_date=date,ipo_date=ipo))
 if seen!=expected:raise ValueError('capital missing stocks')
 return rows

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
  if h[5]!=cmd.send_pkg[1]:raise ValueError('response sequence mismatch')
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
 def names(self,market,date):
  """Real-client044E/044D table; no undocumented record-tail decoding."""
  def exchange(op,payload):
   body=struct.pack('<H',op)+payload
   self.sock.sendall(b'\x0c\x01\x18\x64\x01\x01'+struct.pack('<HH',len(body),len(body))+body)
   hdr,b=recv(self.sock)
   if struct.unpack_from('<H',hdr,10)[0]!=op:raise ValueError('names opcode mismatch')
   return b
  total_body=exchange(0x044e,struct.pack('<HI',market,date))
  if len(total_body)!=2:raise ValueError('names count length mismatch')
  total=struct.unpack('<H',total_body)[0];rows=[];seen=set()
  for start in range(0,total,1600):
   b=exchange(0x044d,struct.pack('<HIH',market,start,1600)+b'\0'*6)
   if len(b)<2:raise ValueError('names page missing count')
   n=struct.unpack_from('<H',b)[0]
   if n!=min(1600,total-start) or len(b)!=2+n*37:raise ValueError('names page length mismatch')
   for off in range(2,len(b),37):
    r=b[off:off+37];code=r[:6].decode('ascii')
    if code in seen:raise ValueError('duplicate names code')
    seen.add(code);raw_name=r[8:24].split(b'\0')[0]
    try:name=raw_name.decode('gbk');decode_ok=True
    except UnicodeDecodeError:name=raw_name.decode('gbk',errors='replace');decode_ok=False
    rows.append(dict(market=market,code=code,name=name,name_decode_ok=decode_ok,volunit=struct.unpack_from('<H',r,6)[0]))
  return dict(market=market,asof_request_date=date,total=total,rows=rows)
 def capital_batch(self,stocks):
  result=[]
  for start in range(0,len(stocks),100):
   chunk=stocks[start:start+100]
   body=struct.pack('<HH',16,len(chunk))+b''.join(struct.pack('<B6s',m,c.encode('ascii')) for m,c in chunk)
   self.sock.sendall(b'\0'*6+struct.pack('<HH',len(body),len(body))+body)
   hdr,response=recv(self.sock)
   if struct.unpack_from('<H',hdr,10)[0]!=16:raise ValueError('capital opcode mismatch')
   result.extend(parse_capital_batch(response,chunk))
  return result
 def daily(self,market,code,count=400):
  """Bounded daily command, no full-history completeness claim."""
  if count<1 or count>12000:raise ValueError('count must be1..12000')
  rows=[]
  for start in range(0,count,800):
   cmd=GetSecurityBarsCmd(self.sock);cmd.setParams(4,market,code,start,min(800,count-start))
   page=self.call(cmd) or [];rows.extend(page)
   if len(page)<min(800,count-start):break
  bydate={}
  for r in rows:
   d=r['datetime'][:10]
   if d in bydate:raise ValueError('duplicate daily date')
   values=[r[x] for x in ('open','high','low','close')]
   if not all(math.isfinite(x) and x>0 for x in values):raise ValueError('invalid daily prices')
   bydate[d]=dict(date=d,open=r['open'],high=r['high'],low=r['low'],close=r['close'],volume_hand=r['vol'],amount=r['amount'])
  return [bydate[d] for d in sorted(bydate)]
 def qfq_daily(self,market,code,count,asof):
  raw=[r for r in self.daily(market,code,count) if r['date']<=asof]
  if not raw:raise ValueError('daily baseline unavailable')
  events=self.xdxr(market,code)
  # Categories requiring historical-client behavioral verification fail closed.
  for e in events:
   d='{:04d}-{:02d}-{:02d}'.format(e['year'],e['month'],e['day'])
   if raw[0]['date']<d<=asof and e['category'] not in (1,5,6,7,8,9,10,13,14):raise ValueError('unverified special category in adjustment window: '+str(e['category'])+' '+d)
  result=[dict(r) for r in raw]
  for field in ('open','high','low','close'):
   computed=dict(adjust([(r['date'],r[field]) for r in raw],events,asof))
   for r in result:r['raw_'+field]=r[field];r[field]=computed[r['date']]
  return dict(market=market,code=code,asof=asof,adjustment='cat1-affine-c2',rows=result,requested_count=count,returned_count=len(result),complete_history=False)
 def finance(self,market,code):
  cmd=GetFinanceInfo(self.sock);cmd.setParams(market,code)
  row=self.call(cmd)
  if not row or (row.get('market'),row.get('code'))!=(market,code):raise ValueError('finance identity mismatch')
  return row
 def snapshot(self,stocks,use_batch=False):
  """Finance should be cached by caller with date; no fake name/trading status.
  Volume hand-to-share factor100 verified only for sampled A shares.
  """
  result=self.quotes(stocks)
  capitals={(r['market'],r['code']):r for r in self.capital_batch([(q['market'],q['code']) for q in result['rows']])} if use_batch else {}
  for row in result['rows']:
   if use_batch:
    f=capitals[(row['market'],row['code'])];shares=f['float_shares'];date=f['data_date']
   else:
    f=self.finance(row['market'],row['code']);shares=f.get('liutongguben');date=f.get('updated_date')
   row['float_shares']=shares;row['finance_updated_date']=date
   row['capital_source']='op16' if use_batch else 'finance_info'
   row['turnover_pct']=row['vol']*10000/shares if shares and shares>0 else None
   row['pct_change']=(row['price']/row['last_close']-1)*100 if row['last_close'] and row['price'] else None
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

def atomic_json(path,value):
 """Preserve existing final output unless complete serialization+replace succeeds."""
 text=json.dumps(value,ensure_ascii=False,indent=2,allow_nan=False)
 target=Path(path);fd,tmp=tempfile.mkstemp(prefix=target.name+'.',suffix='.tmp',dir=str(target.parent))
 try:
  with os.fdopen(fd,'w',encoding='utf8') as out:out.write(text);out.flush();os.fsync(out.fileno())
  os.replace(tmp,target)
 finally:
  if os.path.exists(tmp):os.unlink(tmp)

def run_hosts(hosts,port,template,operation,attempt_log):
 """Only transport failures switch hosts; semantic/data corruption fails closed."""
 for endpoint in hosts:
  host=endpoint;selected_port=port
  if ':' in endpoint:
   host,port_text=endpoint.rsplit(':',1);selected_port=int(port_text)
  s=None
  try:
   s=Session(host,selected_port,template);value=operation(s)
   attempt_log.append(dict(host=host,port=selected_port,status='success'));return value
  except (OSError,ConnectionError) as e:
   attempt_log.append(dict(host=host,port=selected_port,status='transport_failed',error=repr(e)))
  finally:
   if s:s.close()
 raise ConnectionError('all configured hosts failed: '+str(attempt_log))

def main():
 ap=argparse.ArgumentParser(description=__doc__)
 ap.add_argument('command',choices=['quotes','snapshot','snapshot-batch','capital-batch','finance','names','daily','qfq-daily','xdxr','xdxr-batch']);ap.add_argument('symbols',nargs='+')
 ap.add_argument('--bootstrap',required=True);ap.add_argument('--host',default='123.60.164.122');ap.add_argument('--port',type=int,default=7709)
 ap.add_argument('--asof',help='qfq asof ISO date, default today');ap.add_argument('--out');ap.add_argument('--date',type=int,help='names request date YYYYMMDD, default today');ap.add_argument('--count',type=int,default=400);ap.add_argument('--fallback-host',action='append',default=[]);ap.add_argument('--attempt-log');a=ap.parse_args()
 attempts=[]
 def operation(s):
  stocks=[symbol(x) for x in a.symbols]
  if a.command=='quotes':return s.quotes(stocks)
  if a.command=='snapshot':return s.snapshot(stocks)
  if a.command=='snapshot-batch':return s.snapshot(stocks,use_batch=True)
  if a.command=='capital-batch':return s.capital_batch(stocks)
  if a.command=='names':
   import datetime
   date=a.date or int(datetime.date.today().strftime('%Y%m%d'))
   return {str(m):s.names(m,date) for m in sorted(set(m for m,c in stocks))}
  if a.command=='daily':return {x:s.daily(*symbol(x),count=a.count) for x in a.symbols}
  if a.command=='qfq-daily':
   import datetime
   asof=a.asof or datetime.date.today().isoformat();datetime.date.fromisoformat(asof)
   return {x:s.qfq_daily(*symbol(x),count=a.count,asof=asof) for x in a.symbols}
  if a.command=='finance':return {x:s.finance(*symbol(x)) for x in a.symbols}
  if a.command=='xdxr-batch':return s.xdxr_batch(stocks)
  return {x:s.xdxr(*symbol(x)) for x in a.symbols}
 result=run_hosts([a.host]+a.fallback_host,a.port,a.bootstrap,operation,attempts)
 if a.attempt_log:atomic_json(a.attempt_log,attempts)
 if a.out:atomic_json(a.out,result)
 else:print(json.dumps(result,ensure_ascii=False,indent=2,allow_nan=False))

if __name__=='__main__':
 try:main()
 except ConnectionError as e:sys.exit(str(e))
 except ValueError as e:sys.exit('data validation failed: '+str(e))
