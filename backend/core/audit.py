"""Audit trail helper."""

import logging

from .models import AuditLog

logger = logging.getLogger(__name__)


def record_audit_log(actor, action: str, detail: str):
    """Insert one AuditLog row, best-effort (never breaks an API call).

    Failures are logged loudly instead of silently swallowed so a broken
    audit write leaves its own trace in the error log.
    """
    try:
        AuditLog.objects.create(actor=actor, action=action, detail=detail)
    except Exception:  # noqa: BLE001 - audit must never block requests
        logger.exception("Audit write failed for action '%s' by actor '%s'", action, getattr(actor, "username", actor))


def audit(actor, action: str, detail: str):
    """Public alias kept for readability at call sites."""
    record_audit_log(actor, action, detail)
