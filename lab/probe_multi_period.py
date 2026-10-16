#!/usr/bin/env python3
"""Test which free periods work via op11+op4045 without account login."""
import secrets, socket, struct, time, zlib
from pathlib import Path

HOST, PORT = '175.178.112.197', 7709
LAB = Path(__file__).resolve().parent
OP11 = (LAB / 'op11_template.bin').read_bytes() + secrets.token_bytes(8)

# Known period tail values from captures and prior experiments
PERIODS = {
    '5m': 0x0000,
    '1m': 0x0007,
    'daily': 0x0004,   # seen in fresh c1 daily requests
    '15m': 0x0005,     # hypothesis
    '30m': 0x0006,     # hypothesis
    '60m': 0x0001,     # hypothesis from pytdx mapping
    '1m_alt': 0x0008,  # hypothesis
}

# Also try standard pytdx category numbers as raw u16
for cat in range(0, 16):
    name = f'cat{cat:02d}'
    if name not in PERIODS:
        PERIODS[name] = cat

CODES = ['000001', '600000', '159919']  # SZ stock, SH stock, SZ ETF


def recv_exact(sock, n):
    out = bytearray()
    while len(out) < n:
        part = sock.recv(n - len(out))
        if not part:
            raise ConnectionError(f'closed with {n - len(out)} left')
        out.extend(part)
    return bytes(out)


def recv_response(sock):
    hdr = recv_exact(sock, 16)
    zlen, rawlen = struct.unpack_from('<HH', hdr, 12)
    payload = recv_exact(sock, zlen)
    try:
        body = zlib.decompress(payload) if payload[:1] == b'\x78' else payload
    except zlib.error:
        body = payload
    return hdr, body, rawlen


def main():
    results = {}
    with socket.create_connection((HOST, PORT), timeout=15) as sock:
        sock.settimeout(30)
        sock.sendall(OP11)
        h, body, _ = recv_response(sock)
        op = struct.unpack_from('<H', h, 10)[0]
        if op != 0x000B:
            print(f'op11 rejected: op={op:04x}')
            return

        seq = 1
        for period_name, period_val in sorted(PERIODS.items(), key=lambda x: x[1]):
            for code in CODES:
                market = 0
                if code.startswith('6'):
                    market = 1  # SH
                req = (bytes((0x0c, seq & 0xff, 0x38, 0x8d, 0, 1))
                       + struct.pack('<HHH', 0x14, 0x14, 0x0fcd)
                       + b'\x00\x00' + code.encode('ascii')
                       + struct.pack('<IIH', 0x01352700, 0x01352769, period_val))
                try:
                    sock.sendall(req)
                    h, body, rawlen = recv_response(sock)
                    resp_op = struct.unpack_from('<H', h, 10)[0]
                    seq += 1
                    n_bars = 0
                    if len(body) >= 6 and (len(body) - 6) % 32 == 0:
                        n_bars = (len(body) - 6) // 32
                    else:
                        n_bars = len(body)
                    status = 'OK' if n_bars > 0 else 'EMPTY/SHORT'
                    if resp_op != 0x0fcd:
                        status = f'WRONG_OP_{resp_op:04x}'
                    results[(period_name, code)] = (status, n_bars, len(body))
                    print(f'{period_name:>8} (0x{period_val:04x}) {code}: {status} bars={n_bars} body={len(body)}B')
                except Exception as e:
                    results[(period_name, code)] = ('ERROR', 0, str(e))
                    print(f'{period_name:>8} (0x{period_val:04x}) {code}: ERROR {e}')
                    # reconnect
                    try:
                        sock.close()
                    except:
                        pass
                    sock = socket.create_connection((HOST, PORT), timeout=15)
                    sock.settimeout(30)
                    sock.sendall(OP11)
                    recv_response(sock)
                    seq = 1

    # Summary: which periods work for all codes
    print('\n--- Summary ---')
    by_period = {}
    for (pname, code), (status, nb, info) in results.items():
        by_period.setdefault(pname, []).append((code, status, nb))
    for pname in sorted(by_period.keys()):
        entries = by_period[pname]
        all_ok = all(s == 'OK' for _, s, _ in entries)
        bars = [nb for _, s, nb in entries if s == 'OK']
        print(f'{pname:>8}: {"ALL OK" if all_ok else "MIXED"}  bars={bars}')


if __name__ == '__main__':
    main()
