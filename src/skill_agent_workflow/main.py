from __future__ import annotations
from pathlib import Path
from typing import Any
import os, sys

# ── bootstrap core repo ────────────────────────────────────────────────────────
def _ensure_core_repo_on_path() -> None:
    configured = str(os.getenv("AUTOBOT_CORE_REPO", "")).strip()
    candidates = [Path(configured)] if configured else []
    candidates += [Path(__file__).resolve().parents[3]]
    for c in candidates:
        if c.is_dir() and (c / "ecosystem").is_dir():
            if str(c) not in sys.path:
                sys.path.insert(0, str(c))
            return
    raise RuntimeError("Cannot locate core repo. Set AUTOBOT_CORE_REPO.")

_ensure_core_repo_on_path()

try:
    from ecosystem.contracts import HealthSnapshot, TaskRequest, TaskResult  # noqa
    from ecosystem.skills import BaseSkill, SkillCapability, SkillManifest   # noqa
except ImportError:
    # Dummy classes for standalone testing if ecosystem is not available
    class BaseSkill: pass
    class HealthSnapshot:
        def __init__(self, **kwargs): pass
    class TaskRequest: pass
    class TaskResult:
        def __init__(self, **kwargs): pass
    class SkillCapability:
        def __init__(self, **kwargs): pass
    class SkillManifest:
        def __init__(self, **kwargs): pass

# ── lazy internal imports ───────────────────────────────────────────────────────
def _selector():
    from .selector import WorkflowSelector
    return WorkflowSelector()

def _guardrails():
    from .guardrails import GuardrailPolicy
    return GuardrailPolicy()


class Skill(BaseSkill):
    def manifest(self) -> SkillManifest:
        import yaml
        raw = yaml.safe_load(
            (Path(__file__).parents[2] / "skill.yaml").read_text(encoding="utf-8")
        )
        caps = [SkillCapability(**c) for c in raw.get("capabilities", [])]
        svc = raw.get("service", {})
        return SkillManifest(
            name=raw["name"],
            version=raw["version"],
            mode=raw["mode"],
            entrypoint=raw["entrypoint"],
            core_api=raw["core_api"],
            capabilities=caps,
            healthcheck=raw.get("healthcheck", {}),
            permissions=raw.get("permissions", {}),
            timeout_ms=raw.get("timeout_ms", 90000),
            enabled_by_default=raw.get("enabled_by_default", True),
            service=svc,
        )

    def healthcheck(self) -> HealthSnapshot:
        return HealthSnapshot(status="available", detail="skill-agent-workflow ready")

    def execute(self, request: TaskRequest) -> TaskResult:
        capability = str(getattr(request, "capability", "")).strip()
        params = dict(getattr(request, "parameters", {}) or {})
        task_id = str(getattr(request, "task_id", ""))
        session_id = getattr(request, "session_id", None)

        selector = _selector()
        guardrails = _guardrails()

        try:
            if capability == "workflow.plan":
                plan = selector.plan(params.get("intent", ""))
                return TaskResult(
                    task_id=task_id,
                    status="completed",
                    artifacts={"result": plan},
                )

            # Resolve domain workflow
            domain, workflow_cls = selector.resolve(capability, params)
            guardrails.check(domain, params)
            workflow = workflow_cls(task_id=task_id, session_id=session_id)
            result = workflow.run(params)
            return TaskResult(
                task_id=task_id,
                status="completed",
                artifacts={"result": result},
            )
        except PermissionError as exc:
            return TaskResult(task_id=task_id, status="blocked", detail=str(exc))
        except Exception as exc:
            return TaskResult(task_id=task_id, status="failed", detail=str(exc))
