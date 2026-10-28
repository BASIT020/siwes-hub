"""Organizations where students carry out their industrial training."""

from django.db import models


class Organization(models.Model):
    """A company/industry that hosts SIWES students."""

    name = models.CharField(max_length=150, unique=True)
    address = models.CharField(max_length=250, blank=True)
    contact_person = models.CharField(max_length=120, blank=True)
    contact_phone = models.CharField(max_length=20, blank=True)
    contact_email = models.EmailField(blank=True)
    industry = models.CharField(max_length=120, blank=True, help_text="e.g. Software development")
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]
        verbose_name_plural = "organizations"

    def __str__(self) -> str:
        return self.name
