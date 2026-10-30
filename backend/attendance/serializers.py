from django.utils import timezone
from rest_framework import serializers

from .models import Attendance


class AttendanceSerializer(serializers.ModelSerializer):
    student_name = serializers.CharField(source="student.__str__", read_only=True)
    matric_number = serializers.CharField(source="student.matric_number", read_only=True)
    recorded_by_name = serializers.CharField(source="recorded_by.username", read_only=True)
    verified_by_name = serializers.SerializerMethodField()

    class Meta:
        model = Attendance
        fields = [
            "id",
            "student",
            "student_name",
            "matric_number",
            "date",
            "status",
            "note",
            "recorded_by",
            "recorded_by_name",
            "verified_by",
            "verified_by_name",
            "verified_at",
            "created_at",
        ]
        # student/date are fixed at creation: PATCH may correct status/note but
        # never re-point (or backdate) a record onto another student/day.
        read_only_fields = ["student", "date", "recorded_by", "verified_by", "verified_at"]

    def get_verified_by_name(self, obj):
        return str(obj.verified_by) if obj.verified_by else None

    def validate_date(self, value):
        today = timezone.localdate()
        if value > today:
            raise serializers.ValidationError("Attendance cannot be recorded for a future date.")
        return value
