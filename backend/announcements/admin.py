from django.contrib import admin

from .models import Announcement


@admin.register(Announcement)
class AnnouncementAdmin(admin.ModelAdmin):
    list_display = ("title", "audience", "created_by", "created_at", "is_active")
    list_filter = ("audience", "is_active")
