# TDX (通达信) 行情数据纯 CLI 逆向

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

## 数据完整性与实现说明

默认使用 `op 0x052d` 的 count-based 分页，而不是早期实验性的 `op4045` 绝对游标：

- `start=0` 从最新 bar 开始，随后按 800 根一页向历史回溯；因此不会把“最新窗口”和“最老窗口”拼在一起，也不会静默漏掉中间几十年。
- 1m/5m 的 `time_key` 输出为可读的 `YYYYMMDDHHMM`；日线为 `YYYYMMDD`。
- 旧 op4045 路径保留在代码中供协议实验/对拍，但不作为生产分页路径。
- 生产接入前应检查首尾日期和分页去重；空响应或异常日期必须报错，不应伪装成完整历史。

## 已知限制

- 15m/30m/60m 不由服务器直接提供，需从 1m/5m 聚合
- 北交所（market=2）在此协议下不可用
- 并发过多可能触发服务器限流（4 worker 实测稳定）
- op11 模板来自抓包，协议升级后可能需重新提取
- 052d 的第二个成交量字段按 pytdx 兼容语义输出为 `amount`，需与本地 `.day/.lc1` 做一次业务口径复核
