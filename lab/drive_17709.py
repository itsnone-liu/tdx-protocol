#!/usr/bin/env python3
"""1016 lab · drive_17709.py — wait for 17709, then fetch 10 stocks x 1-minute bars.

Drives the ISOLATED tdx-tq-v773 client's local HTTP data plane so the wire
traffic (login channel) carries minute-line data while netmon records endpoints.

Stdlib only. Writes lab/out/drive_<stamp>.json with per-request latency.
"""
import json
import socket
import sys
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

URL = "http://127.0.0.1:17709/"
STOCKS = [
    "600519.SH", "000001.SZ", "600036.SH", "000858.SZ", "601318.SH",
    "300750.SZ", "002594.SZ", "600900.SH", "000333.SZ", "601898.SH",
]
PERIOD_CANDIDATES = ["1m"]  # tqcenter.py L1161 valid_periods; '1min' returns period error
COUNT = 240


def post(method: str, params: dict, req_id: int, timeout: float = 90.0):
    body = json.dumps({"id": req_id, "method": method, "params": params}).encode()
    req = urllib.request.Request(URL, data=body, headers={"Content-Type": "application/json"})
    t0 = time.perf_counter()
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        raw = resp.read()
    dt = time.perf_counter() - t0
    return dt, raw


def wait_port(host="127.0.0.1", port=17709, timeout_s=180.0):
    t0 = time.time()
    while time.time() - t0 < timeout_s:
        try:
            with socket.create_connection((host, port), timeout=2):
                return True
        except OSError:
            time.sleep(2.0)
    return False


def main() -> int:
    out_dir = Path(__file__).resolve().parent / "out"
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    log = {
        "started_at": datetime.now(timezone.utc).isoformat(),
        "port_up_s": None,
        "period_probe": [],
        "requests": [],
    }

    t0 = time.time()
    up = wait_port()
    log["port_up_s"] = round(time.time() - t0, 1) if up else None
    if not up:
        log["error"] = "17709 did not open within timeout (login may be stuck)"
        (out_dir / f"drive_{stamp}.json").write_text(
            json.dumps(log, ensure_ascii=False, indent=2), encoding="utf-8")
        print(json.dumps(log, ensure_ascii=False))
        return 2

    # probe which period token works for minute bars
    period_ok = None
    for cand in PERIOD_CANDIDATES:
        try:
            dt, raw = post("get_market_data", {
                "stock_list": ["600519.SH"], "count": 5,
                "dividend_type": "none", "period": cand}, 1)
            parsed = json.loads(raw)
            ok = (isinstance(parsed.get("result"), dict)
                  and "Error" not in parsed["result"]
                  and "error" not in parsed["result"])
            log["period_probe"].append({"period": cand, "latency_s": round(dt, 3),
                                        "sample": str(parsed)[:300]})
            if ok:
                period_ok = cand
                break
        except Exception as e:  # noqa: BLE001
            log["period_probe"].append({"period": cand, "exception": repr(e)[:200]})
    if period_ok is None:
        period_ok = "1m"  # proceed anyway; per-request errors will be visible
    log["period_used"] = period_ok

    for i, code in enumerate(STOCKS, start=10):
        try:
            dt, raw = post("get_market_data", {
                "stock_list": [code], "count": COUNT,
                "dividend_type": "none", "period": period_ok}, i)
            parsed = json.loads(raw)
            n = None
            try:
                data = parsed.get("result") or parsed.get("data")
                if isinstance(data, dict):
                    for v in data.values():
                        if isinstance(v, list):
                            n = len(v)
                            break
                elif isinstance(data, list):
                    n = len(data)
            except Exception:  # noqa: BLE001
                pass
            log["requests"].append({"code": code, "latency_s": round(dt, 3),
                                    "bars": n, "bytes": len(raw),
                                    "err": parsed.get("error") if isinstance(parsed, dict) else None})
        except Exception as e:  # noqa: BLE001
            log["requests"].append({"code": code, "exception": repr(e)[:200]})
        time.sleep(0.4)

    lat = [r["latency_s"] for r in log["requests"] if "latency_s" in r]
    if lat:
        log["summary"] = {"n_ok": len(lat), "min_s": round(min(lat), 3),
                          "median_s": round(sorted(lat)[len(lat)//2], 3),
                          "max_s": round(max(lat), 3)}
    log["finished_at"] = datetime.now(timezone.utc).isoformat()
    path = out_dir / f"drive_{stamp}.json"
    path.write_text(json.dumps(log, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(log.get("summary", {}), ensure_ascii=False))
    print(f"LOG {path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
