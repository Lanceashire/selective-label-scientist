from __future__ import annotations

from typing import Any


def generate_report(context: dict[str, Any]) -> str:
    spec = context["domain_spec"]
    audit = context["audit"]
    results = context.get("results", [])
    status = context.get("evidence_status", "INCONCLUSIVE")
    lines = [
        "# ECOMIC 自动科研报告", "", "## 一、数据集概况", "",
        f"- 数据集：`{context['dataset_path']}`", f"- 行数：{context['schema']['row_count']}；列数：{context['schema']['column_count']}", f"- SHA-256：`{context['dataset_hash']}`", "",
        "## 二、领域与标签机制识别", "", f"- 推断领域：{spec.get('domain_name', 'unknown')}（领域不是运行通用实验的必要前提）", f"- 结果标签字段：`{spec.get('outcome', {}).get('column')}`", f"- 历史决策字段：`{spec.get('historical_decision', {}).get('column')}`", "",
        "## 三、选择性标签审计", "", f"- 审计状态：**{audit['status']}**", f"- 通过检查：{audit['passed_checks']}/{audit['total_checks']}", "",
        "## 四、成本与预算定义", "", f"- 成本字段：`{spec.get('observation_cost', {}).get('column')}`", "- 成本性质：PROXY COST（代理成本，不等于真实伤害）", f"- 预算：{context.get('budget')}", "",
        "## 五、研究问题", "", context.get("research_question", "在固定预算下，反馈数量与反馈价值如何权衡？"), "",
        "## 六、研究假设", "", context.get("hypothesis", "H1：在可行预算下，数量优先策略可以获得更多可观测反馈；其下游效果需要独立评价。"), "",
        "## 七、实验设计", "", "研究阶段只使用可见反馈、预测成本和预算利用率；outer-test 由 Final Evaluation Barrier 隔离。", "",
        "## 八、实验结果", "", *[f"- {r['policy']}：状态={r['status']}，反馈数={r.get('feedback_count', '—')}，预测成本={r.get('predicted_cost', '—')}" for r in results], "",
        "## 九、反馈恢复分析", "", "反馈数量和可见覆盖率在研究阶段记录；不将其自动等同于下游召回或校准。", "",
        "## 十、下游决策恢复分析", "", "本次 GenericTabularAdapter smoke run 不揭示 outer-test 指标；需要锁定计划后再进行一次性最终评价。", "",
        "## 十一、假设修订过程", "", "首版由确定性工具生成基线假设；LLM 只能在证据范围内改写，不得制造数值结果。", "",
        "## 十二、最终可支持结论", "", f"- 当前证据状态：**{status}**。", "- 系统已证明该数据的 schema 审计、DomainSpec 构造和预算化策略调用可执行。", "",
        "## 十三、当前不能支持的结论", "", "- 不能宣称策略适用于所有领域。", "- 不能宣称代理成本等于真实安全风险。", "- 不能把 Generic smoke run 当成新领域科研验证。", "",
        "## 十四、限制与证据等级", "", f"- 领域证据等级：{context.get('domain_evidence_level', 'EXECUTABLE_ONLY')}", "- 关键限制：语义仍需要人工确认；Parquet 依赖可选；当前通用策略使用离线代理价值。", "",
        "## 十五、复现信息", "", f"- session：`{context['session_id']}`", "- 运行目录包含 manifest、schema_profile、domain_spec、audit_report、actions、experiment_results 和 final_claims。", "",
    ]
    return "\n".join(lines)

