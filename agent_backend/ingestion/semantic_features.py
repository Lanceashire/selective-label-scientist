from __future__ import annotations

from typing import Any

from .profiler import inspect_schema, profile_columns


def infer_semantics(dataset: dict[str, Any], description: str = "") -> dict[str, Any]:
    schema = inspect_schema(dataset)
    candidates = profile_columns(dataset, schema)
    return {
        "schema": schema,
        "candidates": candidates,
        "description": description,
        "needs_confirmation": [
            key for key in ("target", "decision", "cost") if len(candidates.get(key, [])) != 1
        ],
        "reasoning": "字段名仅作为信号，候选同时结合类型、值分布和缺失情况；关键字段不确定时必须人工确认。",
    }

