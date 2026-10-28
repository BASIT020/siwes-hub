"""Serializers for daily logs."""
from rest_framework import serializers

from .models import DailyLog


class DailyLogSerializer(serializers.ModelSerializer):
    student_name = serializers.CharField(source="student.__str__", read_only=True)
    matric_number = serializers.CharField(source="student.matric_number", read_only=True)
    supervisor_name = serializers.SerializerMethodField()

    class Meta:
        model = DailyLog
        fields = [
            "id",
            "student",
            "student_name",
            "matric_number",
            "log_date",
            "activities",
            "tools_used",
            "skills_learned",
            "hours_spent",
            "remarks",
            "status",
            "submitted_at",
            "supervisor",
            "supervisor_name",
            "supervisor_comment",
            "reviewed_at",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "student",
            "status",
            "submitted_at",
            "supervisor",
            "supervisor_name",
            "supervisor_comment",
            "reviewed_at",
            "createdAt",
        ]

    def get_supervisor_name(self, obj):
        return str(obj.supervisor) if obj.supervisor else None

    def validate_log_date(self, value):
        from django.utils import timezone

        if value > timezone.localdate():
            raise serializers.ValidationError("The log date cannot be in the future.")
        return value

    def validate_activities(self, value):
        if not (value or "").strip():
            raise serializers.ValidationError("Please describe the activities performed.")
        return value


class LogReviewSerializer(serializers.Serializer):
    """Input for the review endpoint."""

    decision = serializers.ChoiceField(choices=["approve", "reject"])
    comment = serializers.CharField(max_length=1000, required=False, allow_blank=True)
