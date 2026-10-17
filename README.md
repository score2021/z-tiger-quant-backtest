# z-tiger-quant-backtest

为老虎量化编写、迁移、修复和验证 Python 回测代码。入口：[SKILL.md](SKILL.md)。

## 可防范的已知问题

| 问题 | 技能中的处理方式 |
| --- | --- |
| QuantConnect 代码直接搬入老虎而无法运行 | 使用老虎原生回调、行情及订单 API |
| 普通名称、日志文字误触 `os` / `exec` 禁词；`sorted` 不可用 | 按实际报错改写无害文本，使用已验证的替代写法 |
| 页面与代码起止不一致，报 `Wrong first trading day` | 同时列出两处参数，核验实际首次回调；不假定初始化必占一天 |
| 将午夜日线回调判成错误、历史不足仍强行交易 | 每日模式与窗口长度分别验证，缺数据明确停止 |
| 用提交日价格算满仓股数，延后成交后透支现金、触发杠杆检查 | 买单按限价上界计资，预留费用；不提前使用未成交卖单回款 |
| 放宽杠杆上限掩盖错误 | 保留用户的融资约束，修复现金与成交逻辑 |
| 未成交或部分成交被误判成失败；撤单未完成就重复下单 | 跟踪订单状态，等待异步撤单或成交确认，拒单仍明确报错 |
| 下载日志未包含异常，或前端超时就盲目重跑 | 同时查看页面末尾错误和历史任务状态 |
| 信号完成被当作全部成交，虚拟账本被当作原生主图 | 分别核对末日、订单终态、原生/虚拟账户及统计口径 |
| 更换撮合、限价或手续费后仍宣称复现旧收益 | 保留信号规则，明确执行差异，重新验证结果 |

## 使用与验证

在对话中调用 `$z-tiger-quant-backtest`。只请求代码时不会自动登录或提交线上回测。

- 原生下单前阅读：[成交与现金约束](references/execution.md)。
- 可复用片段：[现金约束下单样例](examples/cash-orders.py)，须嵌入完整策略，不是独立回测程序。
- 离线自检：`python3 scripts/test_cash_orders.py`，仅使用伪订单接口，不连接账户。
- 实测边界：[证据与验收](references/validation.md)。

这些规则用于减少已知错误，不能保证所有账户、平台版本和行情下永不报错。新代码仍须区分本地检查、平台编译和完整线上运行。

## 成果展示

输入：“在老虎量化每日读取 QQQ 最近5根已完成日线，不交易。”

对应的最小代码为 [history-smoke.py](examples/history-smoke.py)：

```python
def initialize(context):
    context.asset = symbol("QQQ")
    set_benchmark(context.asset)


def handle_data(context, data):
    history = data.history(context.asset, "close", 5, "1d")
    log.info("QQQ latest historical close: %s" % history.iloc[-1])
```

来源会话中的该模式已在每日、2018-07-01 至 2018-12-31 的老虎回测中成功执行。它是无交易接口检查，收益0%正常；不证明撮合或策略收益正确。本次发布重新验证了离线现金约束测试，未重新提交线上回测。现金执行片段的历史来源与本包验证范围见[验证记录](references/validation.md)。

## 安装

仓库：[score2021/z-tiger-quant-backtest](https://github.com/score2021/z-tiger-quant-backtest)。个人技能调用名使用标准兼容的 `z-` 前缀，默认允许按相关任务自动选用。

先下载并进入仓库目录：

```sh
git clone https://github.com/score2021/z-tiger-quant-backtest.git
cd z-tiger-quant-backtest
```

然后执行以下安装命令；已有同名目录、文件或断链时停止，不覆盖个人修改：

```sh
skill_target="$HOME/.agents/skills/z-tiger-quant-backtest"
if [ -e "$skill_target" ] || [ -L "$skill_target" ]; then
  echo "目标已存在，请检查后再决定如何更新；未覆盖。" >&2
  exit 1
fi
mkdir -p "$HOME/.agents/skills"
mkdir "$skill_target" || exit 1
cp -R SKILL.md agents references examples scripts LICENSE "$skill_target/"
```

安装后重新打开对话，输入 `$z-tiger-quant-backtest`；候选未刷新时重启客户端。Codex 用户级安装路径是 `~/.agents/skills/z-tiger-quant-backtest/`。其他客户端的发现方式未经验证。离线样例测试需要 Python 3；老虎线上执行需要用户自己的登录与回测权限。

## 样例

以下内容可直接复制到 Codex 对话，不需要私有文件：

```text
$z-tiger-quant-backtest
请给我一个能在老虎量化每日回测中运行的最小 Python 脚本：
QQQ，读取最近5根已完成日线收盘价，输出最后一根，不交易。
只在会话提供完整代码，不写文件、不登录网站、不提交回测。
请给出平台链接、页面日期与频率设置、验收证据和已验证范围。
```

预期得到老虎原生回调代码及测试说明；无文件写入和外部提交。若后续要求实际操作平台，需要相应操作授权与可用工具。指定“改成老虎量化能运行的代码”也可自然触发，普通证券行情问题不应触发。

## 文件与许可

`SKILL.md` 是执行入口，`agents/` 为界面元数据，`references/` 为兼容与成交说明，`examples/` 为接口样例和执行片段，`scripts/` 为离线回归测试。原创材料与样例采用 [MIT](LICENSE)；链接的官方网页遵循各自条款。本仓库不含账户、凭据或原始用户回测数据。
