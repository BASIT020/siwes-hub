"""Serializers for weekly reports."""
from rest_framework import serializers

from .models import WeeklyReport


class WeeklyReportSerializer(serializers.ModelSerializer):
    student_name = serializers.CharField(source="student.__str__", read_only=True)
    matric_number = serializers.CharField(source="student.matric_number", read_only=True)
    supervisor_name = serializers.SerializerMethodField()
    week_end = serializers.DateField(required=False, allow_null=True)

    class Meta:
        model = WeeklyReport
        fields = [
            "id",
            "student",
            "student_name",
            "matric_number",
            "week_start",
            "week_end",
            "summary_of_activities",
            "challenges_faced",
            "lessons_learned",
            "skills_acquired",
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
        ]

    def get_supervisor_name(self, obj):
        return str(obj.supervisor) if obj.supervisor else None

    def validate_week_start(self, value):
        from django.utils import timezone

        if value > timezone.localdate():
            raise serializers.ValidationError("The reporting week cannot start in the future.")
        return value

    def validate(self, attrs):
        start = attrs.get("week_start", getattr(self.instance, "week_start", None))
        end = attrs.get("week_end", getattr(self.instance, "week_end", None))
        if start and end and end <= start:
            raise serializers.ValidationError(
                {"week_end": "Week end must be after the week start."}
            )
        return attrs


class ReportReviewSerializer(serializers.Serializer):
    decision = serializers.ChoiceField(choices=["approve", "reject"])
    comment = serializers.CharField(max_length=1000, required=False, allow_blank=True)
