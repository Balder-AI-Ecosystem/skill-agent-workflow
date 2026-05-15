from .base import BaseWorkflow
from typing import Any

class ResearchWorkflow(BaseWorkflow):
    DOMAIN = "research"
    ALLOWED_STEPS = ["query_search", "fetch_content", "extract_info", "synthesize_report"]
    MODE_PATHS = {
        "search": ["query_search"],
        "extract": ["fetch_content", "extract_info"],
        "summarize": ["fetch_content", "synthesize_report"],
        "synthesize": ["query_search", "fetch_content", "extract_info", "synthesize_report"]
    }

    def run(self, params: dict[str, Any]) -> dict[str, Any]:
        mode = str(params.get("mode") or "search").strip()
        steps = self.MODE_PATHS.get(mode, [])
        
        from ..planner import AdaptivePathPlanner
        planner = AdaptivePathPlanner(domain=self.DOMAIN, allowed_steps=self.ALLOWED_STEPS)
        steps = planner.adapt(steps, params)

        context = dict(params.get("parameters") or {})
        trace: list[dict] = []

        for step in steps:
            result = self._dispatch_skill(
                capability=f"research.{step}",
                parameters=context,
            )
            if result:
                context.update(result)
                trace.append({"step": step, "ok": True})
            else:
                trace.append({"step": step, "ok": False, "skipped": True})

        return {"mode": mode, "steps_trace": trace, "output": context}
