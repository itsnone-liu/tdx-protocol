#!/usr/bin/env python3
"""1016 lab · patch_connect_cfg.py — point [HQHOST] of the isolated TDX client
at the local recording proxy (single host 127.0.0.1:7709), keeping GBK encoding
and every other section byte-identical. Original backed up as connect.cfg.bak_orig.
"""
import re
import sys
from pathlib import Path

CFG = Path(r"D:\tdx-node\tdx-tq-v773\connect.cfg")

text = CFG.read_bytes().decode("gbk")
m = re.search(r"\[HQHOST\]\r\n(.*?)\r\n\r\n(?=\[)", text, re.S)
if not m:
    sys.exit("HQHOST section not found")
new_hq = ("[HQHOST]\r\n"
          "HostNum=1\r\n"
          "PrimaryHost=0\r\n"
          "\r\n"
          "HostName01=1016rec\r\n"
          "IPAddress01=127.0.0.1\r\n"
          "Port01=7709\r\n")
text = text[:m.start()] + new_hq + text[m.end():]
CFG.write_bytes(text.encode("gbk"))
print("patched: HQHOST -> 127.0.0.1:7709 (single host)")
