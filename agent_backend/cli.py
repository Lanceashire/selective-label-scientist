"""Small Chinese CLI entry point backed exclusively by ResearchRuntime."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
from .runtime import ResearchRuntime

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="ECOMIC 跨领域选择性标签科研智能体")
    parser.add_argument("--data", help="CSV 或 Parquet 路径")
    parser.add_argument("--description", default="")
    parser.add_argument("--state-dir", default=str(Path.home()/".ecomic"))
    args = parser.parse_args(argv); path = args.data or input("请输入数据集路径（CSV/Parquet）：").strip()
    if not path: return 2
    runtime = ResearchRuntime(args.state_dir)
    try:
        result = runtime.create_session(path, args.description)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        print("\n已创建研究 Session。请在 ECOMIC 中文 TUI 中确认决策字段、标签字段、动作映射、成本和时间顺序后再运行实验。")
        return 0
    finally:
        runtime.close()
if __name__ == "__main__": raise SystemExit(main())
