"""Django admin registration for the core application."""
from django.contrib import admin

from .models import AuditLog, Placement, SIWESSession


@admin.register(SIWESSession)
class SIWESSessionAdmin(admin.ModelAdmin):
    list_display = ("name", "start_date", "end_date", "is_active")
    list_filter = ("is_active",)
    search_fields = ("name",)


@admin.register(Placement)
class PlacementAdmin(admin.ModelAdmin):
    list_display = ("student", "organization", "supervisor", "siwes_session", "is_active")
    list_filter = ("is_active",)


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ("timestamp", "actor", "action", "detail")
    list_filter = ("action",)
    search_fields = ("detail",)
