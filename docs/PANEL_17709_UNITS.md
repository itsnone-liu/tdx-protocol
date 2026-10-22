# 17709 面板字段单位/档位口径（定案 2026-10-22）

**适用**：一切从隔离客户端 `127.0.0.1:17709`（`get_market_snapshot` / `get_market_data`）取行情的代码。
**结论来源**：2026-10-22 客户端 vs CLI 逐字节对拍「表 B」——同一时刻两个出口 5 票逐字段对齐
（11:35:00.926 面板 / 11:35:16.528 L1），非推断。

代码落地：`realclient/panel_units.py`（规则即代码，含 fail-closed 校验），
离线不变量测试 `realclient/test_panel_units.py`。

---

## 1. 三个出口的关系

| 出口 | 地址/方式 | 谁在用 |
|---|---|---|
| **面板** | `POST http://127.0.0.1:17709/` | Windows 侧脚本（`r5_lunch_capture.py`、tdx-node） |
| **协议 L1** | TCP `7709` op11 `GetSecurityQuotes` | `realclient/cli.py`（本机 Linux 侧） |
| **本地文件** | `/root/tdx_data/*.day` | 回测/盘后 |

面板与 L1 是**同一份行情**的两个出口，但**字段名、单位、档位深度都不一样**——
直接混用必然出数据错，且不会报错（静默错）。

---

## 2. 单位规则（硬约束）

| 字段 | 面板 | 协议 L1 | 换算 |
|---|---|---|---|
| 成交额 | `Amount`（**万元**） | `amount`（**元**） | 面板 ×10⁴ |
| 成交量 | `Volume`（手） | `vol`（手） | 1:1 |
| 价格 | `Now/LastClose/Open/Max/Min`（元） | `price/last_close/open/high/low`（元） | 1:1 |

**三角校验（锁死单位，别靠记忆）**：

```
Average == Amount(万) × 1e4 / Volume(手) / 100
000001 实测: 80711.66 × 1e4 / 712860 / 100 = 11.32  ✓ 与面板 Average 一致
```

把面板万元当元用，均价会小 10⁴ 倍 —— `average_check()` 会判 `False`，
所以任何面板取数的入库路径都**应当**跑一次该校验（`volume>0` 时）。

---

## 3. 档位规则（五档只能走 L1）

- 面板 `Buyp/Sellp` **只回第 0 档**：`Buyp[1..4]`/`Sellp[1..4]` 恒 `0.00`，`Buyv/Sellv[1..4]` 恒 `0`。
- **要五档 → 必须走协议 L1**（`quotes()` 的 `bid1..bid5` / `ask1..ask5`）。
- 面板的 1 档只可用于与 L1 的 `bid1/ask1` 交叉校验。
- 代码闸门：`require_five_levels('panel')` **直接抛错**，避免「拿 0 当档位」混进盘口计算。

---

## 4. 新鲜度规则（面板没有时间戳）

- 面板**没有** `servertime` / `reversed_bytes0`（L1 有）。
- 因此**不能**用请求时间判数据新旧；相邻 tick 的区分也只能靠 L1 的
  `servertime` + `reversed_bytes0`。
- 面板侧只记录「请求时刻」，并注明这是**采集时间**而非**行情时间**。

---

## 5. 字段对应表（表 B，全部等值）

| 面板 | L1 | 说明 |
|---|---|---|
| `Now` | `price` | 现价 |
| `LastClose` | `last_close` | 昨收 |
| `Open` / `Max` / `Min` | `open` / `high` / `low` | 开高低 |
| `Volume` | `vol` | 成交量(手) |
| `Amount` | `amount` | 成交额（**单位差 10⁴**） |
| `Inside` / `Outside` | `s_vol` / `b_vol` | 内盘/外盘 |
| `ItemNum` | `active1` | 现手 |
| `Buyp[0]` / `Buyv[0]` | `bid1` / `bid_vol1` | 买一（仅第 0 档） |
| `Sellp[0]` / `Sellv[0]` | `ask1` / `ask_vol1` | 卖一（仅第 0 档） |

**面板独有**（L1 没有）：`Average`、`Before5MinNow`、`NowVol`、`Zangsu`、`ZAFPre3`、
`TickDiff`、`XsFlag`、`InOutFlag`、`UpHome`、`DownHome`、`Jjjz`、`ErrorId`。

其中 `Zangsu = (Now / Before5MinNow − 1) × 100`（实测 4/4 吻合，见 `zangsu_pct()`）。

---

## 6. 停牌/无行情判定（相关，同一轮对拍定案）

- **不要**用 `price == 0 && vol == 0` 判停牌：盘前 09:10 全市场请求 5598 只、返回 5576 只，
  5576/5576 **全部** `price=0,vol=0,servertime=8:35:00.000`。
- 真信号 = 服务器**不返回该记录**（missing）。C-2 实测 22 只 = 停牌/无行情。
- 少给记录时服务器用**占位行**凑数（C-3：unexpected 恒为 `600839`，出现次数与 missing 严格 1:1）
  → 请求集之外的键一律噪声，绝不入榜。

---

## 7. 用法

```python
from panel_units import (amount_wan_to_yuan, average_check,
                         map_panel_to_l1, require_five_levels, zangsu_pct)

row = snapshot['600000']                 # 面板原始行
m = map_panel_to_l1(row)                 # → L1 同义字段（amount 已换算为元）
ok, exp = average_check(row['Amount'], row['Volume'], row['Average'])
require_five_levels('l1')                # 五档场景；传 'panel' 直接抛错
```

`map_panel_to_l1()` 保留面板独有字段为 `panel_*` 前缀，避免与 L1 字段混淆；
`amount_source='panel_wan_x1e4'` 标记该 amount 是换算来的，便于审计回溯。