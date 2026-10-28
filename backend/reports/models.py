"""WeeklyReport - one week of a student's industrial training summary."""

from django.utils import timezone
from django.db import models


class WeeklyReport(models.Model):
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
        related_name="weekly_reports",
    )
    week_start = models.DateField("Week start (Monday)")
    week_end = models.DateField("Week end", null=True, blank=True)
    summary_of_activities = models.TextField("Summary of the week's activities")
    challenges_faced = models.TextField(blank=True)
    lessons_learned = models.TextField(blank=True)
    skills_acquired = models.CharField(max_length=250, blank=True)

    status = models.CharField(max_length=20, choices=STATUSES, default=STATUS_DRAFT)
    submitted_at = models.DateTimeField(null=True, blank=True)

    supervisor = models.ForeignKey(
        "supervisors.SupervisorProfile",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="reviewed_reports",
    )
    supervisor_comment = models.TextField(blank=True)
    reviewed_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-week_start"]
        constraints = [
            models.UniqueConstraint(
                fields=["student", "week_start"],
                name="unique_weekly_report_per_student_per_week",
            )
        ]
        indexes = [
            models.Index(fields=["student", "status"]),
        ]

    def __str__(self) -> str:
        return f"{self.student} - week of {self.week_start}"

    @property
    def is_editable(self) -> bool:
        return self.status in (self.STATUS_DRAFT, self.STATUS_REJECTED)

    @staticmethod
    def week_bounds_for(monday):
        """Given a Monday date, return realistic week date range."""
        from datetime import timedelta

        return monday, monday + timedelta(days=6)
