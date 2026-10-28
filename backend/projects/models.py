"""StudentProject - the SIWES-related project of each student (one per student)."""

from django.utils import timezone
from django.db import models


class StudentProject(models.Model):
    PROJECT_STATUSES = [
        ("in_progress", "In progress"),
        ("completed", "Completed"),
        ("presented", "Presented"),
    ]
    REVIEW_NOT_SUBMITTED = "not_submitted"
    REVIEW_SUBMITTED = "submitted"
    REVIEW_APPROVED = "approved"
    REVIEW_REJECTED = "rejected"
    REVIEW_STATUSES = [
        (REVIEW_NOT_SUBMITTED, "Not yet submitted for review"),
        (REVIEW_SUBMITTED, "Awaiting supervisor review"),
        (REVIEW_APPROVED, "Approved"),
        (REVIEW_REJECTED, "Rejected - corrections requested"),
    ]

    student = models.OneToOneField(
        "students.StudentProfile",
        on_delete=models.CASCADE,
        related_name="project",
    )
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    objectives = models.TextField(blank=True)
    technologies = models.CharField(max_length=250, blank=True, help_text="Comma-separated list")
    status = models.CharField(max_length=20, choices=PROJECT_STATUSES, default="in_progress")

    review_status = models.CharField(max_length=20, choices=REVIEW_STATUSES, default=REVIEW_NOT_SUBMITTED)
    submitted_at = models.DateTimeField(null=True, blank=True)
    reviewed_at = models.DateTimeField(null=True, blank=True)
    supervisor = models.ForeignKey(
        "supervisors.SupervisorProfile",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="reviewed_projects",
    )
    supervisor_comment = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-updated_at"]

    def __str__(self) -> str:
        return f"{self.student} - {self.title}"

    @property
    def is_editable(self) -> bool:
        return self.review_status in (self.REVIEW_NOT_SUBMITTED, self.REVIEW_REJECTED)
