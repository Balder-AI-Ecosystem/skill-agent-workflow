from .base import BaseWorkflow
from typing import Any

class CalendarWorkflow(BaseWorkflow):
    DOMAIN = "calendar"
    ALLOWED_STEPS = ["check_availability", "create_event", "update_event", "notify_participants"]
    MODE_PATHS = {
        "schedule": ["check_availability", "create_event", "notify_participants"],
        "reschedule": ["check_availability", "update_event", "notify_participants"],
        "check_conflicts": ["check_availability"]
    }

    def run(self, params: dict[str, Any]) -> dict[str, Any]:
        mode = str(params.get("mode") or "schedule").strip()
        steps = self.MODE_PATHS.get(mode, [])
        
        from ..planner import AdaptivePathPlanner
        planner = AdaptivePathPlanner(domain=self.DOMAIN, allowed_steps=self.ALLOWED_STEPS)
        steps = planner.adapt(steps, params)

        context = dict(params.get("parameters") or {})
        trace: list[dict] = []

        for step in steps:
            result = self._dispatch_skill(
                capability=f"calendar.{step}",
                parameters=context,
            )
            if result:
                context.update(result)
                trace.append({"step": step, "ok": True})
            else:
                trace.append({"step": step, "ok": False, "skipped": True})

        return {"mode": mode, "steps_trace": trace, "output": context}
