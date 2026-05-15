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
