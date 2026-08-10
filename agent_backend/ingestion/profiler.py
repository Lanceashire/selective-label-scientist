from __future__ import annotations

import math
import re
from collections import Counter
from datetime import datetime
from typing import Any

_MISSING = {"", "na", "n/a", "null", "none", "nan", "missing", "未知"}
_DATE_RE = re.compile(r"^\d{4}[-/]\d{1,2}[-/]\d{1,2}")

def _missing(value: Any) -> bool:
    return value is None or str(value).strip().lower() in _MISSING
def _number(value: Any) -> float | None:
    if _missing(value): return None
    try: return float(str(value).replace(",", ""))
    except (TypeError, ValueError): return None
def _try_date(value: str) -> bool:
    for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%Y-%m-%d %H:%M:%S", "%m/%d/%Y"):
        try: datetime.strptime(value, fmt); return True
        except ValueError: pass
    return False
def _is_date_like(values: list[Any]) -> bool:
    nonempty = [str(v).strip() for v in values if not _missing(v)]
    if not nonempty: return False
    return sum(bool(_DATE_RE.match(v)) for v in nonempty) / len(nonempty) >= .8 or sum(_try_date(v) for v in nonempty[:100]) / min(100, len(nonempty)) >= .8
def inspect_schema(dataset: dict[str, Any]) -> dict[str, Any]:
    rows, columns = dataset["rows"], dataset["columns"]
    profile: dict[str, Any] = {}
    for column in columns:
        values = [row.get(column) for row in rows]; nums = [_number(v) for v in values]
        numeric = sum(v is not None for v in nums) >= max(1, int(.8 * len(values)))
        nonmissing = [v for v in values if not _missing(v)]; counter = Counter(str(v) for v in nonmissing)
        entry: dict[str, Any] = {"dtype": "numeric" if numeric else ("datetime" if _is_date_like(values) else "categorical"), "rows": len(values), "missing_count": len(values)-len(nonmissing), "missing_rate": round((len(values)-len(nonmissing))/max(1,len(values)), 6), "unique_count": len(counter), "top_values": dict(counter.most_common(8))}
        if numeric:
            finite = [v for v in nums if v is not None and math.isfinite(v)]
            if finite: entry.update({"min": min(finite), "max": max(finite), "mean": sum(finite)/len(finite)})
        profile[column] = entry
    return {"row_count": len(rows), "column_count": len(columns), "columns": profile}
def _name_signal(column: str, terms: tuple[str, ...]) -> float:
    lowered = column.lower(); tokens = [t for t in re.split(r"[^a-z0-9]+", lowered) if t]; score = 0.0
    for term in terms:
        t = term.lower()
        if any(ord(ch) > 127 for ch in t): matched = t in lowered
        elif len(t) <= 2: matched = t in tokens
        else: matched = any(token == t or token.startswith(t) for token in tokens)
        if matched: score += .35
    return min(1.0, score)
def profile_columns(dataset: dict[str, Any], schema: dict[str, Any] | None = None) -> dict[str, Any]:
    schema = schema or inspect_schema(dataset); candidates = {"id": [], "target": [], "decision": [], "time": [], "cost": [], "sensitive": [], "leakage": []}
    for column, stats in schema["columns"].items():
        unique_rate = stats["unique_count"] / max(1, stats["rows"]); dtype = stats["dtype"]
        scores = {
            "id": _name_signal(column, ("id", "编号", "账号", "用户")) + (.35 if unique_rate > .98 and dtype == "categorical" else 0),
            "target": _name_signal(column, ("label", "outcome", "target", "result", "default", "fraud", "risk", "结果", "结局", "标签")) + (.2 if dtype == "categorical" and stats["unique_count"] <= 3 else 0),
            "decision": _name_signal(column, ("approved", "decision", "review", "action", "treat", "investigat", "申请", "审批", "决策", "复核")) + (.3 if dtype == "categorical" and stats["unique_count"] <= 4 else 0),
            "cost": _name_signal(column, ("cost", "price", "expense", "loss", "exposure", "minutes", "费用", "成本", "耗时", "损失")) + (.3 if dtype == "numeric" else 0),
            "sensitive": _name_signal(column, ("sex", "gender", "race", "age", "ethnic", "protected", "性别", "年龄", "民族")),
            "leakage": _name_signal(column, ("post", "future", "settled", "after", "事后", "最终", "结算")),
        }
        for key, score in scores.items():
            if score >= .35: candidates[key].append({"column": column, "confidence": round(min(score, .99), 2)})
        if dtype == "datetime": candidates["time"].append({"column": column, "confidence": .8})
    for key in candidates: candidates[key].sort(key=lambda x: x["confidence"], reverse=True)
    return candidates
