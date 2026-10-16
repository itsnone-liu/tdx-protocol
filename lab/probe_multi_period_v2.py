#!/usr/bin/env python3
"""Test free periods with correct market byte for SZ/SH/BJ."""
import secrets, socket, struct, zlib
from pathlib import Path

HOST, PORT = '175.178.112.197', 7709
LAB = Path(__file__).resolve().parent
OP11 = (LAB / 'op11_template.bin').read_bytes() + secrets.token_bytes(8)

PERIODS = {
    '5m': 0x0000,
    '1h': 0x0001,
    '15m': 0x0002,  # try pytdx-style
    '30m': 0x0003,  # try pytdx-style
    'daily': 0x0004,
    'weekly': 0x0005,
    'monthly': 0x0006,
    '1m': 0x0007,
    '1m_raw': 0x0008,
    'daily2': 0x0009,
    '3m': 0x000a,
}

TESTS = [
    # (code, market_u16, label)
    ('000001', 0, 'SZ-stock'),
    ('600000', 1, 'SH-stock'),
    ('159919', 0, 'SZ-ETF'),
    ('510300', 1, 'SH-ETF'),
    ('835174', 2, 'BJ-stock'),  # try BJ market=2
    ('835174', 0, 'BJ-as-SZ'),  # try BJ as market 0
]


def recv_exact(sock, n):
    out = bytearray()
    while len(out) < n:
        part = sock.recv(n - len(out))
        if not part: raise ConnectionError('closed')
        out.extend(part)
    return bytes(out)


def recv_response(sock):
    hdr = recv_exact(sock, 16)
    zlen, rawlen = struct.unpack_from('<HH', hdr, 12)
    payload = recv_exact(sock, zlen)
    try: body = zlib.decompress(payload) if payload[:1] == b'\x78' else payload
    except zlib.error: body = payload
    return hdr, body, rawlen


def main():
    with socket.create_connection((HOST, PORT), timeout=15) as sock:
        sock.settimeout(30)
        sock.sendall(OP11)
        h, body, _ = recv_response(sock)
        if struct.unpack_from('<H', h, 10)[0] != 0x000B:
            print('op11 rejected'); return

        seq = 1
        print(f'{"period":>8} {"market":>3} {"code":>8} {"label":>10} | {"bars":>5} {"body_B":>7} first_date  last_date')
        print('-' * 80)

        for pname, pval in sorted(PERIODS.items(), key=lambda x: x[1]):
            for code, market, label in TESTS:
                req = (bytes((0x0c, seq & 0xff, 0x38, 0x8d, 0, 1))
                       + struct.pack('<HHH', 0x14, 0x14, 0x0fcd)
                       + struct.pack('<H', market) + code.encode('ascii')
                       + struct.pack('<IIH', 0x01352700, 0x01352769, pval))
                try:
                    sock.sendall(req)
                    h, body, _ = recv_response(sock)
                    seq += 1
                    n_bars = (len(body) - 6) // 32 if len(body) >= 6 and (len(body) - 6) % 32 == 0 else 0
                    if n_bars > 0:
                        # decode first and last bar dates for context
                        off_first = 6
                        day1 = struct.unpack_from('<H', body, off_first)[0]
                        day2 = struct.unpack_from('<H', body, off_first + 32*(n_bars-1))[0]
                        print(f'{pname:>8} {market:>3} {code:>8} {label:>10} | {n_bars:>5} {len(body):>7} {day1:>10}  {day2:>10}')
                    else:
                        # show raw body hex for diagnosis
                        bh = body[:12].hex(' ') if len(body) <= 12 else body[:12].hex(' ') + '...'
                        print(f'{pname:>8} {market:>3} {code:>8} {label:>10} | {n_bars:>5} {len(body):>7} EMPTY {bh}')
                except Exception as e:
                    print(f'{pname:>8} {market:>3} {code:>8} {label:>10} | ERROR {e}')
                    try: sock.close()
                    except: pass
                    sock = socket.create_connection((HOST, PORT), timeout=15)
                    sock.settimeout(30)
                    sock.sendall(OP11)
                    recv_response(sock)
                    seq = 1


if __name__ == '__main__':
    main()
