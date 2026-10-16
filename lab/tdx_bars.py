#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
tdx_bars.py — TDX op 0x052d (get_security_bars) 纯 stdlib 实现。

移植自 pytdx (MIT, Copyright rainx) 的 GetSecurityBarsCmd/helper，去依赖化：
  - struct/socket/zlib 之外零依赖
  - count-based 向后翻页：start=最新偏移，count≤800/页 —— 不依赖
    op4045 的绝对游标语义（该语义在云主站上不可靠，见 PROTOCOL.md）

报文格式（与 pytdx 抓包逐字节一致，已验证）:
  send: struct.pack('<HIHHHH6sHHHHIIH',
        0x10c, 0x01016408, 0x1c, 0x1c, 0x052d,
        market, code6s, category, 1, start, count, 0, 0, 0)
  recv: 16B 头(zlib帧) + u16 count + N×记录
  记录: 4B datetime | varint×4 价格差分 | f32 volume | f32 amount

category: 8=1分钟, 0=5分钟, 9=日K线（15/30/60分钟请从5m聚合，服务器不直接给）
"""
import struct

# ---------------------------------------------------------------- 构包

def make_052d(seq, market, code, category, start, count):
    values = (0x10c, 0x01016408, 0x1c, 0x1c, 0x052d,
              market, code.encode('ascii'), category, 1,
              start, count, 0, 0, 0)
    return struct.pack('<HIHHHH6sHHHHIIH', *values)


# ---------------------------------------------------------------- 解码

def _get_datetime(category, buf, pos):
    """分钟类: u16 zipday + u16 分钟; 日线类: u32 YYYYMMDD"""
    if category < 4 or category in (7, 8):
        zipday, tminutes = struct.unpack_from('<HH', buf, pos)
        year = (zipday >> 11) + 2004
        month = (zipday % 2048) // 100
        day = (zipday % 2048) % 100
        hour, minute = tminutes // 60, tminutes % 60
        pos += 4
        if category < 4 or category in (7, 8):
            return '%04d%02d%02d%02d%02d' % (year, month, day, hour, minute), pos
        return '%04d%02d%02d' % (year, month, day), pos
    else:
        (zipday,) = struct.unpack_from('<I', buf, pos)
        pos += 4
        return '%08d' % zipday, pos


def _get_price(buf, pos):
    """varint 差分价格: 6bit/段, bit7=续位, bit6=符号"""
    b = buf[pos]
    val = b & 0x3f
    sign = bool(b & 0x40)
    pos_byte = 6
    if b & 0x80:
        while True:
            pos += 1
            b = buf[pos]
            val += (b & 0x7f) << pos_byte
            pos_byte += 7
            if not (b & 0x80):
                break
    pos += 1
    return (-val if sign else val), pos


def _get_volume(ivol):
    """x87 反编译成交量/额解码（vendored from pytdx helper.get_volume）"""
    logpoint = ivol >> 24
    hleax = (ivol >> 16) & 0xff
    lheax = (ivol >> 8) & 0xff
    lleax = ivol & 0xff
    dwEcx = logpoint * 2 - 0x7f
    dwEdx = logpoint * 2 - 0x86
    dwEsi = logpoint * 2 - 0x8e
    dwEax = logpoint * 2 - 0x96
    xmm6 = 2.0 ** abs(dwEcx)
    if dwEcx < 0:
        xmm6 = 1.0 / xmm6
    if hleax > 0x80:
        xmm4 = 2.0 ** dwEdx * 128.0 + (hleax & 0x7f) * 2.0 ** (dwEdx + 1)
    else:
        xmm4 = hleax * 2.0 ** -dwEdx
    xmm3 = 2.0 ** dwEsi * lheax
    xmm1 = 2.0 ** dwEax * lleax
    if hleax & 0x80:
        xmm3 *= 2.0
        xmm1 *= 2.0
    return xmm6 + xmm4 + xmm3 + xmm1


def parse_052d(body, category):
    """解析 052d 响应体 → [(time_key, open, high, low, close, amount, volume)]"""
    if len(body) < 2:
        return []
    (ret_count,) = struct.unpack_from('<H', body, 0)
    pos = 2
    bars = []
    pre_diff_base = 0
    for _ in range(ret_count):
        try:
            time_key, pos = _get_datetime(category, body, pos)
            d_open, pos = _get_price(body, pos)
            d_close, pos = _get_price(body, pos)
            d_high, pos = _get_price(body, pos)
            d_low, pos = _get_price(body, pos)
            vol_raw, dbvol_raw = struct.unpack_from('<II', body, pos)
            pos += 8
        except (struct.error, IndexError):
            break
        p_open = d_open + pre_diff_base
        o = p_open / 1000.0
        c = (p_open + d_close) / 1000.0
        h = (p_open + d_high) / 1000.0
        l = (p_open + d_low) / 1000.0
        pre_diff_base = p_open + d_close
        # Current 7709 servers encode these two u32 slots as IEEE-754 float32.
        # pytdx's legacy get_volume decoder happens to agree for many bit patterns,
        # but silently corrupts others. Daily volume is in lots; minute volume is
        # already in shares. Amount is yuan for both.
        volume = struct.unpack('<f', struct.pack('<I', vol_raw))[0]
        amount = struct.unpack('<f', struct.pack('<I', dbvol_raw))[0]
        bars.append((time_key, round(o, 3), round(h, 3), round(l, 3),
                     round(c, 3), float(amount),
                     int(round(volume)) * (100 if category == 9 else 1)))
    return bars


CATEGORY_CODES = {'1m': 8, '5m': 0, '15m': 0, '30m': 0, '60m': 0, 'daily': 9}
MAX_PER_CALL = 800
