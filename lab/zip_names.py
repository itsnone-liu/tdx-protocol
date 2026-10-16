import re
import struct
from pathlib import Path

b = Path(r"D:\qjcNetDiskDownload\deepseek-harness\project\1016\lab\out\e3_bigdata_1.zip").read_bytes()
# local header: PK\x03\x04 <ver><flag><method><time><date><crc><csize><usize><nlen><elen> name...
names = []
for m in re.finditer(b"PK\x03\x04", b):
    o = m.start()
    if o + 30 > len(b):
        continue
    nlen, elen = struct.unpack_from("<HH", b, o + 26)
    name = b[o + 30: o + 30 + nlen]
    csize, usize = struct.unpack_from("<II", b, o + 18)
    names.append((name.decode("gbk", "replace"), csize, usize))
print(f"entries: {len(names)}")
for n, cs, us in names[:30]:
    print(f"  {n}  c={cs} u={us}")
from collections import Counter
ext = Counter(n.rsplit(".", 1)[-1] if "." in n else n for n, _, _ in names)
print("extensions:", ext.most_common(10))
