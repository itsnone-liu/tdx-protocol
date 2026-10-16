#!/usr/bin/env python3
"""Inspect op0010 batch response records and compare to .lc1 bars."""
import re, struct, zlib
from pathlib import Path
D=Path(__file__).resolve().parent/'out'/'rec_20261015T235945Z'
req=(D/'c10_c2s.bin').read_bytes(); resp=(D/'c10_s2c.bin').read_bytes()
MAGIC=bytes.fromhex('b1 cb 74 00')
# Extract first op0010 request code list (legacy 6-zero prefix frames)
o=0; req_codes=[]
while o+12<=len(req):
    if req[o:o+6]!=b'\0'*6: o+=1; continue
    n1,n2,op=struct.unpack_from('<HHH',req,o+6)
    if n1!=n2 or o+12+n1>len(req): o+=1; continue
    pay=req[o+12:o+12+n1]
    if op==0x10 and len(pay)>=4:
        count=struct.unpack_from('<H',pay,0)[0]
        # request uses 7-byte market+code records
        codes=[]
        for i in range(count):
            x=pay[2+i*7:2+(i+1)*7]
            if len(x)==7: codes.append((x[0],x[1:7].decode('ascii','replace')))
        req_codes.append(codes)
    o+=12+n1
print('op0010 request batches',len(req_codes),'first batch codes',req_codes[0][:5] if req_codes else None)
# parse responses and row stride
pos=0; batches=[]
while True:
    i=resp.find(MAGIC,pos)
    if i<0 or i+16>len(resp): break
    op=struct.unpack_from('<H',resp,i+10)[0]
    zlen,rawlen=struct.unpack_from('<HH',resp,i+12)
    if op==0x10 and i+16+zlen<=len(resp):
        p=resp[i+16:i+16+zlen]
        try: raw=zlib.decompress(p) if p[:2]==b'\x78\x9c' else p
        except Exception: raw=p
        batches.append(raw)
    pos=i+4
print('op0010 response batches',len(batches),'raw lens',sorted(set(map(len,batches))))
if not batches: raise SystemExit
raw=batches[0]
count=struct.unpack_from('<H',raw,0)[0]
print('first response count',count,'expected bytes',2+count*143,'actual',len(raw))
for j in range(3):
    off=2+j*143; rec=raw[off:off+143]
    print(f'row{j} market={rec[0]} code={rec[1:7]!r} bytes={len(rec)} head={rec[:48].hex(" ")}')
    if j < len(req_codes[0]): print('  request code:',req_codes[0][j])

# Check if row payload contains any 32-byte .lc1 bars by field plausibility and OHLC signatures
vip=Path(r'D:\tdx-node\tdx-tq-v773\vipdoc\sz\minline')
for target in ['000036','000049','000059']:
    try: f=(vip/f'sz{target}.lc1').read_bytes()
    except Exception as e: print(target,e); continue
    sig=set()
    for x in range(0,len(f)-31,32):
        o,h,l,c=struct.unpack_from('<4f',f,x+4)
        sig.add(tuple(round(v,2) for v in (o,h,l,c)))
    rowidx=next((i for i,r in enumerate(req_codes[0]) if r[1]==target),None)
    if rowidx is None: continue
    rec=raw[2+rowidx*143:2+(rowidx+1)*143]
    print(f'\nTARGET {target}, row idx {rowidx}, .lc1 sigs {len(sig)}')
    for sh in range(0,9):
        hits=[]; plausible=[]
        for off in range(sh, len(rec)-31, 32):
            d,t=struct.unpack_from('<HH',rec,off)
            vals=struct.unpack_from('<4f',rec,off+4)
            if 540<=t<=930 and 0<vals[0]<10000 and 0<vals[1]<10000 and 0<vals[2]<10000 and 0<vals[3]<10000:
                plausible.append((off,d,t,vals))
                if tuple(round(v,2) for v in vals) in sig: hits.append((off,d,t,vals))
        if len(plausible)>=2:
            print(' shift',sh,'plausible',[(x[0],x[2],tuple(round(v,2) for v in x[3])) for x in plausible[:5]],'hits',len(hits))
