from typing import Any

class AdaptivePathPlanner:
    """
    Agent nhỏ: nhận static steps, trả về adapted steps.
    Chỉ được thêm/bớt bước nằm trong allowed_steps. 
    Không được đổi domain hay gọi skill ngoài domain.
    """
    def __init__(self, domain: str, allowed_steps: list[str]):
        self.domain = domain
        self.allowed_steps = allowed_steps

    def adapt(self, steps: list[str], params: dict[str, Any]) -> list[str]:
        """
        Level 2: pass-through (không làm gì).
        Level 3: override bằng LLM planner hoặc rule engine.
        """
        # Chỉ giữ các bước nằm trong allowed_steps (guardrail cứng)
        return [s for s in steps if s in self.allowed_steps]
