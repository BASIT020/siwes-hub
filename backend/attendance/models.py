"""Attendance tracking model.

Students do NOT record their own attendance: only an assigned supervisor (or
an administrator) may create/verify attendance, which prevents students from
fabricating supervisor-verified records.
"""

from django.conf import settings
from django.db import models


class Attendance(models.Model):
    STATUS_PRESENT = "present"
    STATUS_ABSENT = "absent"
    STATUS_LATE = "late"
    STATUS_EXCUSED = "excused"
    STATUSES = [
        (STATUS_PRESENT, "Present"),
        (STATUS_ABSENT, "Absent"),
        (STATUS_LATE, "Late"),
        (STATUS_EXCUSED, "Excused"),
    ]

    student = models.ForeignKey(
        "students.StudentProfile",
        on_delete=models.CASCADE,
        related_name="attendance_records",
    )
    date = models.DateField()
    status = models.CharField(max_length=20, choices=STATUSES)
    note = models.CharField(max_length=250, blank=True)
    recorded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="attendance_records_made",
    )
    verified_by = models.ForeignKey(
        "supervisors.SupervisorProfile",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="verified_attendance",
    )
    verified_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-date"]
        constraints = [
            models.UniqueConstraint(
                fields=["student", "date"],
                name="unique_attendance_per_student_per_date",
            )
        ]
        indexes = [
            models.Index(fields=["student", "date"]),
        ]

    def __str__(self) -> str:
        return f"{self.student} - {self.date} ({self.status})"
