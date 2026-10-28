"""
User model for SIWES Hub.

A single user table is used with a "role" field instead of three separate
models for students/supervisors/administrators. The role controls which
permissions the user receives; extra profile details live in the StudentProfile
and SupervisorProfile models (students and supervisors apps).
"""
from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    """Application user with a SIWES Hub role."""

    ROLE_STUDENT = "student"
    ROLE_SUPERVISOR = "supervisor"
    ROLE_ADMIN = "admin"
    ROLES = [
        (ROLE_STUDENT, "Student"),
        (ROLE_SUPERVISOR, "Supervisor"),
        (ROLE_ADMIN, "Administrator"),
    ]

    email = models.EmailField("Email address", blank=True)
    phone = models.CharField("Phone number", max_length=20, blank=True)
    full_name = models.CharField("Full name", max_length=150, blank=True)
    role = models.CharField(max_length=20, choices=ROLES, default=ROLE_STUDENT)

    class Meta:
        ordering = ["-date_joined"]
        indexes = [
            models.Index(fields=["role"]),
        ]

    def __str__(self) -> str:
        return self.full_name or self.username

    # ------------------------------------------------------------------ #
    # Small helpers used across the codebase
    # ------------------------------------------------------------------ #
    @property
    def is_admin_role(self) -> bool:
        return self.role == self.ROLE_ADMIN

    @property
    def is_supervisor_role(self) -> bool:
        return self.role == self.ROLE_SUPERVISOR

    @property
    def is_student_role(self) -> bool:
        return self.role == self.ROLE_STUDENT
