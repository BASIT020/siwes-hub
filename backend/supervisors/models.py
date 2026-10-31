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
    # Administrator decisions (kept so the trail is queryable, not only in the
    # audit log): approve/reject actions stamp these; re-approval wipes the
    # rejection fields again.
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="supervisors_approved",
    )
    approved_at = models.DateTimeField(null=True, blank=True)
    rejected_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="supervisors_rejected",
    )
    rejected_at = models.DateTimeField(null=True, blank=True)
    rejected_reason = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["user__full_name"]

    def __str__(self) -> str:
        name = self.user.full_name or self.user.username
        return f"{name}".strip()

    @property
    def status(self) -> str:
        """Application status for the approval queue: pending -> approved
        (or rejected), then optionally deactivated later by the office."""
        if self.is_pending:
            return "pending"
        if self.is_active:
            return "approved"
        if self.rejected_at:
            return "rejected"
        return "inactive"
