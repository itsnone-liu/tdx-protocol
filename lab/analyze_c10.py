#!/usr/bin/env python3
"""Analyze response frames in c10 (the actual 1-minute download session)."""
import re
import struct
import zlib
from collections import Counter
from pathlib import Path

p=Path(__file__).resolve().parent/"out"/"rec_20261015T235945Z"/"c10_s2c.bin"
b=p.read_bytes()
magic=bytes.fromhex("b1 cb 74 00")
frames=[]
o=0
while True:
    i=b.find(magic,o)
    if i<0 or i+16>len(b): break
    op,=struct.unpack_from("<H",b,i+10)
    z,raw=struct.unpack_from("<HH",b,i+12)
    if i+16+z<=len(b):
        pay=b[i+16:i+16+z]
        body=pay
        if pay[:2] in (b"\x78\x9c",b"\x78\x01",b"\x78\xda"):
            try: body=zlib.decompress(pay)
            except zlib.error: pass
        frames.append((i,op,z,raw,pay,body))
    o=i+4
print("frames",len(frames),"ops",Counter(f[1] for f in frames))
for j,(i,op,z,raw,pay,body) in enumerate(frames):
    print(f"#{j:03d} off={i:6d} op={op:04x} z={z:5d} raw={raw:5d} body={len(body):5d} head={body[:32].hex(' ')}")
    asc=re.sub(rb"[^\x20-\x7e]",b".",body[:500]).decode('ascii','replace')
    txt=''.join(x for x in asc if x!='.')
    if len(txt)>8: print("   text:",txt[:140])
    # test 32-byte record parse if length divisible-ish
    if len(body)>1000:
        for shift in range(0,32):
            n=(len(body)-shift)//32
            if n<8: continue
            mins=[]
            days=[]
            good=0
            for k in range(n):
                off=shift+k*32
                d,t=struct.unpack_from('<HH',body,off)
                if 540<=t<=930: good+=1; mins.append(t);days.append(d)
            if good>n*.7:
                print(f"   32B candidate shift={shift} rows={good}/{n} time={min(mins)}..{max(mins)} days={len(set(days))}")
                break
