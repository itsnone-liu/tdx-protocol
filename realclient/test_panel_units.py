"""17709 面板单位/档位口径的离线不变量测试（不需要网络、不需要客户端）。

测试锚点全部来自 2026-10-22 客户端 vs CLI 逐字节对拍的「表 B」
（5 票 1:1 互证，11:35:00.926 / 11:35:16.528），不是模拟数据。
"""
import math

import pytest

from panel_units import (PANEL_LEVELS, amount_wan_to_yuan, average_check,
                         average_from_amount, map_panel_to_l1, require_five_levels,
                         zangsu_pct)


def test_amount_unit_is_wan_vs_yuan():
    # 面板 000001 Amount = 80711.66 万元 == 807,116,600 元
    assert amount_wan_to_yuan(80711.66) == pytest.approx(807116600.0, rel=1e-12)


def test_average_triangle_locks_amount_unit():
    """Average == Amount(万)×1e4 / Volume(手) / 100（000001 实测三角校验）。"""
    exp = average_from_amount(80711.66, 712860)
    assert exp == pytest.approx(11.32, abs=0.005)
    ok, expected = average_check(80711.66, 712860, 11.32)
    assert ok is True
    assert expected == pytest.approx(11.32, abs=0.005)


def test_average_triangle_rejects_wrong_unit():
    """若把面板万元当元用（少乘 1e4），均价会小 10^4 倍 —— 必须被判定不自洽。"""
    ok, expected = average_check(8.071166, 712860, 11.32)
    assert ok is False
    assert expected == pytest.approx(11.32 / 10000, rel=1e-3)


def test_average_check_preopen_returns_none():
    """盘前 vol=0 无法校验 —— 返回 None，不猜真假（fail-quiet，不是 fail-open）。"""
    ok, expected = average_check(0.0, 0, 0.0)
    assert ok is None and expected is None


def test_panel_amount_rejects_bad_values():
    for bad in (float('nan'), float('inf'), -1.0, None):
        with pytest.raises(ValueError):
            amount_wan_to_yuan(bad)


def test_five_levels_require_l1():
    assert require_five_levels('l1') is True
    with pytest.raises(ValueError) as e:
        require_five_levels('panel')
    assert 'L1' in str(e.value)
    assert PANEL_LEVELS == 1


def test_panel_only_returns_level0():
    """面板 Buyp[1..4]/Sellp[1..4] 恒 0 —— 映射后只应有 bid1/ask1，没有 bid2/ask2。"""
    row = {'Now': 11.32, 'LastClose': 11.30, 'Open': 11.31, 'Max': 11.35, 'Min': 11.25,
           'Volume': 712860, 'Amount': 80711.66, 'Inside': 400000, 'Outside': 312860,
           'ItemNum': 3, 'Buyp': [11.31, 0.0, 0.0, 0.0, 0.0], 'Buyv': [120, 0, 0, 0, 0],
           'Sellp': [11.32, 0.0, 0.0, 0.0, 0.0], 'Sellv': [340, 0, 0, 0, 0],
           'Average': 11.32, 'Zangsu': 0.18}
    m = map_panel_to_l1(row)
    assert m['price'] == 11.32 and m['last_close'] == 11.30
    assert m['high'] == 11.35 and m['low'] == 11.25
    assert m['vol'] == 712860 and m['s_vol'] == 400000 and m['b_vol'] == 312860
    assert m['bid1'] == 11.31 and m['bid_vol1'] == 120
    assert m['ask1'] == 11.32 and m['ask_vol1'] == 340
    for k in ('bid2', 'bid3', 'bid4', 'bid5', 'ask2', 'ask3', 'ask4', 'ask5'):
        assert k not in m
    assert m['amount'] == pytest.approx(807116600.0)
    assert m['amount_source'] == 'panel_wan_x1e4'
    assert m['panel_Average'] == 11.32          # 面板独有字段带前缀保留
    assert m['panel_Zangsu'] == 0.18


def test_zangsu_formula():
    """Zangsu = (Now / Before5MinNow − 1) × 100；000001 实测 0.18。"""
    assert zangsu_pct(11.32, 11.30) == pytest.approx(0.177, abs=0.002)
    assert round(zangsu_pct(11.32, 11.30), 2) == 0.18
    with pytest.raises(ValueError):
        zangsu_pct(11.32, 0.0)


def test_mapped_amount_matches_l1_semantics():
    """映射后 amount 与 L1 同口径（元），可用 元/手/100 直接得均价。"""
    m = map_panel_to_l1({'Amount': 80711.66, 'Volume': 712860, 'Average': 11.32,
                         'Now': 11.32})
    exp = m['amount'] / m['vol'] / 100
    assert math.isclose(exp, m['panel_Average'], abs_tol=0.005)