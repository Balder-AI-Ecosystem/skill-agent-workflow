from .base import BaseWorkflow
from typing import Any

class EmailWorkflow(BaseWorkflow):
    DOMAIN = "email"
    ALLOWED_STEPS = [
        "read_email", "analyze_email", "detect_priority",
        "draft_email", "summarize_email", "label_email",
    ]
    # Level 2: mode-parameterized skeleton
    MODE_PATHS = {
        "triage":    ["read_email", "detect_priority", "label_email"],
        "reply":     ["read_email", "analyze_email", "detect_priority", "draft_email"],
        "digest":    ["read_email", "summarize_email"],
        "summarize": ["read_email", "summarize_email"],
    }

    def run(self, params: dict[str, Any]) -> dict[str, Any]:
        mode = str(params.get("mode") or "summarize").strip()
        steps = self.MODE_PATHS.get(mode, self.MODE_PATHS["summarize"])

        # Level 3: AdaptivePathPlanner có thể overwrite steps nếu cần
        from ..planner import AdaptivePathPlanner
        planner = AdaptivePathPlanner(domain=self.DOMAIN, allowed_steps=self.ALLOWED_STEPS)
        steps = planner.adapt(steps, params)   # chỉ được trim/thêm trong ALLOWED_STEPS

        context = dict(params.get("parameters") or {})
        trace: list[dict] = []

        for step in steps:
            result = self._dispatch_skill(
                capability=f"email.{step}",    # gọi skill-office-mail
                parameters=context,
            )
            if result:
                context.update(result)
                trace.append({"step": step, "ok": True})
            else:
                trace.append({"step": step, "ok": False, "skipped": True})

        return {"mode": mode, "steps_trace": trace, "output": context}
