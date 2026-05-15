# Blueprint: `skill-agent-workflow` — Adaptive Business Workflow Skill Repo

> Dựa trên phân tích `ideaAgentWorkFlow.md` và chuẩn skill-contract của JARVIS core.

---

## 1. Tổng quan kiến trúc

```
Core Router
    │
    ▼
skill-agent-workflow  (local_plugin hoặc service mode)
    │
    ├── WorkflowSelector          ← chọn domain workflow đúng
    │       │
    │       ├── EmailWorkflow
    │       ├── CalendarWorkflow
    │       ├── ResearchWorkflow
    │       └── ... (mở rộng thêm domain)
    │
    └── AdaptivePathPlanner       ← agent nhỏ bên trong workflow
            │                       chọn sub-skill path phù hợp
            ├── allowed_steps
            ├── guardrail policy
            └── gọi lại skill-* khác qua core skill dispatch
```

**Nguyên tắc cốt lõi từ ideaAgentWorkFlow.md:**
- Workflow = khung cố định (xương sống)
- Agent = lớp thích nghi nhẹ bên trong (cơ bắp linh hoạt)
- Router chọn đúng domain → Workflow giữ đúng khung → Agent chỉ adapt bên trong khung đó

---

## 2. Cấu trúc repo

```
D:\Autobot\skill-agent-workflow\
│
├── skill.yaml                        # manifest chuẩn core contract
├── pyproject.toml
├── README.md
│
├── src/
│   └── skill_agent_workflow/
│       ├── __init__.py
│       ├── main.py                   # entrypoint → class Skill(BaseSkill)
│       │
│       ├── selector.py               # WorkflowSelector: ánh xạ intent → domain
│       ├── planner.py                # AdaptivePathPlanner: chọn sub-skill path
│       ├── guardrails.py             # policy checks, allowed_steps per domain
│       │
│       ├── workflows/
│       │   ├── __init__.py
│       │   ├── base.py               # BaseWorkflow ABC
│       │   ├── email.py              # EmailWorkflow
│       │   ├── calendar.py           # CalendarWorkflow
│       │   └── research.py          # ResearchWorkflow
│       │
│       └── settings.py               # lazy-load config, không import core eagerly
│
└── tests/
    ├── test_manifest.py
    ├── test_selector.py
    ├── test_planner.py
    ├── test_email_workflow.py
    └── test_guardrails.py
```

---

## 3. `skill.yaml` — manifest chuẩn

```yaml
name: skill-agent-workflow
version: 0.1.0
mode: local_plugin
entrypoint: src.skill_agent_workflow.main:Skill
core_api: ">=1.0,<2.0"

capabilities:
  - id: workflow.email.run
    description: Run adaptive email workflow (triage / reply / digest / summarize).
    input_schema:
      type: object
      properties:
        intent:      { type: string }
        parameters:  { type: object }
        mode:        { type: string, enum: [triage, reply, digest, summarize] }
        session_id:  { type: string }
      required: [intent]
    output_schema:
      type: object
    risk_level: medium
    confirmation_required: false
    retry_policy: bounded_backoff
    observability_events:
      - workflow.email.run

  - id: workflow.calendar.run
    description: Run adaptive calendar workflow (schedule / reschedule / check_conflicts).
    input_schema:
      type: object
      properties:
        intent:      { type: string }
        parameters:  { type: object }
        mode:        { type: string, enum: [schedule, reschedule, check_conflicts] }
        session_id:  { type: string }
      required: [intent]
    output_schema:
      type: object
    risk_level: medium
    confirmation_required: false
    retry_policy: bounded_backoff
    observability_events:
      - workflow.calendar.run

  - id: workflow.research.run
    description: Run adaptive research workflow (search / summarize / extract / synthesize).
    input_schema:
      type: object
      properties:
        intent:      { type: string }
        parameters:  { type: object }
        mode:        { type: string, enum: [search, summarize, extract, synthesize] }
        session_id:  { type: string }
      required: [intent]
    output_schema:
      type: object
    risk_level: low
    confirmation_required: false
    retry_policy: bounded_backoff
    observability_events:
      - workflow.research.run

  - id: workflow.plan
    description: >
      Lightweight intent → domain planner. Returns which workflow + mode 
      should handle a given user request, without executing.
    input_schema:
      type: object
      properties:
        intent: { type: string }
      required: [intent]
    output_schema:
      type: object
    risk_level: low
    confirmation_required: false
    retry_policy: none
    observability_events:
      - workflow.plan

healthcheck:
  kind: local
  module: src.skill_agent_workflow.main
  method: healthcheck

permissions:
  read_skills_registry: true     # cần đọc registry để gọi skill-* phụ
  dispatch_skill_calls: true     # gọi sub-skill qua core service_dispatch
timeout_ms: 90000
enabled_by_default: true
```

---

## 4. `main.py` — entrypoint Skill class (skeleton)

```python
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

from ecosystem.contracts import HealthSnapshot, TaskRequest, TaskResult  # noqa
from ecosystem.skills import BaseSkill, SkillCapability, SkillManifest   # noqa

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
            (Path(__file__).parents[3] / "skill.yaml").read_text(encoding="utf-8")
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
        capability = str(request.capability or "").strip()
        params = dict(request.parameters or {})
        task_id = str(request.task_id or "")
        session_id = request.session_id

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
```

---

## 5. `selector.py` — WorkflowSelector

```python
_CAPABILITY_TO_DOMAIN = {
    "workflow.email.run":    "email",
    "workflow.calendar.run": "calendar",
    "workflow.research.run": "research",
}

class WorkflowSelector:
    def resolve(self, capability: str, params: dict) -> tuple[str, type]:
        domain = _CAPABILITY_TO_DOMAIN.get(capability)
        if not domain:
            raise ValueError(f"Unknown workflow capability: {capability}")
        workflow_cls = _load_workflow_cls(domain)
        return domain, workflow_cls

    def plan(self, intent: str) -> dict:
        """Trả về domain + suggested mode, không execute."""
        # TODO: dùng LLM nhỏ (Gemma local) hoặc keyword heuristic
        intent_lower = intent.lower()
        if any(w in intent_lower for w in ["mail", "email", "inbox", "reply", "draft"]):
            return {"domain": "email", "capability": "workflow.email.run",
                    "suggested_mode": _suggest_email_mode(intent_lower)}
        if any(w in intent_lower for w in ["lịch", "calendar", "meeting", "schedule"]):
            return {"domain": "calendar", "capability": "workflow.calendar.run",
                    "suggested_mode": "schedule"}
        if any(w in intent_lower for w in ["tìm", "search", "research", "nghiên cứu"]):
            return {"domain": "research", "capability": "workflow.research.run",
                    "suggested_mode": "search"}
        return {"domain": "unknown", "capability": None, "suggested_mode": None}

def _suggest_email_mode(intent: str) -> str:
    if any(w in intent for w in ["triage", "lọc", "phân loại"]): return "triage"
    if any(w in intent for w in ["reply", "trả lời", "soạn"]): return "reply"
    if any(w in intent for w in ["digest", "tóm tắt ngày"]): return "digest"
    return "summarize"

def _load_workflow_cls(domain: str) -> type:
    if domain == "email":
        from .workflows.email import EmailWorkflow
        return EmailWorkflow
    if domain == "calendar":
        from .workflows.calendar import CalendarWorkflow
        return CalendarWorkflow
    if domain == "research":
        from .workflows.research import ResearchWorkflow
        return ResearchWorkflow
    raise ValueError(f"No workflow for domain: {domain}")
```

---

## 6. `workflows/base.py` — BaseWorkflow

```python
from abc import ABC, abstractmethod
from typing import Any

class BaseWorkflow(ABC):
    """Static skeleton. Subclasses define allowed steps và run()."""

    ALLOWED_STEPS: list[str] = []           # guardrail: steps được phép
    DOMAIN: str = ""

    def __init__(self, task_id: str, session_id: str | None = None):
        self.task_id = task_id
        self.session_id = session_id

    @abstractmethod
    def run(self, params: dict[str, Any]) -> dict[str, Any]:
        """Execute workflow. Adaptive path planner lives here."""
        ...

    def _dispatch_skill(self, capability: str, parameters: dict) -> dict | None:
        """Gọi skill-* khác qua core service_dispatch."""
        from ecosystem.skills import execute_service_skill_sync
        return execute_service_skill_sync(
            capability=capability,
            parameters=parameters,
            task_id=self.task_id,
            session_id=self.session_id,
        )
```

---

## 7. `workflows/email.py` — EmailWorkflow (Level 1 → Level 2 → Level 3)

```python
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
```

---

## 8. `planner.py` — AdaptivePathPlanner

```python
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
```

---

## 9. `guardrails.py` — Policy

```python
_DOMAIN_POLICIES: dict[str, dict] = {
    "email": {
        "require_confirm_before_send": True,
        "max_draft_length": 2000,
        "allowed_modes": ["triage", "reply", "digest", "summarize"],
    },
    "calendar": {
        "require_confirm_before_create": True,
        "allowed_modes": ["schedule", "reschedule", "check_conflicts"],
    },
    "research": {
        "allowed_modes": ["search", "summarize", "extract", "synthesize"],
    },
}

class GuardrailPolicy:
    def check(self, domain: str, params: dict) -> None:
        policy = _DOMAIN_POLICIES.get(domain, {})
        mode = str(params.get("mode") or "").strip()
        allowed_modes = policy.get("allowed_modes", [])
        if allowed_modes and mode and mode not in allowed_modes:
            raise PermissionError(f"Mode '{mode}' not allowed in domain '{domain}'")
```

---

## 10. Đăng ký vào `config/skills_registry.yaml`

Sau khi tạo repo xong, thêm entry vào core:

```yaml
  - name: skill-agent-workflow
    path: D:\Autobot\skill-agent-workflow
    mode: local_plugin
    enabled: true
    manifest: D:\Autobot\skill-agent-workflow\skill.yaml
    core_api: ">=1.0,<2.0"
```

---

## 11. Core-side integration — cách core gọi skill này

```python
from ecosystem.skills import execute_service_skill_sync

# Bước 1: hỏi kế hoạch (không execute)
plan = execute_service_skill_sync(
    capability="workflow.plan",
    parameters={"intent": "Xem mail khách A, nếu gấp thì soạn trả lời"},
    task_id=task_id,
)
# → {"domain": "email", "capability": "workflow.email.run", "suggested_mode": "reply"}

# Bước 2: execute workflow
result = execute_service_skill_sync(
    capability="workflow.email.run",
    parameters={
        "intent": "Xem mail khách A, nếu gấp thì soạn trả lời",
        "mode": plan["output"]["suggested_mode"],
        "parameters": {"query": "from:khach_a@example.com"},
    },
    task_id=task_id,
)
```

---

## 12. Lộ trình triển khai 3 giai đoạn

### Giai đoạn 1 — Fixed Workflow (MVP)
| Mục tiêu | Nội dung |
|---|---|
| Repo skeleton | `skill.yaml`, `main.py`, `selector.py`, `guardrails.py` |
| EmailWorkflow Level 1 | 4 mode cố định, gọi `skill-office-mail` |
| Tests | manifest test, selector test, guardrail test |
| Registry | Đăng ký vào `skills_registry.yaml` |

**Deliverable:** `workflow.email.run` + `workflow.plan` hoạt động qua `execute_service_skill_sync`.

---

### Giai đoạn 2 — Parameterized Workflow
| Mục tiêu | Nội dung |
|---|---|
| CalendarWorkflow | 3 mode: schedule/reschedule/check_conflicts |
| ResearchWorkflow | 4 mode: search/summarize/extract/synthesize |
| AdaptivePathPlanner | Rule-based adapter (không dùng LLM, chỉ rule) |
| Observability | Emit events qua `observability_events` |

**Deliverable:** 3 domain đầy đủ, planner rule-based, bắt đầu dùng trong production.

---

### Giai đoạn 3 — Adaptive Workflow Agent
| Mục tiêu | Nội dung |
|---|---|
| LLM Planner | `AdaptivePathPlanner` dùng Gemma local để chọn path |
| Dynamic mode resolution | `workflow.plan` dùng LLM thay keyword heuristic |
| Multi-step chaining | Workflow có thể gọi workflow khác nếu domain chain |
| Guardrail nâng cao | Rate-limit, cost budget, domain isolation strict |

**Deliverable:** Workflow thật sự tự adaptive có kiểm soát, ready cho autonomy loop.

---

## 13. `pyproject.toml` (skeleton)

```toml
[project]
name = "skill-agent-workflow"
version = "0.1.0"
requires-python = ">=3.11"
dependencies = [
    "pyyaml>=6.0",
    "httpx>=0.27",
]

[project.optional-dependencies]
dev = ["pytest>=8.0", "pytest-asyncio"]
```

---

## 14. Checklist trước khi merge

- [ ] `python -c "from src.skill_agent_workflow.main import Skill; print(Skill().manifest())"` không lỗi
- [ ] `Skill().manifest().validate()` trả về `[]`
- [ ] `Skill().healthcheck().status == "available"`
- [ ] Test selector: mỗi domain → đúng workflow class
- [ ] Test guardrail: mode không hợp lệ → `PermissionError`
- [ ] Entry trong `skills_registry.yaml` được load bởi `SkillRepoRegistry`
- [ ] `execute_service_skill_sync(capability="workflow.plan", ...)` trả về đúng structure

---

## 15. Quy tắc bất biến (không phá vỡ trong mọi giai đoạn)

1. **Không import core eagerly** ở module-load time — chỉ lazy import sau `_ensure_core_repo_on_path()`.
2. **Không emit `core_repo` / `skill_repo` path** trong payload trả về core.
3. **Workflow không gọi skill ngoài domain của mình** — mọi cross-domain call phải qua `workflow.plan` của chính skill này.
4. **AdaptivePathPlanner không thể thêm step ngoài `ALLOWED_STEPS`** — guardrail cứng.
5. **mode: local_plugin** cho Giai đoạn 1–2; chỉ chuyển sang `service` nếu workflow cần long-running async ở Giai đoạn 3.
