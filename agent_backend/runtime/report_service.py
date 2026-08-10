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
    final = db.connection.execute("SELECT * FROM final_evaluations WHERE session_id=?", (session_id,)).fetchone()
    claims = [dict(row) for row in db.connection.execute("SELECT * FROM claims WHERE session_id=?", (session_id,))]
    events = [dict(row) for row in db.connection.execute("SELECT * FROM agent_events WHERE session_id=? ORDER BY timestamp", (session_id,))]
    spec = json.loads(state["domain_specs"][-1]["content_json"]) if state["domain_specs"] else {}
    lines = [
        "# ECOMIC 中文科研报告",
        f"\n- Session：`{session_id}`",
        f"- 状态：`{state['status']}`",
        f"- DomainSpec 版本：{len(state['domain_specs'])}",
        f"- 假设数：{len(state['hypotheses'])}",
        f"- 实验数：{len(state['runs'])}",
        "\n## 领域与语义审计",
        f"```json\n{json.dumps(spec, ensure_ascii=False, indent=2)}\n```",
        "\n## 实验运行",
    ]
    for run in state["runs"]:
        lines.append(f"- `{run['run_id']}` · {run['policy']} · budget={run['budget']} · seed={run['seed']} · {run['status']}")
    lines.extend([
        "\n## 内部 Oracle Final Evaluation",
        f"```json\n{final['metrics_json'] if final else json.dumps({'status': 'NOT_REVEALED'}, ensure_ascii=False)}\n```",
        "\n## Claim Guard",
    ])
    for claim in claims:
        lines.append(f"- `{claim['status']}`：{claim['content']}")
    lines.extend([
        "\n## 限制",
        "- 研究阶段不暴露 Oracle 标签或最终指标。",
        "- REPLAY MODE / simulation 不能替代真实历史选择机制证据。",
        "- 观察成本代理不得表述为真实业务伤害或真实干预成本。",
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
        "security": {"oracle_labels_exported": False, "credentials_exported": False},
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    actions = root / "exported_actions.jsonl"
    actions.write_text("\n".join(json.dumps(event, ensure_ascii=False) for event in events) + ("\n" if events else ""), encoding="utf-8")
    return {"final_report": str(report), "manifest": str(manifest), "actions": str(actions), "plots": str(plots), "artifacts": str(artifacts)}
