"""Supervisor model."""

from django.conf import settings
from django.db import models


class SupervisorProfile(models.Model):
    """Extended information of a user with the Supervisor role."""

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="supervisor_profile",
    )
    staff_id = models.CharField(max_length=30, blank=True)
    title = models.CharField("Job title", max_length=80, blank=True, help_text="e.g. Dr., Mr., Engr.")
    department = models.CharField(max_length=120, blank=True)
    is_active = models.BooleanField(default=True)
    # Set when the supervisor self-registered on the public page and the user
    # account is still awaiting administrator approval; cleared once approved
    # (or once the request is rejected/deactivated by the SIWES office).
    is_pending = models.BooleanField("Awaiting approval", default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["user__full_name"]

    def __str__(self) -> str:
        name = self.user.full_name or self.user.username
        return f"{name}".strip()
