"""In-app notification model."""

from django.conf import settings
from django.db import models


class Notification(models.Model):
    """One message for one recipient (created by other apps' actions)."""

    recipient = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="notifications",
    )
    kind = models.CharField(max_length=40, blank=True)
    title = models.CharField(max_length=150)
    body = models.TextField(blank=True)
    target_url = models.CharField(max_length=200, blank=True, help_text="Relative frontend page link")
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["recipient", "is_read"]),
        ]

    def __str__(self) -> str:
        return f"{self.recipient} - {self.title}"
