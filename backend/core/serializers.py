"""Serializers for core models (sessions, placements, audit)."""
from rest_framework import serializers

from .models import AuditLog, Placement, SIWESSession


class SIWESSessionSerializer(serializers.ModelSerializer):
    placements_count = serializers.SerializerMethodField()

    class Meta:
        model = SIWESSession
        fields = [
            "id", "name", "start_date", "end_date", "description",
            "is_active", "placements_count", "created_at",
        ]
        read_only_fields = ["created_at"]

    def get_placements_count(self, obj):
        return obj.placements.count()

    def validate(self, attrs):
        start = attrs.get("start_date", getattr(self.instance, "start_date", None))
        end = attrs.get("end_date", getattr(self.instance, "end_date", None))
        if start and end and end < start:
            raise serializers.ValidationError(
                {"end_date": "End date cannot be earlier than the start date."}
            )
        return attrs


class PlacementSerializer(serializers.ModelSerializer):
    """Read representation of a placement with the related names resolved."""

    student_name = serializers.CharField(source="student.__str__", read_only=True)
    matric_number = serializers.CharField(
        source="student.matric_number", read_only=True
    )
    organization_name = serializers.CharField(
        source="organization.name", read_only=True, default=None
    )
    supervisor_name = serializers.CharField(
        source="supervisor.__str__", read_only=True, default=None
    )
    session_name = serializers.CharField(
        source="siwes_session.name", read_only=True, default=None
    )

    class Meta:
        model = Placement
        fields = [
            "id",
            "student",
            "student_name",
            "matric_number",
            "organization",
            "organization_name",
            "supervisor",
            "supervisor_name",
            "siwes_session",
            "session_name",
            "start_date",
            "end_date",
            "is_active",
            "remarks",
        ]

    def validate(self, attrs):
        start = attrs.get("start_date", getattr(self.instance, "start_date", None))
        end = attrs.get("end_date", getattr(self.instance, "end_date", None))
        if start and end and end < start:
            raise serializers.ValidationError(
                {"end_date": "Placement end date cannot be earlier than start date."}
            )
        return attrs


class AuditLogSerializer(serializers.ModelSerializer):
    actor_name = serializers.CharField(source="actor.username", read_only=True, default=None)

    class Meta:
        model = AuditLog
        fields = ["id", "timestamp", "actor", "actor_name", "action", "detail"]
