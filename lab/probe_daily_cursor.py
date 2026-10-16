#!/usr/bin/env python3
"""Probe daily cursor semantics to maximize history depth."""
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


def query_daily(sock, seq, code, market, cs, ce):
    req = (bytes((0x0c, seq & 0xff, 0x38, 0x8d, 0, 1))
           + struct.pack('<HHH', 0x14, 0x14, 0x0fcd)
           + struct.pack('<H', market) + code.encode()
           + struct.pack('<IIH', cs, ce, 0x0004))
    sock.sendall(req)
    h, body = recv_response(sock)
    if len(body) < 6 or (len(body) - 6) % 32:
        return 0, None, None
    nb = (len(body) - 6) // 32
    first_day = struct.unpack_from('<H', body, 6)[0]
    last_day = struct.unpack_from('<H', body, 6 + 32 * (nb - 1))[0]
    first_close = struct.unpack_from('<f', body, 6 + 16)[0]
    last_close = struct.unpack_from('<f', body, 6 + 32 * (nb - 1) + 16)[0]
    return nb, (first_day, first_close), (last_day, last_close)


with socket.create_connection((HOST, PORT), timeout=15) as sock:
    sock.settimeout(30)
    sock.sendall(OP11)
    recv_response(sock)

    seq = 1
    # Try different cursor ranges for daily
    ranges = [
        (0, 0xFFFFFFFF, 'full-range'),
        (0x00000000, 0x0000FFFF, 'low-16bit'),
        (0x00000000, 0x00002710, 'low-10000'),
        (9000, 10100, '9000-10100'),
        (9500, 10100, '9500-10100'),
        (9900, 10100, '9900-10100'),
        (10000, 10100, '10000-10100'),
        (10050, 10100, '10050-10100'),
        (10080, 10100, '10080-10100'),
        # Also test the minute cursor range
        (0x01352700, 0x01352769, 'minute-range'),
        # Try raw day indices
        (1, 10100, '1-10100'),
        (5000, 10100, '5000-10100'),
        (8000, 10100, '8000-10100'),
    ]

    for cs, ce, label in ranges:
        seq += 1
        try:
            nb, first, last = query_daily(sock, seq, '000001', 0, cs, ce)
            print(f'{label:>15} (0x{cs:08x}..0x{ce:08x}): {nb:>4} bars  first={first}  last={last}')
        except Exception as e:
            print(f'{label:>15}: ERROR {e}')
            try: sock.close()
            except: pass
            sock = socket.create_connection((HOST, PORT), timeout=15)
            sock.settimeout(30)
            sock.sendall(OP11)
            recv_response(sock)
            seq = 1
