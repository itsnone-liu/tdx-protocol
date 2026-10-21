# TDX (通达信) 行情数据纯 CLI 逆向

## 后续更新：批量股本、名称、前复权与故障保护

`realclient/cli.py` 当前还支持 `capital-batch`、`snapshot-batch`、`names`、`daily`、`qfq-daily`、`finance`。真实名称协议044E/044D已在沪深北在线复现；80只quotes+op16股本约594ms（单次午间样本）。独立网络daily+xdxr自算qfq的四只6384个OHLC点全≤0.01。回归 **27/27通过**。

全市场按本机文件清单5597只，op15累计187646事件、373秒、零请求失败；该清单含旧码，不是官方在市普查。R1原始字节证明601198当前日线响应为空、quote返回600839，排除本项目JSON解析丢Date；证券生命周期原因未知。线上/本地表未发现重复cat1，不能据此宣称同日归一化已验。

```bash
python3 realclient/cli.py snapshot-batch sh600125 sz000001 bj920002 --bootstrap lab/op11_template.bin --out snapshot.json
python3 realclient/cli.py names bj920002 --bootstrap lab/op11_template.bin --out bj_names.json
python3 realclient/cli.py qfq-daily sh600125 --count 400 --bootstrap lab/op11_template.bin --out qfq.json
# 仅传输故障切站；语义错误不静默重试。结果原子替换，失败保留旧文件。
python3 realclient/cli.py quotes sh600125 --host 123.60.164.122 --fallback-host 175.178.112.197:7709 --bootstrap lab/op11_template.bin --out quotes.json --attempt-log attempts.json
```

[R1–R6待验清单](docs/R1_R6_ACCEPTANCE_PLAN.md)、[Ubuntu交接说明（未实跑）](docs/UBUNTU_HANDOFF.md)、[工程与证据摘要](docs/REALCLIENT_UPDATE_20261021.md)。特殊类别/未知类别在复权窗口内失败即拒绝；不宣称全史复权、竞价或停牌状态已验收。

## 2026-10-21 真实客户端增量验证

新增 `realclient/cli.py`：真实 op11 握手、沪深北实时快照、op15 批量除权、仿射前复权计算。使用 Python3 + tdxpy==0.2.7（仅编解码）；不访问腾讯或新浪。

```bash
python3 -m pip install -r realclient/requirements.txt
python3 realclient/cli.py quotes sh600125 sz000001 bj920002 --bootstrap lab/op11_template.bin
python3 realclient/cli.py xdxr-batch sh600125 bj920002 --bootstrap lab/op11_template.bin
python3 realclient/test_cli.py
```

本轮证据：
- **客户端正常退出、17709关闭后**，独立新连接quotes3/3与除权46/15条通过，随后恢复客户端。
- 同主站同80只：旧库握手0条；真实op11握手80条，沪30深30北20身份集合匹配（异常000004单列，CLI拒收意外代码）。
- 定向16只共25,536个已收盘OHLC价格点，与实际客户端front输出误差均≤0.01。
- 冻结种子随机50只近一年事件票：49只有效基准46,880个OHLC价格点零超差；601198.SH客户端缺Date基准，**不是50/50通过**。
- 本地gbbq与网络4股44条cat1字段完全相等；实际客户端批量op15已在独立连接复现。
- **ForwardFactor不等于front价格乘数**。前复权使用cat1仿射链；不能以股本前后比替代送转率。

详见 [本轮报告](docs/REALCLIENT_20261021.md) 与 `realclient/evidence/` 精简结果。Ubuntu运行尚未实测；模板仍来自真实抓包，尚不是完整初始化字段生成器。以下旧文中的“北交所不可用”只描述旧K线探针，**不适用于本轮实时与除权**；旧模板长度说明亦有笔误：当前前缀284B（含12B头），加8B尾共292B。

逆向通达信桌面版 V7.73 的行情数据下载协议，实现纯 Python stdlib CLI，
无需登录、无需运行桌面客户端、可直接在 Ubuntu 上使用。

## 快速开始

```bash
# 需要两个文件在同一目录：
#   tdx_cli.py          — 主 CLI
#   op11_template.bin   — 会话初始化模板 (272B)

# 10只股票 × 1分钟 + 日线
python3 lab/tdx_cli.py 000001 600000 510300 688981 --periods 1m,daily --workers 4

# 自动从48个主站中选最快的
python3 lab/tdx_cli.py 000001 --period daily --out my_data.csv
```

## 支持范围

| 功能 | 状态 |
|------|------|
| 1 分钟线 | ✅ 1000 条/次 |
| 5 分钟线 | ✅ 1000 条/次 |
| 日线 | ✅ 1000+ 条，自动分页回溯 |
| 深市主板/创业板 | ✅ market=0 |
| 沪市主板/科创板 | ✅ market=1 |
| 沪/深 ETF | ✅ |
| 主站自动测速 | ✅ 48 台服务器 |
| 并发下载 | ✅ 多 worker + 持久连接 |
| 服务器故障切换 | ✅ |
| 登录 | ❌ 不需要（7709 行情通道无账号认证） |

## 协议要点

详见 `PROTOCOL.md`。

- **op11**: 会话初始化帧，292B = 272B 固定模板 + 8B 随机数。发送后服务器返回
  确认，即可开始数据请求。这不是账号 token，是客户端能力声明。
- **op4045**: K线数据请求。`market:u16 + code:6B ASCII + cursor_start:u32 +
  cursor_end:u32 + period:u16`
- **周期码**: 1m=`0x0007`, 5m=`0x0000`, daily=`0x0004`
- **市场码**: SZ=`0`, SH=`1`（北交所 `2` 不可用）

## 数据验证

- 1分钟：10 只票 × 960 条，与桌面客户端抓包和本地 `.lc1` 逐字节匹配
- 日线：1,820 条与本地 `.day` 文件 100% 匹配

## 文件说明

| 文件 | 用途 |
|------|------|
| `lab/tdx_cli.py` | 生产 CLI（纯 stdlib） |
| `lab/op11_template.bin` | 会话模板（必需） |
| `lab/tdx_op11_minimal_cli.py` | 最小验证 CLI |
| `lab/validate_op11_minimal_cli.py` | 数据验证脚本 |
| `lab/validate_daily_vs_local.py` | 日线 vs 本地 .day 对拍 |
| `lab/analyze_daily_format.py` | 日线格式分析 |
| `lab/probe_multi_period_v2.py` | 周期/市场探测 |
| `lab/probe_daily_pagination.py` | 日线游标分页探测 |
| `PROTOCOL.md` | 完整协议文档 |
| `PLAN.md` | 项目计划与实验记录 |

## 已知限制

- 15m/30m/60m 不由服务器直接提供，需从 1m/5m 聚合
- 北交所（market=2）在此协议下不可用
- 并发过多可能触发服务器限流（4 worker 实测稳定）
- op11 模板来自抓包，协议升级后可能需重新提取
