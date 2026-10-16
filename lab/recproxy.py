#!/usr/bin/env python3
"""1016 lab · recproxy.py — bidirectional recording TCP proxy for TDX 7709.

Listens on 127.0.0.1:LISTEN, forwards to UPSTREAM, records every byte in both
directions per connection with timestamps:

  out/rec_<stamp>/meta.json          connection index
  out/rec_<stamp>/c<N>_c2s.bin       client->server raw bytes
  out/rec_<stamp>/c<N>_s2c.bin       server->client raw bytes
  out/rec_<stamp>/c<N>_events.jsonl  {t_ms, dir, offset, len} per TCP segment

Pure stdlib (asyncio). Ctrl-C or SIGTERM to stop (flushes files).
"""
import asyncio
import json
import signal
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

LISTEN = ("127.0.0.1", 7709)
UPSTREAM = ("175.178.112.197", 7709)


class Session:
    def __init__(self, root: Path, idx: int):
        self.idx = idx
        self.c2s = open(root / f"c{idx}_c2s.bin", "ab")
        self.s2c = open(root / f"c{idx}_s2c.bin", "ab")
        self.events = open(root / f"c{idx}_events.jsonl", "a", encoding="utf-8")
        self.n_c2s = 0
        self.n_s2c = 0
        self.t0 = time.time()

    def note(self, direction: str, data: bytes):
        now_ms = int((time.time() - self.t0) * 1000)
        if direction == "c2s":
            off = self.n_c2s
            self.n_c2s += len(data)
            self.c2s.write(data)
        else:
            off = self.n_s2c
            self.n_s2c += len(data)
            self.s2c.write(data)
        self.events.write(json.dumps(
            {"t_ms": now_ms, "dir": direction, "off": off, "len": len(data)}) + "\n")
        self.events.flush()

    def close(self):
        for f in (self.c2s, self.s2c, self.events):
            try:
                f.flush()
                f.close()
            except Exception:
                pass


async def pipe(reader, writer, session: Session, direction: str):
    try:
        while True:
            data = await reader.read(65536)
            if not data:
                break
            session.note(direction, data)
            writer.write(data)
            await writer.drain()
    except Exception as e:  # noqa: BLE001
        sys.stderr.write(f"[pipe {direction}] {e!r}\n")
    finally:
        try:
            writer.close()
        except Exception:
            pass


async def handle(client_reader, client_writer, root: Path, counter):
    idx = counter[0]
    counter[0] += 1
    print(f"[conn {idx}] opened", flush=True)
    try:
        upstream_reader, upstream_writer = await asyncio.open_connection(*UPSTREAM)
    except Exception as e:  # noqa: BLE001
        print(f"[conn {idx}] upstream fail: {e!r}", flush=True)
        client_writer.close()
        return
    session = Session(root, idx)
    meta_path = root / "meta.json"
    tasks = [
        asyncio.create_task(pipe(client_reader, upstream_writer, session, "c2s")),
        asyncio.create_task(pipe(upstream_reader, client_writer, session, "s2c")),
    ]
    await asyncio.gather(*tasks)
    session.close()
    meta = {}
    if meta_path.exists():
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
    meta[str(idx)] = {
        "opened_utc": datetime.now(timezone.utc).isoformat(),
        "bytes_c2s": session.n_c2s,
        "bytes_s2c": session.n_s2c,
    }
    meta_path.write_text(json.dumps(meta, indent=2), encoding="utf-8")
    print(f"[conn {idx}] closed c2s={session.n_c2s} s2c={session.n_s2c}", flush=True)


async def main():
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    root = Path(__file__).resolve().parent / "out" / f"rec_{stamp}"
    root.mkdir(parents=True, exist_ok=True)
    print(f"recproxy listening {LISTEN} -> {UPSTREAM}", flush=True)
    print(f"recording into {root}", flush=True)
    counter = [0]
    server = await asyncio.start_server(
        lambda r, w: handle(r, w, root, counter), *LISTEN)
    stop = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, stop.set)
        except NotImplementedError:
            pass
    async with server:
        await stop.wait()
    print("recproxy stopped", flush=True)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
