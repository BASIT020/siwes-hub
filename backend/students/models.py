"""Student-specific data models."""

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core.validators import RegexValidator
from django.db import models


class StudentProfile(models.Model):
    """
    Extended information of a user with the Student role.

    Placement (organization, supervisor, session) is stored in core.Placement
    so there is exactly one place where assignments are managed.
    """

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="student_profile",
    )
    matric_number = models.CharField(
        "Matriculation number",
        max_length=30,
        unique=True,
        validators=[
            RegexValidator(
                r"^[A-Za-z0-9/\-.]+$",
                "Matriculation number may contain letters, digits, slashes, dots and hyphens.",
            )
        ],
        help_text="e.g. 230591056",
    )
    department = models.CharField(max_length=120, blank=True)
    faculty = models.CharField(max_length=120, blank=True)
    level = models.CharField(max_length=20, blank=True)
    training_start_date = models.DateField(null=True, blank=True)
    training_end_date = models.DateField(null=True, blank=True)
    is_active = models.BooleanField(default=True)  # deactivated students disappear from dashboards
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["user__full_name", "matric_number"]

    def __str__(self) -> str:
        name = self.user.full_name or self.user.username
        return f"{name} ({self.matric_number})"

    def clean(self):
        if self.training_end_date and self.training_start_date and self.training_end_date < self.training_start_date:
            raise ValidationError("Training end date cannot be earlier than the start date.")

    # ================================================================== #
    # Fields that a student may edit about themselves. Anything else
    # (matriculation number, department changes, dates) belongs to
    # the administrator.
    # ================================================================== #
    EDITABLE_BY_STUDENT = {"department", "faculty", "level"}


class Skill(models.Model):
    """A skill a student says they learned during industrial training."""

    LEVELS = [
        ("beginner", "Beginner"),
        ("intermediate", "Intermediate"),
        ("advanced", "Advanced"),
    ]

    student = models.ForeignKey(
        StudentProfile,
        on_delete=models.CASCADE,
        related_name="skills",
    )
    name = models.CharField(max_length=120)
    description = models.TextField(blank=True)
    date_learned = models.DateField()
    proficiency_level = models.CharField(max_length=20, choices=LEVELS, default="intermediate")
    # optional link to the log where this skill was exercised
    related_activity = models.ForeignKey(
        "logs.DailyLog",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="related_skills",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-date_learned"]
        constraints = [
            models.UniqueConstraint(
                fields=["student", "name"], name="unique_skill_per_student"
            )
        ]

    def __str__(self) -> str:
        return f"{self.name} ({self.student})"
