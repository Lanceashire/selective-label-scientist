"""Render auditable Chinese session deliverables from SQLite source of truth."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def export_session(db: Any, session_id: str, run_root: Path) -> dict[str, str]:
    state = db.resume_session(session_id)
    root = run_root / session_id
    plots = root / "plots"
    artifacts = root / "artifacts"
    for directory in (root, plots, artifacts):
        directory.mkdir(parents=True, exist_ok=True)
    dataset = db.connection.execute(
        "SELECT sha256, format, row_count, column_count FROM datasets WHERE dataset_id=?", (state["dataset_id"],)
    ).fetchone()
    final = db.connection.execute("SELECT * FROM final_evaluations WHERE session_id=?", (session_id,)).fetchone()
    claims = [dict(row) for row in db.connection.execute("SELECT * FROM claims WHERE session_id=?", (session_id,))]
    events = [dict(row) for row in db.connection.execute("SELECT * FROM agent_events WHERE session_id=? ORDER BY timestamp", (session_id,))]
    spec = json.loads(state["domain_specs"][-1]["content_json"]) if state["domain_specs"] else {}
    question = str(state.get("research_question") or "未记录独立自然语言问题；以下研究围绕当前已确认的 DomainSpec 与假设展开。")
    lines = [
        "# ECOMIC 中文科研报告",
        "",
        "## 研究问题",
        question,
        "",
        "## Session 与数据集",
        f"- Session：`{session_id}`",
        f"- 状态：`{state['status']}`",
        f"- 数据集哈希：`{dataset['sha256'] if dataset else 'UNKNOWN'}`",
        f"- 数据格式 / 规模：{dataset['format'] if dataset else 'UNKNOWN'} / {dataset['row_count'] if dataset else 'UNKNOWN'} 行、{dataset['column_count'] if dataset else 'UNKNOWN'} 列",
        "",
        "## DomainSpec 与语义审计",
        f"- DomainSpec 版本：{len(state['domain_specs'])}",
        f"- 审计状态：{spec.get('audit_status', 'UNKNOWN')}",
        f"```json\n{json.dumps(spec, ensure_ascii=False, indent=2)}\n```",
        "",
        "## 假设与修订",
    ]
    if state["hypotheses"]:
        for hypothesis in state["hypotheses"]:
            parent = f"（修订自 `{hypothesis['parent_hypothesis_id']}`）" if hypothesis.get("parent_hypothesis_id") else ""
            lines.append(f"- H{hypothesis['version']} · `{hypothesis['status']}` {parent}：{hypothesis['content']}")
    else:
        lines.append("- 尚未创建假设。")
    lines.extend(["", "## 实验与可见证据"])
    if state["runs"]:
        for run in state["runs"]:
            lines.append(f"- `{run['run_id']}` · policy={run['policy']} · budget={run['budget']} · seed={run['seed']} · rounds={run['round_end']} · {run['status']}")
    else:
        lines.append("- 尚未运行实验。")
    lines.extend(["", "## 审计事件"])
    if events:
        for event in events[-20:]:
            lines.append(f"- {event['timestamp']} · `{event['tool_name']}` · {event['status']} · {event['summary']}")
    else:
        lines.append("- 尚无审计事件。")
    lines.extend([
        "",
        "## 内部 Oracle Final Evaluation",
        f"```json\n{final['metrics_json'] if final else json.dumps({'status': 'NOT_REVEALED'}, ensure_ascii=False)}\n```",
        "",
        "## Claim Guard",
    ])
    if claims:
        for claim in claims:
            lines.append(f"- `{claim['status']}`：{claim['content']}")
    else:
        lines.append("- 尚未形成可提交 Claim。")
    lines.extend([
        "",
        "## 限制",
        "- 研究阶段不暴露 Oracle 标签或最终指标；最终指标仅在锁定计划后的 Final Evaluation 中出现。",
        "- REPLAY MODE / simulation 不能替代真实历史选择机制证据。",
        "- 观察成本代理不得表述为真实业务伤害或真实干预成本。",
        "",
        "## Reproduction Info",
        f"- SQLite source of truth：`{db.path}`",
        f"- Final evaluation revealed：`{bool(state['final_evaluation_revealed'])}`",
        "- 重现配方：使用上方每个 Run 的 policy、budget、seed 和 rounds；运行记录及导出 manifest 与本报告存于同一 Session 目录。",
        "- 安全边界：报告不导出 API Key、Authorization header、Oracle 原始标签或模型私有推理过程。",
    ])
    report = root / "final_report.md"
    report.write_text("\n".join(lines), encoding="utf-8")
    manifest = root / "manifest.json"
    manifest.write_text(json.dumps({
        "session_id": session_id,
        "database_source_of_truth": str(db.path),
        "final_evaluation_revealed": bool(state["final_evaluation_revealed"]),
        "run_count": len(state["runs"]),
        "outputs": {"final_report": str(report), "actions": str(root / "exported_actions.jsonl"), "plots": str(plots), "artifacts": str(artifacts)},
        "security": {"oracle_labels_exported": False, "credentials_exported": False, "private_reasoning_exported": False},
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    actions = root / "exported_actions.jsonl"
    actions.write_text("\n".join(json.dumps(event, ensure_ascii=False) for event in events) + ("\n" if events else ""), encoding="utf-8")
    return {"final_report": str(report), "manifest": str(manifest), "actions": str(actions), "plots": str(plots), "artifacts": str(artifacts)}