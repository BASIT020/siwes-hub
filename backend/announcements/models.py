"""Announcement model - messages published by administrators."""

from django.conf import settings
from django.db import models


class Announcement(models.Model):
    AUDIENCE_ALL = "all"
    AUDIENCE_STUDENTS = "students"
    AUDIENCE_SUPERVISORS = "supervisors"
    AUDIENCES = [
        (AUDIENCE_ALL, "All users"),
        (AUDIENCE_STUDENTS, "Students"),
        (AUDIENCE_SUPERVISORS, "Supervisors"),
    ]

    title = models.CharField(max_length=200)
    content = models.TextField()
    audience = models.CharField(max_length=20, choices=AUDIENCES, default=AUDIENCE_ALL)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="announcements_created",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_active = models.BooleanField(default=True)
    read_by = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        blank=True,
        related_name="announcements_read",
    )

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["audience", "is_active"]),
        ]

    def __str__(self) -> str:
        return self.title

    @classmethod
    def visible_for(cls, user):
        """Announcements the given user is allowed to see."""
        qs = cls.objects.filter(is_active=True)
        if user.is_admin_role:
            return qs
        if not user.is_authenticated:
            return cls.objects.none()
        audience = {
            user.ROLE_STUDENT: cls.AUDIENCE_STUDENTS,
            user.ROLE_SUPERVISOR: cls.AUDIENCE_SUPERVISORS,
            user.ROLE_ADMIN: cls.AUDIENCE_ALL,
        }.get(user.role)
        allowed = [cls.AUDIENCE_ALL]
        if audience:
            allowed.append(audience)
        return qs.filter(audience__in=allowed)
