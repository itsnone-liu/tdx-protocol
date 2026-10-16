#!/usr/bin/env python3
"""Replay fresh TdxW session-init frames, then try an independent 1m K-line query.

Uses fresh c1 bytes only through op0fde (before ordinary quote requests). This is
an experiment, not a claim that the prelude is the minimal or correct login API.
"""
import socket, struct, sys, zlib
from pathlib import Path

CAP = Path(__file__).resolve().parent / 'out' / 'rec_20261016T072253Z' / 'c1_c2s.bin'
HOST, PORT = '175.178.112.197', 7709
PREFIX_END = 6021  # includes op0fde at 6009..6020; first op0547 begins at 6021
CURSOR_START, CURSOR_END = 0x01352764, 0x01352769


def frames(data, end):
    off=0
    while off < end:
        if data[off] != 0x0c:
            raise ValueError(f'bad frame marker at {off}: {data[off]:02x}')
        n=10+struct.unpack_from('<H',data,off+6)[0]
        if n < 12 or off+n > end:
            raise ValueError(f'bad frame length at {off}: {n}')
        yield data[off:off+n]
        off+=n
    if off != end: raise ValueError(f'prefix ended at {off}, expected {end}')


def recv_exact(s,n):
    b=bytearray()
    while len(b)<n:
        x=s.recv(n-len(b))
        if not x: raise ConnectionError(f'peer closed with {n-len(b)} bytes outstanding')
        b.extend(x)
    return bytes(b)


def recv_response(s):
    h=recv_exact(s,16)
    if h[:4] != bytes.fromhex('b1 cb 74 00'):
        raise ValueError(f'bad response magic: {h.hex(" ")}')
    zlen,rawlen=struct.unpack_from('<HH',h,12)
    p=recv_exact(s,zlen)
    try: body=zlib.decompress(p) if p[:1]==b'\x78' else p
    except zlib.error: body=p
    return h,body,rawlen


def req_1m(seq,code,magic):
    return (bytes((0x0c,seq&255,0x38,magic,0x00,0x01))
      +struct.pack('<HHH',0x14,0x14,0x0fcd)+b'\x00\x00'+code.encode('ascii')
      +struct.pack('<IIH',CURSOR_START,CURSOR_END,0x0007))


def main():
    data=CAP.read_bytes()
    init=list(frames(data,PREFIX_END))
    print('replaying fresh init frames',len(init),'bytes',sum(map(len,init)))
    with socket.create_connection((HOST,PORT),timeout=10) as s:
        s.settimeout(25)
        for i,f in enumerate(init):
            s.sendall(f)
            h,body,raw=recv_response(s)
            op=struct.unpack_from('<H',h,10)[0]
            if h[5]!=f[1] or op!=struct.unpack_from('<H',f,10)[0]:
                raise RuntimeError(f'pair mismatch #{i} reqseq={f[1]} op={struct.unpack_from("<H",f,10)[0]:04x} respseq={h[5]} op={op:04x}')
            print(f'  init#{i:02d} op={op:04x} seq={h[5]} zbody={len(body)} raw={raw}')
        for magic in (0x8d,0x8e):
            f=req_1m(1,'000001',magic)
            s.sendall(f)
            h,body,raw=recv_response(s)
            print(f'1m magic={magic:02x} response op={struct.unpack_from("<H",h,10)[0]:04x} seq={h[5]} zbody={len(body)} raw={raw} head={body[:24].hex(" ")}')
            if len(body)>=6 and (len(body)-6)%32==0:
                print('  candidate bars',(len(body)-6)//32)

if __name__=='__main__': main()
