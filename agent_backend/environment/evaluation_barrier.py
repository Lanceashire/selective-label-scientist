from __future__ import annotations


class EvaluationBarrier:
    def __init__(self) -> None:
        self.research_plan_locked = False
        self.final_evaluation_revealed = False

    def lock_research_plan(self) -> dict[str, bool]:
        if self.final_evaluation_revealed:
            raise RuntimeError("final evaluation 已揭示，不能重新锁定")
        self.research_plan_locked = True
        return {"research_plan_locked": True, "final_evaluation_revealed": False}

    def reveal(self, metrics: dict) -> dict:
        if not self.research_plan_locked:
            raise RuntimeError("必须先 lock_research_plan")
        if self.final_evaluation_revealed:
            raise RuntimeError("final evaluation 只能揭示一次")
        self.final_evaluation_revealed = True
        return {"final_evaluation_revealed": True, "metrics": metrics}

    def assert_research(self) -> None:
        if self.final_evaluation_revealed:
            raise RuntimeError("final evaluation 后禁止 adaptive research")

