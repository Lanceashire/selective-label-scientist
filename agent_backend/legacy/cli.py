from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .session import ResearchSession


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="ECOMIC 跨领域选择性标签科研后端")
    parser.add_argument("--data", help="CSV 或 Parquet 路径")
    parser.add_argument("--description", default="", help="数据来源和标签可见性的辅助描述")
    parser.add_argument("--budget", type=float, default=None)
    parser.add_argument("--seed", type=int, default=7)
    parser.add_argument("--root", default=str(Path(__file__).parents[1]))
    parser.add_argument("--id", dest="entity_id", help="人工确认实体 ID 字段")
    parser.add_argument("--decision", help="人工确认历史决策字段")
    parser.add_argument("--target", help="人工确认结果标签字段")
    parser.add_argument("--cost", help="人工确认观察成本字段")
    args = parser.parse_args(argv)
    data_path = args.data or input("请输入数据集路径（CSV/Parquet）：").strip()
    if not data_path:
        print("未提供数据集路径", file=sys.stderr)
        return 2
    overrides = {k: v for k, v in {"id": args.entity_id, "decision": args.decision, "target": args.target, "cost": args.cost}.items() if v}
    try:
        result = ResearchSession(data_path, args.root, args.description, overrides).run(args.budget, [args.seed])
    except Exception as exc:
        print(json.dumps({"status": "ERROR", "message": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 1
    print("╔════════════════════ 研究任务完成 ═══════════════════╗")
    print(f"║ 审计状态：{result['audit_status']:<38}║")
    print(f"║ 证据状态：{result['evidence_status']:<38}║")
    print(f"║ Session：{result['session_id']:<40}║")
    print(f"║ 中文报告：{Path(result['run_dir']) / 'final_report.md'}")
    print(f"║ DomainSpec：{Path(result['run_dir']) / 'domain_spec.json'}")
    print(f"║ 审计日志：{Path(result['run_dir']) / 'actions.jsonl'}")
    if result["needs_confirmation"]:
        print(f"║ 需要确认字段：{', '.join(result['needs_confirmation'])}")
        print("║ 可用 --decision/--target/--cost 进行结构化确认后重跑")
    print("╚════════════════════════════════════════════════════╝")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
