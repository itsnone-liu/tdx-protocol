#!/usr/bin/env python3
"""Dump raw daily response bytes to identify bar format."""
import secrets, socket, struct, zlib
from pathlib import Path

LAB = Path(__file__).resolve().parent
OP11 = (LAB / 'op11_template.bin').read_bytes() + secrets.token_bytes(8)
HOST, PORT = '175.178.112.197', 7709


def recv_exact(sock, n):
    buf = bytearray()
    while len(buf) < n:
        c = sock.recv(n - len(buf))
        if not c: raise ConnectionError('closed')
        buf.extend(c)
    return bytes(buf)


def recv_response(sock):
    hdr = recv_exact(sock, 16)
    zlen, _ = struct.unpack_from('<HH', hdr, 12)
    p = recv_exact(sock, zlen)
    try: body = zlib.decompress(p)
    except zlib.error: body = p
    return hdr, body


with socket.create_connection((HOST, PORT), timeout=15) as sock:
    sock.settimeout(30)
    sock.sendall(OP11)
    recv_response(sock)

    # Query daily for 000001
    req = (bytes((0x0c, 1, 0x38, 0x8d, 0, 1))
           + struct.pack('<HHH', 0x14, 0x14, 0x0fcd)
           + struct.pack('<H', 0) + b'000001'
           + struct.pack('<IIH', 0x01352700, 0x01352769, 0x0004))
    sock.sendall(req)
    h, body = recv_response(sock)

    print(f'body len={len(body)}')
    print(f'header 6B: {body[:6].hex(" ")}')
    nb = (len(body) - 6) // 32
    print(f'bars: {nb}')

    # Dump first 3 and last 3 bars in raw hex
    for i in [0, 1, 2, nb-3, nb-2, nb-1]:
        if 0 <= i < nb:
            bar = body[6+i*32:6+(i+1)*32]
            print(f'\nbar[{i:2d}]: {bar.hex(" ")}')
            # Try different interpretations
            u16s = struct.unpack_from('<16H', bar)
            u32s = struct.unpack_from('<8I', bar)
            f32s = struct.unpack_from('<8f', bar)
            print(f'  u16: {u16s}')
            print(f'  u32: {u32s}')
            # Check if first u32 could be YYYYMMDD
            if u32s[0] > 19900000 and u32s[0] < 20310000:
                print(f'  date={u32s[0]}  open={u32s[1]/100:.2f} high={u32s[2]/100:.2f} low={u32s[3]/100:.2f} close={u32s[4]/100:.2f}')
                print(f'  amount={f32s[5]:.0f} vol={u32s[6]}')

    # Also dump first 3 bars of 1m for comparison
    req1m = (bytes((0x0c, 2, 0x38, 0x8d, 0, 1))
             + struct.pack('<HHH', 0x14, 0x14, 0x0fcd)
             + struct.pack('<H', 0) + b'000001'
             + struct.pack('<IIH', 0x01352700, 0x01352769, 0x0007))
    sock.sendall(req1m)
    h, body1m = recv_response(sock)
    print(f'\n--- 1m body first 3 bars ---')
    for i in range(3):
        bar = body1m[6+i*32:6+(i+1)*32]
        u16s = struct.unpack_from('<16H', bar)
        u32s = struct.unpack_from('<8I', bar)
        print(f'1m bar[{i}]: u16={u16s[:4]}  u32={u32s[:4]}')

    # Check local .day file for reference
    dayfile = Path(r'D:\tdx-node\tdx-tq-v773\vipdoc\sz\lday\sz000001.day')
    if dayfile.exists():
        raw = dayfile.read_bytes()
        print(f'\n--- local .day file (last 3 records) ---')
        for i in [-3, -2, -1]:
            rec = raw[i*32:(i+1)*32]
            u32s = struct.unpack_from('<8I', rec)
            f32s = struct.unpack_from('<8f', rec)
            print(f'local[{i}]: date={u32s[0]} o={u32s[1]/100:.2f} h={u32s[2]/100:.2f} l={u32s[3]/100:.2f} c={u32s[4]/100:.2f} amt={f32s[5]:.0f} vol={u32s[6]}')
