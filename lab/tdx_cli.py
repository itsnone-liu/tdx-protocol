#!/usr/bin/env python3
"""TDX market data CLI — pure Python stdlib, no login, no TdxW, Ubuntu-ready.

Supports: 1m, 5m, daily (paginated) for SZ/SH stocks, ETFs, GEM, STAR.
Usage:
  python tdx_cli.py 000001 600000 --period 1m
  python tdx_cli.py 000001 --period daily --out daily.csv
  python tdx_cli.py --codes-file codes.txt --periods 1m,daily --workers 4
"""
import argparse, csv, secrets, socket, struct, sys, threading, time, zlib
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

# ---------------------------------------------------------------------------
# Server pool (48 hosts from stock connect.cfg)
# ---------------------------------------------------------------------------
SERVERS = [
    ('110.41.147.114', 7709), ('110.41.2.72', 7709), ('101.33.225.16', 7709),
    ('175.178.112.197', 7709), ('175.178.128.227', 7709), ('43.139.95.83', 7709),
    ('124.223.163.242', 7709), ('122.51.120.217', 7709), ('150.158.160.2', 7709),
    ('123.60.164.122', 7709), ('111.229.247.189', 7709), ('124.70.199.56', 7709),
    ('62.234.50.143', 7709), ('81.70.151.186', 7709), ('82.156.214.79', 7709),
    ('159.75.29.111', 7709), ('43.139.18.171', 7709), ('81.71.32.47', 7709),
    ('122.51.232.182', 7709), ('118.25.98.114', 7709), ('121.36.225.169', 7709),
    ('123.60.70.228', 7709), ('123.60.73.44', 7709), ('124.70.133.119', 7709),
    ('124.71.187.72', 7709), ('124.71.187.122', 7709), ('119.97.185.59', 7709),
    ('129.204.230.128', 7709), ('101.42.240.54', 7709), ('124.71.9.153', 7709),
    ('123.60.84.66', 7709), ('111.230.186.52', 7709), ('101.43.159.194', 7709),
    ('120.53.8.251', 7709), ('152.136.191.169', 7709), ('116.205.163.254', 7709),
    ('116.205.171.132', 7709), ('116.205.183.150', 7709), ('49.232.15.141', 7709),
    ('82.156.174.84', 7709), ('101.42.164.241', 7709), ('101.35.121.35', 7709),
    ('111.231.113.208', 7709), ('43.136.95.205', 7709), ('43.136.96.138', 7709),
    ('101.33.244.209', 7709), ('106.53.63.234', 7709), ('119.91.226.89', 7709),
]

_LAB = Path(__file__).resolve().parent
OP11_TEMPLATE = (_LAB / 'op11_template.bin').read_bytes()

PERIOD_CODES = {'1m': 0x0007, '5m': 0x0000, 'daily': 0x0004}
# Cursor windows calibrated from experiments
CURSOR_RECENT = (0x01352700, 0x01353000)  # ~Jun 2026 → today (daily)
CURSOR_MINUTE = (0x01352700, 0x01352769)  # ~5 trading days (1m/5m)
MAX_BARS_PER_QUERY = 1000


def market_of(code):
    """SH=1 for codes starting with 5 (ETF) or 6 (stock/STAR); SZ=0 for 0/1/3."""
    return 1 if code[0] in '56' else 0


# ---------------------------------------------------------------------------
# Low-level protocol
# ---------------------------------------------------------------------------
def _recv_exact(sock, n):
    buf = bytearray()
    while len(buf) < n:
        chunk = sock.recv(n - len(buf))
        if not chunk:
            raise ConnectionError(f'peer closed ({len(buf)}/{n})')
        buf.extend(chunk)
    return bytes(buf)


def _recv_response(sock):
    hdr = _recv_exact(sock, 16)
    zlen, _ = struct.unpack_from('<HH', hdr, 12)
    payload = _recv_exact(sock, zlen)
    try:
        body = zlib.decompress(payload) if payload[:1] == b'\x78' else payload
    except zlib.error:
        body = payload
    return hdr, body


def _make_4045(seq, market, code, cursor_start, cursor_end, period):
    return (bytes((0x0c, seq & 0xff, 0x38, 0x8d, 0x00, 0x01))
            + struct.pack('<HHH', 0x14, 0x14, 0x0fcd)
            + struct.pack('<H', market) + code.encode('ascii')
            + struct.pack('<IIH', cursor_start, cursor_end, period))


def _parse_minute_bars(body):
    """Parse 1m/5m bars: u16 day, u16 minute, 5×f32, 2×u32."""
    if len(body) < 6 or (len(body) - 6) % 32:
        return []
    bars = []
    for off in range(6, len(body), 32):
        day, minute = struct.unpack_from('<HH', body, off)
        o, h, l, c, amt = struct.unpack_from('<5f', body, off + 4)
        vol, _ = struct.unpack_from('<II', body, off + 24)
        bars.append((day * 100000 + minute, o, h, l, c, amt, vol))
    return bars


def _parse_daily_bars(body):
    """Parse daily bars: u32 date(YYYYMMDD), 4×u32 prices×100, f32 amt, u32 vol, u32 reserved."""
    if len(body) < 6 or (len(body) - 6) % 32:
        return []
    bars = []
    for off in range(6, len(body), 32):
        date, o_raw, h_raw, l_raw, c_raw = struct.unpack_from('<5I', body, off)
        amt, = struct.unpack_from('<f', body, off + 20)
        vol, _ = struct.unpack_from('<II', body, off + 24)
        bars.append((date, o_raw / 100.0, h_raw / 100.0, l_raw / 100.0, c_raw / 100.0, amt, vol))
    return bars


# ---------------------------------------------------------------------------
# Server selection
# ---------------------------------------------------------------------------
def _probe_one(host, port, timeout=3.0):
    try:
        t0 = time.monotonic()
        s = socket.create_connection((host, port), timeout=timeout)
        dt = (time.monotonic() - t0) * 1000
        s.close()
        return dt
    except OSError:
        return None


def select_best_servers(n=5, timeout=3.0):
    with ThreadPoolExecutor(max_workers=16) as pool:
        futs = {pool.submit(_probe_one, h, p, timeout): (h, p) for h, p in SERVERS}
        results = []
        for fut in as_completed(futs):
            h, p = futs[fut]
            ms = fut.result()
            if ms is not None:
                results.append((h, p, ms))
    results.sort(key=lambda x: x[2])
    return results[:n]


# ---------------------------------------------------------------------------
# Data session
# ---------------------------------------------------------------------------
class DataSession:
    def __init__(self, host, port):
        self.host, self.port = host, port
        self.sock = None
        self.seq = 0
        self._connect()

    def _connect(self):
        self.sock = socket.create_connection((self.host, self.port), timeout=15)
        self.sock.settimeout(30)
        self.sock.sendall(OP11_TEMPLATE + secrets.token_bytes(8))
        hdr, _ = _recv_response(self.sock)
        if struct.unpack_from('<H', hdr, 10)[0] != 0x000B:
            raise RuntimeError(f'op11 rejected by {self.host}')
        self.seq = 0

    def _ensure(self):
        if self.sock is None:
            self._connect()
            return
        try:
            self.sock.getpeername()
        except OSError:
            self._connect()

    def fetch(self, code, period, cursor=None):
        """Fetch one batch. Returns list of (time_key, o, h, l, c, amt, vol)."""
        self._ensure()
        if cursor:
            cs, ce = cursor
        elif period == 'daily':
            cs, ce = CURSOR_RECENT
        else:
            cs, ce = CURSOR_MINUTE

        pcode = PERIOD_CODES[period]
        mkt = market_of(code)

        for retry in range(3):
            try:
                self.seq = (self.seq + 1) & 0xff or 1
                req = _make_4045(self.seq, mkt, code, cs, ce, pcode)
                self.sock.sendall(req)
                hdr, body = _recv_response(self.sock)
                if struct.unpack_from('<H', hdr, 10)[0] != 0x0fcd:
                    raise RuntimeError(f'unexpected opcode')
                parser = _parse_daily_bars if period == 'daily' else _parse_minute_bars
                return parser(body)
            except (OSError, ConnectionError, RuntimeError):
                if retry == 2:
                    raise
                try: self.sock.close()
                except OSError: pass
                self.sock = None
                time.sleep(0.3 * (retry + 1))
                self._connect()

    def fetch_full(self, code, period, max_bars=10000):
        """Fetch data; daily paginates from present backwards. Returns most recent bars."""
        if period != 'daily':
            return self.fetch(code, period)

        # Daily: fetch latest batch first, then paginate backwards
        all_bars = []
        seen = set()

        # Step 1: get latest data using narrow recent cursor
        batch = self.fetch(code, 'daily')
        for b in batch:
            if b[0] not in seen:
                seen.add(b[0])
                all_bars.append(b)

        # Step 2: if need more, widen cursor window progressively
        # Each step goes back further in history
        cursor_end = 0x01352700  # ~June 2026
        while len(all_bars) < max_bars:
            batch = self.fetch(code, 'daily', cursor=(0x00000000, cursor_end))
            new = [b for b in batch if b[0] not in seen]
            if not new:
                break
            for b in new:
                seen.add(b[0])
                all_bars.append(b)
            if len(batch) < MAX_BARS_PER_QUERY:
                break
            # Step back ~3 years per page
            cursor_end = max(0x01000000, cursor_end - 0x00140000)

        all_bars.sort(key=lambda b: b[0])
        return all_bars[-max_bars:] if max_bars < len(all_bars) else all_bars

    def close(self):
        if self.sock:
            try: self.sock.close()
            except OSError: pass
            self.sock = None


# ---------------------------------------------------------------------------
# Batch download
# ---------------------------------------------------------------------------
def batch_download(codes, periods, host, port, workers=3, fallback_servers=None):
    all_rows = []
    errors = []
    tasks = [(code, period) for period in periods for code in codes]
    sessions = {}
    lock = threading.Lock()
    fallbacks = fallback_servers or []

    def get_session(h=None, p=None):
        tid = threading.current_thread().ident
        hh, pp = h or host, p or port
        with lock:
            key = (tid, hh, pp)
            if key not in sessions or sessions[key] is None:
                sessions[key] = DataSession(hh, pp)
            return sessions[key]

    def worker(task):
        code, period = task
        for attempt in range(3):
            try:
                sess = get_session()
                bars = sess.fetch_full(code, period)
                if bars:
                    return code, period, bars
                # If empty, try fallback server
                for fb_host, fb_port in fallbacks[:2]:
                    try:
                        fb_sess = get_session(fb_host, fb_port)
                        bars = fb_sess.fetch_full(code, period)
                        if bars:
                            return code, period, bars
                    except Exception:
                        continue
                return code, period, bars  # return empty even if all servers fail
            except Exception:
                with lock:
                    tid = threading.current_thread().ident
                    for k in list(sessions.keys()):
                        if k[0] == tid and sessions[k]:
                            try: sessions[k].close()
                            except Exception: pass
                            sessions[k] = None
                time.sleep(0.3 * (attempt + 1))
        raise RuntimeError(f'all retries failed')

    with ThreadPoolExecutor(max_workers=workers) as pool:
        futs = {pool.submit(worker, t): t for t in tasks}
        for fut in as_completed(futs):
            code, period = futs[fut]
            try:
                _, _, bars = fut.result()
                print(f'  {code} {period}: {len(bars)} bars')
                for bar in bars:
                    all_rows.append((code, period, *bar))
            except Exception as e:
                print(f'  {code} {period}: ERROR {e}', file=sys.stderr)
                errors.append((code, period, str(e)))

    with lock:
        for s in sessions.values():
            if s:
                try: s.close()
                except Exception: pass
    return all_rows, errors


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    ap = argparse.ArgumentParser(description='TDX market data CLI (no login required)')
    ap.add_argument('codes', nargs='*', help='stock codes (000001 600000 ...)')
    ap.add_argument('--codes-file', help='file with one code per line')
    ap.add_argument('--period', default='1m', choices=list(PERIOD_CODES))
    ap.add_argument('--periods', help='comma-separated (1m,5m,daily)')
    ap.add_argument('--out', default='tdx_data.csv')
    ap.add_argument('--host', help='override server host')
    ap.add_argument('--workers', type=int, default=3)
    ap.add_argument('--probe', action='store_true', help='only show latency ranking')
    args = ap.parse_args()

    codes = list(args.codes)
    if args.codes_file:
        codes.extend(Path(args.codes_file).read_text().strip().splitlines())
    if not codes:
        codes = ['000001', '600000']
    codes = [c.strip() for c in codes if c.strip()]

    periods = args.periods.split(',') if args.periods else [args.period]
    periods = [p.strip() for p in periods if p.strip() in PERIOD_CODES]

    if args.host:
        host, port = args.host, 7709
        print(f'Server: {host}:{port} (specified)')
    else:
        print('Probing 48 servers...')
        top = select_best_servers()
        for h, p, ms in top:
            print(f'  {h}:{p} — {ms:.0f}ms')
        host, port, _ = top[0]
        print(f'Selected: {host}:{port}')

    if args.probe:
        return

    print(f'Downloading {len(codes)} codes × {len(periods)} periods ({args.workers} workers)...')
    t0 = time.time()
    rows, errors = batch_download(codes, periods, host, port, workers=args.workers,
                                   fallback_servers=top[1:3] if not args.host else [])
    dt = time.time() - t0

    out = Path(args.out)
    with out.open('w', newline='', encoding='utf-8') as f:
        w = csv.writer(f)
        w.writerow(['code', 'period', 'time_key', 'open', 'high', 'low', 'close', 'amount', 'volume'])
        w.writerows(rows)

    print(f'Done: {len(rows)} bars in {dt:.1f}s ({len(rows)/dt:.0f} bars/s) → {out.resolve()}')
    if errors:
        print(f'WARNING: {len(errors)} tasks failed', file=sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    main()
