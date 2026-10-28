"""
Core data models:

* SIWESSession - one training session (e.g. "2025/2026 Session").
* Placement    - links a student to an organization + supervisor + session.
* AuditLog     - trail of important administrative/review actions.
"""
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models


class SIWESSession(models.Model):
    """A training session inside which SIWES placements take place."""

    name = models.CharField(max_length=120, unique=True)
    start_date = models.DateField()
    end_date = models.DateField()
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-start_date"]

    def __str__(self) -> str:
        return self.name

    def clean(self):
        if self.end_date and self.start_date and self.end_date < self.start_date:
            raise ValidationError("Session end date cannot be earlier than the start date.")


class Placement(models.Model):
    """
    Assignment of one student to:
      * an organization,
      * a supervisor,
      * a SIWES session.

    Placed here instead of on StudentProfile so that administration and
    monitoring share exactly one consistent definition of "who is where".
    """

    student = models.OneToOneField(
        "students.StudentProfile",
        on_delete=models.CASCADE,
        related_name="placement",
    )
    organization = models.ForeignKey(
        "organizations.Organization",
        on_delete=models.PROTECT,
        related_name="placements",
        null=True,
        blank=True,
    )
    supervisor = models.ForeignKey(
        "supervisors.SupervisorProfile",
        on_delete=models.PROTECT,
        related_name="placements",
        null=True,
        blank=True,
    )
    siwes_session = models.ForeignKey(
        SIWESSession,
        on_delete=models.PROTECT,
        related_name="placements",
        null=True,
        blank=True,
    )
    start_date = models.DateField(null=True, blank=True)
    end_date = models.DateField(null=True, blank=True)
    is_active = models.BooleanField(default=True)  # False = placement completed/withdrawn
    remarks = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self) -> str:
        return f"{self.student} -> {self.organization or 'unassigned'}"

    def clean(self):
        if self.start_date and self.end_date and self.end_date < self.start_date:
            raise ValidationError("Placement end date cannot be earlier than start date.")


class AuditLog(models.Model):
    """Who did what and when (kept even after records are edited)."""

    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="audit_actions",
    )
    action = models.CharField(max_length=120)
    detail = models.TextField(blank=True)
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-timestamp"]
