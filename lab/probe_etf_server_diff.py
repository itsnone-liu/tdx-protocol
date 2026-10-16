#!/usr/bin/env python3
"""Check which codes work on which servers."""
import secrets, socket, struct, time, zlib
from pathlib import Path

LAB = Path(__file__).resolve().parent
OP11 = (LAB / 'op11_template.bin').read_bytes() + secrets.token_bytes(8)
SERVERS = [('175.178.112.197', 7709), ('121.36.225.169', 7709), ('124.223.163.242', 7709)]
CODES = [
    ('000001', 0, 'SZ-stock'), ('600000', 1, 'SH-stock'),
    ('159919', 0, 'SZ-ETF'), ('510300', 1, 'SH-ETF'),
    ('000016', 0, 'SZ-ETF-2'), ('510050', 1, 'SH-ETF-2'),
    ('300750', 0, 'SZ-GEM'), ('688981', 1, 'SH-STAR'),
    ('000858', 0, 'SZ-Moutai'), ('601318', 1, 'SH-PingAn'),
]


def recv_exact(sock, n):
    buf = bytearray()
    while len(buf) < n:
        chunk = sock.recv(n - len(buf))
        if not chunk: raise ConnectionError('closed')
        buf.extend(chunk)
    return bytes(buf)


def recv_response(sock):
    hdr = recv_exact(sock, 16)
    zlen, _ = struct.unpack_from('<HH', hdr, 12)
    payload = recv_exact(sock, zlen)
    try: body = zlib.decompress(payload) if payload[:1] == b'\x78' else payload
    except zlib.error: body = payload
    return hdr, body


for host, port in SERVERS:
    print(f'\n--- {host}:{port} ---')
    try:
        sock = socket.create_connection((host, port), timeout=10)
        sock.settimeout(20)
        sock.sendall(OP11)
        h, b = recv_response(sock)
        if struct.unpack_from('<H', h, 10)[0] != 0x000B:
            print('op11 rejected'); continue

        seq = 1
        for code, mkt, label in CODES:
            req = (bytes((0x0c, seq & 0xff, 0x38, 0x8d, 0, 1))
                   + struct.pack('<HHH', 0x14, 0x14, 0x0fcd)
                   + struct.pack('<H', mkt) + code.encode()
                   + struct.pack('<IIH', 0x01352700, 0x01352769, 0x0007))
            try:
                sock.sendall(req)
                h, b = recv_response(sock)
                seq += 1
                nb = (len(b) - 6) // 32 if len(b) >= 6 and (len(b) - 6) % 32 == 0 else 0
                print(f'  {code} {label:>12}: {nb:>4} bars')
            except Exception as e:
                print(f'  {code} {label:>12}: ERROR {e}')
                try: sock.close()
                except: pass
                sock = socket.create_connection((host, port), timeout=10)
                sock.settimeout(20)
                sock.sendall(OP11)
                recv_response(sock)
                seq = 1
        sock.close()
    except Exception as e:
        print(f'  Connection failed: {e}')
