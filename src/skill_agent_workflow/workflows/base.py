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
        try:
            from ecosystem.skills import execute_service_skill_sync
            return execute_service_skill_sync(
                capability=capability,
                parameters=parameters,
                task_id=self.task_id,
                session_id=self.session_id,
            )
        except ImportError:
            # Dummy cho standalone tests
            print(f"Mock calling {capability} with {parameters}")
            return {"mock_result": f"mock {capability}"}
