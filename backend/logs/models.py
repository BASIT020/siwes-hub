r"""
DailyLog - one day of a student's industrial training activity.

Lifecycle:
    DRAFT -> SUBMITTED -> APPROVED
                      \-> REJECTED -> (edit) -> SUBMITTED ...

Only the submitting student creates/edits drafts, and only the assigned
supervisor (or, defensively, no one else) may review submissions.
"""
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models


class DailyLog(models.Model):
    STATUS_DRAFT = "draft"
    STATUS_SUBMITTED = "submitted"
    STATUS_APPROVED = "approved"
    STATUS_REJECTED = "rejected"
    STATUSES = [
        (STATUS_DRAFT, "Draft"),
        (STATUS_SUBMITTED, "Submitted for review"),
        (STATUS_APPROVED, "Approved"),
        (STATUS_REJECTED, "Rejected"),
    ]

    student = models.ForeignKey(
        "students.StudentProfile",
        on_delete=models.CASCADE,
        related_name="daily_logs",
    )
    log_date = models.DateField()
    activities = models.TextField("Activities performed")
    tools_used = models.CharField("Tools / technologies used", max_length=250, blank=True)
    skills_learned = models.CharField("Skills learned", max_length=250, blank=True)
    hours_spent = models.DecimalField(max_digits=4, decimal_places=1, null=True, blank=True)
    remarks = models.TextField(blank=True, help_text="Student's optional extra remarks")

    status = models.CharField(max_length=20, choices=STATUSES, default=STATUS_DRAFT)
    submitted_at = models.DateTimeField(null=True, blank=True)

    # Review information (STUDENT VIEW IS READ-ONLY FOR THESE FIELDS)
    supervisor = models.ForeignKey(
        "supervisors.SupervisorProfile",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="reviewed_logs",
    )
    supervisor_comment = models.TextField(blank=True)
    reviewed_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-log_date"]
        constraints = [
            models.UniqueConstraint(
                fields=["student", "log_date"],
                name="unique_daily_log_per_student_per_date",
            )
        ]
        indexes = [
            models.Index(fields=["student", "status"]),
        ]

    def __str__(self) -> str:
        return f"{self.student} - {self.log_date}"

    def clean(self):
        """Basic model-level validation, also applied by full_clean()."""
        if self.log_date and self.log_date > timezone_today():
            raise ValidationError("The log date cannot be in the future.")

    # ------------------------------------------------------------------ #
    # State helpers used by the API views
    # ------------------------------------------------------------------ #
    @property
    def is_editable(self) -> bool:
        return self.status in (self.STATUS_DRAFT, self.STATUS_REJECTED)

    def can_be_reviewed_by(self, supervisor_profile) -> bool:
        """Only the supervisor currently assigned through an active placement."""
        student = self.student
        student.refresh_from_db(fields=["id"])
        placement = getattr(student, "placement", None)
        return (
            self.status == self.STATUS_SUBMITTED
            and placement is not None
            and placement.is_active
            and placement.supervisor_id == supervisor_profile.id
        )


def timezone_today():
    from django.utils import timezone

    return timezone.localdate()
