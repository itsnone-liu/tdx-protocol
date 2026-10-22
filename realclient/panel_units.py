"""17709 面板字段单位/档位口径（2026-10-22 客户端 vs CLI 逐字节对拍「表 B」定案）。

面板 = 隔离客户端监听的 127.0.0.1:17709 HTTP 快照（get_market_snapshot / get_market_data）。
它与协议 L1（op11 GetSecurityQuotes）是**同一份行情**的两个出口，已 1:1 互证
（2026-10-22 11:35:00.926 / 11:35:16.528，5 票逐字段对齐）。

单位/口径规则 —— 违反即数据错，不是风格问题：

1. **Amount**：面板 = **万元**，协议 L1 = **元**，两者差 10,000×。
   面板取到的 amount 必须 ×1e4 才与 L1 同口径。
   三角校验（000001 实测）：Average == Amount(万)×1e4 / Volume(手) / 100
   → 80711.66×1e4 / 712860 / 100 = 11.32 ✓（单位差由该式锁死，不再靠猜）
2. **档位**：面板 Buyp/Sellp **只回第 0 档**（Buyp[1..4]/Sellp[1..4] 恒 0.00/0）。
   要五档必须走协议 L1（bid1..bid5 / ask1..ask5）。面板只可当 1 档交叉校验。
3. **Volume** 面板与 L1 同为**手**；Inside/Outside = L1 内盘 s_vol / 外盘 b_vol。
4. **面板独有字段**：Average, Before5MinNow, NowVol, Zangsu, ZAFPre3, TickDiff,
   XsFlag, InOutFlag, UpHome, DownHome, Jjjz, ErrorId。
   Zangsu = (Now / Before5MinNow − 1) × 100（实测 4/4 吻合）。
5. 面板**没有** servertime / reversed_bytes0 → 判数据新鲜度不能看请求时间，
   必须用 L1 响应的 servertime / reversed_bytes0（相邻 tick 的区分也靠它）。
6. **字段对应（表 B，全部等值）**：
   Now↔price, LastClose↔last_close, Open↔open, Max↔high, Min↔low,
   Volume↔vol, Inside↔s_vol, Outside↔b_vol, ItemNum↔active1,
   Buyp[0]↔bid1, Buyv[0]↔bid_vol1, Sellp[0]↔ask1, Sellv[0]↔ask_vol1。
"""
from __future__ import annotations

import math

WAN = 10000.0          # 万元 → 元
PANEL_LEVELS = 1       # 面板只回 1 档
SHARES_PER_HAND = 100  # A 股 1 手 = 100 股
L1_SOURCE = 'l1'


def _num(x, what):
    """fail-closed 数值入口：None/字符串垃圾/NaN/Inf 一律 ValueError（不猜不补）。"""
    try:
        v = float(x)
    except (TypeError, ValueError):
        raise ValueError('invalid %s: %r' % (what, x))
    if not math.isfinite(v):
        raise ValueError('invalid %s: %r' % (what, x))
    return v


def amount_wan_to_yuan(amount_wan):
    """面板 Amount（万元）→ 元。非有限值/负值一律拒绝（fail-closed，不猜不补）。"""
    x = _num(amount_wan, 'panel amount')
    if x < 0:
        raise ValueError('invalid panel amount: %r' % (amount_wan,))
    return x * WAN


def amount_yuan_to_wan(amount_yuan):
    """元 → 面板口径（万元）。写面板/对照时用。"""
    x = _num(amount_yuan, 'amount')
    if x < 0:
        raise ValueError('invalid amount: %r' % (amount_yuan,))
    return x / WAN


def average_from_amount(amount_wan, volume_hand):
    """三角校验用：面板 Amount(万)+Volume(手) 反算均价（元/股）。

    只有面板单出口时，用它验证 amount 单位取对了：
    面板均价 == amount_wan×1e4 / volume_hand / 100。
    """
    try:
        vol = float(volume_hand)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(vol) or vol <= 0:
        return None
    return amount_wan_to_yuan(amount_wan) / vol / SHARES_PER_HAND


def average_check(amount_wan, volume_hand, average, tol=0.02):
    """面板自洽校验：反算均价 vs 面板 Average 是否在 tol 元内。

    返回 (ok, expected)。vol<=0（盘前/无成交）返回 (None, None) —— 不判真假。
    """
    exp = average_from_amount(amount_wan, volume_hand)
    if exp is None:
        return None, None
    avg = float(average)
    if not math.isfinite(avg):
        return False, exp
    return abs(exp - avg) <= tol, exp


def zangsu_pct(now, before5minnow):
    """面板 Zangsu（%）复算：(Now / Before5MinNow − 1) × 100。前值<=0 拒绝。"""
    b = _num(before5minnow, 'Before5MinNow')
    if b <= 0:
        raise ValueError('invalid Before5MinNow: %r' % (before5minnow,))
    return (_num(now, 'Now') / b - 1.0) * 100.0


def require_five_levels(source):
    """五档报价闸门：只有协议 L1 能给五档，面板调用必须 fail-closed 而不是拿 0 当档位。"""
    if source == L1_SOURCE:
        return True
    raise ValueError('五档报价须走协议 L1(op11 quotes)；面板 source=%r 只回 %d 档' % (source, PANEL_LEVELS))


def map_panel_to_l1(row):
    """面板行（dict，键名见模块 docstring 第 6 条）→ L1 同义字段名。

    只映射已 1:1 互证的字段；面板独有的原样带 `panel_` 前缀保留，避免与 L1 字段混淆。
    """
    pairs = [
        ('Now', 'price'), ('LastClose', 'last_close'), ('Open', 'open'),
        ('Max', 'high'), ('Min', 'low'), ('Volume', 'vol'),
        ('Inside', 's_vol'), ('Outside', 'b_vol'), ('ItemNum', 'active1'),
    ]
    out = {}
    for src, dst in pairs:
        if src in row:
            out[dst] = row[src]
    if 'Buyp' in row and row['Buyp']:
        out['bid1'] = row['Buyp'][0]
    if 'Buyv' in row and row['Buyv']:
        out['bid_vol1'] = row['Buyv'][0]
    if 'Sellp' in row and row['Sellp']:
        out['ask1'] = row['Sellp'][0]
    if 'Sellv' in row and row['Sellv']:
        out['ask_vol1'] = row['Sellv'][0]
    if 'Amount' in row:
        out['amount'] = amount_wan_to_yuan(row['Amount'])
        out['amount_source'] = 'panel_wan_x1e4'
    for k in ('Average', 'Before5MinNow', 'NowVol', 'Zangsu', 'ZAFPre3', 'TickDiff',
              'XsFlag', 'InOutFlag', 'UpHome', 'DownHome', 'Jjjz', 'ErrorId'):
        if k in row:
            out['panel_' + k] = row[k]
    return out