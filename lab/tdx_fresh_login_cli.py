#!/usr/bin/env python3
"""Independent TDX 1m CLI using a freshly captured desktop login prelude.

This replays only the 25 TdxW initialization/control requests from c1 (through
op0fde, before normal quote traffic); all server responses are obtained live.
It is a fresh-capture-assisted prototype, not yet a general login generator.
"""
import argparse, csv, socket, struct, zlib
from pathlib import Path

CAP = Path(__file__).resolve().parent / 'out' / 'rec_20261016T072253Z' / 'c1_c2s.bin'
HOST_DEFAULT, PORT_DEFAULT = '175.178.112.197', 7709
CODES_DEFAULT = ['000001','000002','000006','000007','000009','000010','000011','000012','000014','000016']
CURSOR_START, CURSOR_END = 0x01352764, 0x01352769


def parse_frames(data):
    frames=[]; off=0
    while off+12<=len(data):
        if data[off] != 0x0c:
            off+=1; continue
        n=10+struct.unpack_from('<H',data,off+6)[0]
        if n<12 or off+n>len(data):
            off+=1; continue
        f=data[off:off+n]
        op=struct.unpack_from('<H',f,10)[0]
        frames.append((off,f,op))
        off+=n
    return frames


def recv_exact(sock,n):
    buf=bytearray()
    while len(buf)<n:
        part=sock.recv(n-len(buf))
        if not part: raise ConnectionError(f'peer closed with {n-len(buf)} bytes outstanding')
        buf.extend(part)
    return bytes(buf)


def recv_response(sock):
    hdr=recv_exact(sock,16)
    if hdr[:4]!=bytes.fromhex('b1 cb 74 00'):
        raise ValueError('unexpected response header '+hdr.hex(' '))
    zlen,rawlen=struct.unpack_from('<HH',hdr,12)
    payload=recv_exact(sock,zlen)
    try: body=zlib.decompress(payload) if payload[:1]==b'\x78' else payload
    except zlib.error: body=payload
    return hdr,body,rawlen


def request_1m(seq,code,magic=0x8d):
    if len(code)!=6 or not code.isdigit(): raise ValueError(f'invalid stock code {code!r}')
    return (bytes((0x0c,seq&0xff,0x38,magic,0x00,0x01))
      +struct.pack('<HHH',0x14,0x14,0x0fcd)+b'\x00\x00'+code.encode('ascii')
      +struct.pack('<IIH',CURSOR_START,CURSOR_END,0x0007))


def parse_bars(body):
    if len(body)<6 or (len(body)-6)%32:
        raise ValueError(f'unexpected op4045 body size: {len(body)}')
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
    ap.add_argument('--capture',type=Path,default=CAP)
    ap.add_argument('--out',default='tdx_fresh_login_1m.csv')
    ap.add_argument('--magic',type=lambda s:int(s,0),default=0x8d)
    args=ap.parse_args()
    data=args.capture.read_bytes(); frames=parse_frames(data)
    init=[]
    for _,f,op in frames:
        if op in (0x0547,0x054c,0x0fcd): break
        init.append(f)
    if not init or struct.unpack_from('<H',init[0],10)[0]!=0x000b:
        raise SystemExit('capture does not begin with op11 init')
    if struct.unpack_from('<H',init[-1],10)[0]!=0x0fde:
        raise SystemExit('capture init no longer ends at op0fde; inspect capture before use')
    print(f'fresh captured prelude: {len(init)} client frames, {sum(map(len,init))} bytes')
    rows=[]
    with socket.create_connection((args.host,args.port),timeout=15) as sock:
        sock.settimeout(30)
        for idx,f in enumerate(init):
            sock.sendall(f);h,body,raw=recv_response(sock)
            op=struct.unpack_from('<H',h,10)[0]
            if h[5]!=f[1] or op!=struct.unpack_from('<H',f,10)[0]:
                raise RuntimeError(f'init response mismatch frame {idx}: req seq/op {f[1]}/{struct.unpack_from("<H",f,10)[0]:04x}, response {h[5]}/{op:04x}')
        print('fresh prelude accepted by live server')
        for seq,code in enumerate(args.codes,1):
            sock.sendall(request_1m(seq,code,args.magic))
            h,body,raw=recv_response(sock)
            op=struct.unpack_from('<H',h,10)[0]
            if op!=0x0fcd or h[5]!=seq:
                raise RuntimeError(f'{code}: response mismatch op={op:04x} seq={h[5]}')
            bars=parse_bars(body)
            print(f'{code}: {len(bars)} bars, day markers {bars[0][0]}..{bars[-1][0]}')
            rows.extend((code,*b) for b in bars)
    out=Path(args.out)
    with out.open('w',newline='',encoding='utf-8') as f:
        w=csv.writer(f);w.writerow(['code','day_marker','minute','open','high','low','close','amount','volume','reserved']);w.writerows(rows)
    print(f'saved {len(rows)} bars -> {out.resolve()}')

if __name__=='__main__': main()
