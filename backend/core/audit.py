"""Audit trail helper."""

from .models import AuditLog


def record_audit_log(actor, action: str, detail: str):
    """Insert one AuditLog row, best-effort (never breaks an API call)."""
    try:
        AuditLog.objects.create(actor=actor, action=action, detail=detail)
    except Exception:  # pragma: no cover - audit must never block requests
        pass


def audit(actor, action: str, detail: str):
    """Public alias kept for readability at call sites."""
    record_audit_log(actor, action, detail)
