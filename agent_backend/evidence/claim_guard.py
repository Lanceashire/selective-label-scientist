from __future__ import annotations

from typing import Any


def claim_guard(claim: str, evidence: dict[str, Any], domain: str = "unknown") -> dict[str, Any]:
    lowered = claim.lower()
    forbidden = []
    if "所有领域" in claim or "all domains" in lowered:
        forbidden.append("缺少跨领域证据")
    if "真实安全风险" in claim or "real-world safety" in lowered:
        forbidden.append("代理成本不能等同真实伤害")
    if "一定优于" in claim or "always better" in lowered:
        forbidden.append("不能把单次策略比较写成普遍最优")
    status = "BLOCKED" if forbidden else "ALLOWED_WITH_LIMITATIONS"
    return {"claim": claim, "evidence": evidence, "scope": domain, "limitations": forbidden or ["仅限当前数据、预算、种子和可见证据"], "status": status}

