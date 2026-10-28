from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from .models import User


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    """Admin site configuration for the SIWES Hub user model."""

    list_display = ("username", "full_name", "email", "role", "is_active")
    list_filter = ("role", "is_active")
    search_fields = ("username", "full_name", "email", "phone")
    fieldsets = BaseUserAdmin.fieldsets + (
        ("SIWES Hub details", {"fields": ("role", "full_name", "phone")}),
    )
    add_fieldsets = BaseUserAdmin.add_fieldsets + (
        ("SIWES Hub details", {"fields": ("role", "full_name", "phone")}),
    )
