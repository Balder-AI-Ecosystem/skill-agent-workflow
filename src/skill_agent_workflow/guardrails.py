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
