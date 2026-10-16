import hashlib
import re
from pathlib import Path

b = Path(r"D:\qjcNetDiskDownload\deepseek-harness\project\1016\lab\out\e3_bigdata_1.zip").read_bytes()
print("size", len(b), "md5", hashlib.md5(b).hexdigest())
for off in range(30000, len(b), 30000):
    seg = b[off:off + 6]
    flag = "<== UNSTRIPPED PREFIX!" if seg[:4] == bytes.fromhex("30750000") else ""
    print(f"@{off}: {seg.hex(' ')} {flag}")
locs = [m.start() for m in re.finditer(b"PK\x03\x04", b)]
cds = [m.start() for m in re.finditer(b"PK\x01\x02", b)]
end = [m.start() for m in re.finditer(b"PK\x05\x06", b)]
print("local headers:", locs[:12], "... total", len(locs))
print("central dirs:", cds[:12], "total", len(cds))
print("end records:", end)
