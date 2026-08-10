# ECOMIC · Selective-Label Scientist

这是一个面向 GOAI AI for Research 的跨领域选择性标签科研智能体首版。它把
`Lanceashire/LexiRiskLabel` 作为只读信用参考实现，把 `earendil-works/pi`
作为 Agent Runtime 的扩展入口；通用数据处理、环境审计、预算约束、策略实验、
证据日志和 Claim Guard 均在本项目中独立实现。

## 当前可运行能力

- CSV（必选）和 Parquet（安装 pandas/pyarrow 后）导入；字段统计、缺失率、候选
  ID/标签/历史决策/时间/成本/敏感字段和潜在泄漏字段审计。
- 自动构造不依赖信用术语的 `DomainSpec`；语义不确定时返回
  `NEEDS_USER_INPUT`，不强行猜测。
- GenericTabularAdapter：用 `observation_cost_i` 和预算约束建立通用选择性标签环境。
- `Random`、`CountOnly-MinCost`、`LRBE-Uncertainty` 三个通用策略；每个策略有
  capability 检查，不满足前提时返回 `POLICY_NOT_APPLICABLE`。
- Research Mode / Final Evaluation 隔离：研究阶段不可读 outer-test；计划锁定后
  才能揭示最终评价，揭示后禁止自适应调参。
- 中文报告、JSONL 审计日志、DomainSpec 历史、实验结果和 Claim Guard 结果。
- Pi 扩展 `agent/src/pi-extension.ts` 注册科研工具；LLM 只做语义/规划/解释，
  数值计算由 Python 后端完成。默认 mock 模式无需 API Key 即可跑完整 loop。

## 快速开始

```powershell
cd D:\ECOMIC_Scientist_Agent
npm run ecomic -- --data examples\fraud_like.csv --description "只有被人工复核的交易拥有后续标签"
```

无参数启动会进入中文导入提示：

```powershell
npm run ecomic
```

后端也可直接运行：

```powershell
python -m agent_backend.cli --data examples\fraud_like.csv --description "复核行为决定后续标签是否可见"
```

## Pi 接入

`vendor\pi` 是指定仓库的浅克隆，`agent/src/pi-extension.ts` 按官方
`ExtensionAPI`/`registerTool` 接口实现安全工具扩展。若要运行完整 Pi TUI：

```powershell
cd vendor\pi
npm install --ignore-scripts
npm run build:offline
cd ..\..
npm run ecomic:pi
```

Pi 的默认 shell 工具不在 ECOMIC 扩展中开放；扩展只注册白名单科研工具，所有工具
通过 JSONL 调用 Python 后端。

## 目录

```text
agent_backend/                 Python 科研后端
  ingestion/                   数据读取与 schema intelligence
  domains/                     Generic / Credit reference adapter
  environment/                 可见性、预算、final barrier
  policies/                    通用策略与 capability registry
  evidence/                    审计日志和中文报告
agent/src/main.mjs             npm CLI / 中文 TUI
agent/src/pi-extension.ts      Pi custom tools
agent/src/model.ts             @earendil-works/pi-ai 配置边界
tests_agent/                   关键安全与跨领域测试
examples/                      信贷样式、非信贷样式和失败样例
vendor/LexiRiskLabel/          只读科研参考仓库
vendor/pi/                     只读 Agent Runtime 源码
agent_runs/<session>/          每次运行的可复现输出
```

## 科研边界

LexiRiskLabel 的 `src/phase0_engine.py`、`phase1_runner.py`、`phase2_runner.py`、
`phase3_runner.py` 及 frozen results 不在本项目中修改。CreditReferenceAdapter 只
记录其路径、Git commit 和文件 hash，并可读取已有结果；通用实验不会复制或改写
信用算法。当前 GenericTabularAdapter 的结果是“可执行性证据”，不等于任何新领域
已经完成科学验证。代理成本始终标记为 `PROXY COST`，不能被写成真实伤害或安全风险。

