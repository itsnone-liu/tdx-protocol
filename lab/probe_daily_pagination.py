#!/usr/bin/env python3
"""Find cursor ranges that maximize daily history depth."""
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


def query_daily(sock, seq, cs, ce):
    req = (bytes((0x0c, seq & 0xff, 0x38, 0x8d, 0, 1))
           + struct.pack('<HHH', 0x14, 0x14, 0x0fcd)
           + struct.pack('<H', 0) + b'000001'
           + struct.pack('<IIH', cs, ce, 0x0004))
    sock.sendall(req)
    h, body = recv_response(sock)
    nb = (len(body) - 6) // 32 if len(body) >= 38 and (len(body) - 6) % 32 == 0 else 0
    if nb == 0:
        return 0, None, None
    d1, o1 = struct.unpack_from('<I2I', body, 6)[:2]
    d2, c2 = struct.unpack_from('<I4I', body, 6 + 32*(nb-1))[:2], struct.unpack_from('<I4I', body, 6 + 32*(nb-1))[4]
    return nb, (d1, o1/100), (d2, c2/100)


with socket.create_connection((HOST, PORT), timeout=15) as sock:
    sock.settimeout(30)
    sock.sendall(OP11)
    recv_response(sock)

    seq = 1
    # Systematically test cursor end values with fixed start
    tests = [
        # Known working
        (0x01352700, 0x01352769),
        # Extend end upward
        (0x01352700, 0x01352770),
        (0x01352700, 0x01352780),
        (0x01352700, 0x01352800),
        (0x01352700, 0x01353000),
        (0x01352700, 0x01400000),
        # Extend start downward
        (0x01352600, 0x01352769),
        (0x01352500, 0x01352769),
        (0x01352000, 0x01352769),
        (0x01350000, 0x01352769),
        (0x01340000, 0x01352769),
        (0x01300000, 0x01352769),
        # Try wider range both ways
        (0x01300000, 0x01400000),
        (0x01000000, 0x02000000),
        # Try much lower start
        (0x00000000, 0x01352769),
        (0x00800000, 0x01352769),
        (0x01000000, 0x01352769),
        # Binary search around known values
        (0x01352500, 0x01352800),
        (0x01352000, 0x01353000),
    ]

    for cs, ce in tests:
        seq += 1
        try:
            nb, first, last = query_daily(sock, seq, cs, ce)
            if nb > 0:
                print(f'(0x{cs:08x}..0x{ce:08x}): {nb:>5} bars  {first[0]} ({first[1]:.2f}) → {last[0]} ({last[1]:.2f})')
            else:
                print(f'(0x{cs:08x}..0x{ce:08x}): EMPTY')
        except Exception as e:
            print(f'(0x{cs:08x}..0x{ce:08x}): ERROR {type(e).__name__}')
            try: sock.close()
            except: pass
            sock = socket.create_connection((HOST, PORT), timeout=15)
            sock.settimeout(30)
            sock.sendall(OP11)
            recv_response(sock)
            seq = 1
