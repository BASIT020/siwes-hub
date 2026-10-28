from django.contrib import admin

from .models import DailyLog


@admin.register(DailyLog)
class DailyLogAdmin(admin.ModelAdmin):
    list_display = ("student", "log_date", "status", "supervisor", "reviewed_at")
    list_filter = ("status",)
    search_fields = ("activities",)
