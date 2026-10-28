"""Notification creation helper (used by other applications)."""
from .models import Notification


def notify(recipient, kind: str, title: str, body: str = "", target_url: str = ""):
    """Create one notification for a user; never raises on failure."""
    try:
        Notification.objects.create(
            recipient=recipient,
            kind=kind,
            title=title[:150],
            body=body,
            target_url=target_url,
        )
    except Exception:  # pragma: no cover
        pass
