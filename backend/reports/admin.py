from django.contrib import admin

from .models import WeeklyReport


@admin.register(WeeklyReport)
class WeeklyReportAdmin(admin.ModelAdmin):
    list_display = ("student", "week_start", "week_end", "status", "supervisor", "reviewed_at")
    list_filter = ("status",)
