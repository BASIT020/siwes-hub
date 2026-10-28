from django.contrib import admin

from core.models import Placement  # noqa: F401 (Placement admin lives in core)

from .models import Organization


@admin.register(Organization)
class OrganizationAdmin(admin.ModelAdmin):
    list_display = ("name", "industry", "contact_person", "contact_phone", "is_active")
    search_fields = ("name", "industry")
