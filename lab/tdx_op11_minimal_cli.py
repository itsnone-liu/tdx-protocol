#!/usr/bin/env python3
"""Minimal independent TDX 1m data-session CLI, no TdxW process required.

The observed op11 bootstrap frame has a 272-byte stable payload and an 8-byte
suffix. Fresh, zero, and random suffixes were each accepted in live tests. This
establishes the 7709 MARKET-DATA session; it does not reproduce the separate
username/password account-login service.
"""
import argparse, csv, secrets, socket, struct, zlib
from pathlib import Path

HOST_DEFAULT, PORT_DEFAULT = '175.178.112.197', 7709
CURSOR_START, CURSOR_END = 0x01352764, 0x01352769
CODES_DEFAULT = ['000001','000002','000006','000007','000009','000010','000011','000012','000014','000016']
# Captured static prefix excludes the final 8 bytes, tested independently.
OP11_PREFIX_PATH = Path(__file__).resolve().parent / 'op11_template.bin'
OP11_PREFIX = OP11_PREFIX_PATH.read_bytes()


def recv_exact(sock, n):
    out=bytearray()
    while len(out)<n:
        part=sock.recv(n-len(out))
        if not part: raise ConnectionError(f'peer closed with {n-len(out)} bytes outstanding')
        out.extend(part)
    return bytes(out)


def recv_response(sock):
    hdr=recv_exact(sock,16)
    if hdr[:4]!=bytes.fromhex('b1 cb 74 00'):
        raise ValueError('unexpected response header '+hdr.hex(' '))
    zlen,rawlen=struct.unpack_from('<HH',hdr,12)
    payload=recv_exact(sock,zlen)
    try: body=zlib.decompress(payload) if payload[:1]==b'\x78' else payload
    except zlib.error: body=payload
    return hdr,body,rawlen


def make_op11():
    if len(OP11_PREFIX)!=284: raise AssertionError(f'bad op11 template length {len(OP11_PREFIX)}')
    frame=OP11_PREFIX+secrets.token_bytes(8)
    if len(frame)!=292: raise AssertionError('bad op11 frame length')
    return frame


def request_1m(seq,code):
    if len(code)!=6 or not code.isdigit(): raise ValueError(f'invalid stock code {code!r}')
    return (bytes((0x0c,seq&0xff,0x38,0x8d,0x00,0x01))
      +struct.pack('<HHH',0x14,0x14,0x0fcd)+b'\x00\x00'+code.encode('ascii')
      +struct.pack('<IIH',CURSOR_START,CURSOR_END,0x0007))


def parse_bars(body):
    if len(body)<6 or (len(body)-6)%32: raise ValueError(f'unexpected op4045 body size {len(body)}')
    bars=[]
    for off in range(6,len(body),32):
        day,minute=struct.unpack_from('<HH',body,off)
        vals=struct.unpack_from('<5f',body,off+4)
        volume,reserved=struct.unpack_from('<II',body,off+24)
        bars.append((day,minute,*vals,volume,reserved))
    return bars


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('codes',nargs='*',default=CODES_DEFAULT)
    ap.add_argument('--host',default=HOST_DEFAULT);ap.add_argument('--port',type=int,default=PORT_DEFAULT)
    ap.add_argument('--out',default='tdx_1m.csv')
    args=ap.parse_args()
    rows=[]
    with socket.create_connection((args.host,args.port),timeout=15) as sock:
        sock.settimeout(30)
        ticket=make_op11();sock.sendall(ticket)
        h,body,raw=recv_response(sock)
        op=struct.unpack_from('<H',h,10)[0]
        if op!=0x000b or h[5]!=ticket[1]: raise RuntimeError(f'op11 bootstrap mismatch: op={op:04x} seq={h[5]}')
        print(f'op11 data-session bootstrap accepted; server payload={len(body)} bytes; suffix={ticket[-8:].hex()}')
        for seq,code in enumerate(args.codes,1):
            sock.sendall(request_1m(seq,code))
            h,body,raw=recv_response(sock)
            op=struct.unpack_from('<H',h,10)[0]
            if op!=0x0fcd or h[5]!=seq: raise RuntimeError(f'{code}: response mismatch op={op:04x} seq={h[5]}')
            bars=parse_bars(body)
            print(f'{code}: {len(bars)} bars, day markers {bars[0][0]}..{bars[-1][0]}')
            rows.extend((code,*bar) for bar in bars)
    out=Path(args.out)
    with out.open('w',newline='',encoding='utf-8') as f:
        w=csv.writer(f);w.writerow(['code','day_marker','minute','open','high','low','close','amount','volume','reserved']);w.writerows(rows)
    print(f'saved {len(rows)} bars -> {out.resolve()}')

if __name__=='__main__': main()
