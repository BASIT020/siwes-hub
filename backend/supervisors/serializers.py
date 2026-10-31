"""Serializers for supervisor data."""
from rest_framework import serializers

from .models import SupervisorProfile


class SupervisorProfileSerializer(serializers.ModelSerializer):
    full_name = serializers.CharField(source="user.full_name", read_only=True)
    username = serializers.CharField(source="user.username", read_only=True)
    email = serializers.CharField(source="user.email", read_only=True)
    user_id = serializers.IntegerField(source="user.pk", read_only=True)
    user_is_active = serializers.BooleanField(source="user.is_active", read_only=True)
    is_pending = serializers.BooleanField(read_only=True)
    # Application status: pending / approved / rejected / inactive (property)
    status = serializers.CharField(read_only=True)
    assigned_students = serializers.SerializerMethodField()
    approved_by_name = serializers.CharField(source="approved_by.full_name", read_only=True)
    rejected_by_name = serializers.CharField(source="rejected_by.full_name", read_only=True)

    class Meta:
        model = SupervisorProfile
        fields = [
            "id",
            "user_id",
            "username",
            "full_name",
            "email",
            "user_is_active",
            "is_pending",
            "status",
            "staff_id",
            "title",
            "department",
            "is_active",
            "assigned_students",
            "created_at",
            "approved_by_name",
            "approved_at",
            "rejected_by_name",
            "rejected_at",
            "rejected_reason",
        ]
        read_only_fields = ["created_at", "status", "approved_at", "rejected_at", "rejected_reason"]

    def get_assigned_students(self, obj):
        if not obj.is_active:
            return 0
        return obj.placements.filter(is_active=True).count()

    def to_representation(self, obj):
        data = super().to_representation(obj)
        data["status"] = obj.status
        # Rejection paperwork (reason + who declined) stays in the
        # administrator approval queue only.
        request = self.context.get("request")
        is_admin = bool(
            request
            and getattr(request, "user", None)
            and request.user.is_authenticated
            and request.user.is_admin_role
        )
        if not is_admin:
            data.pop("rejected_reason", None)
            data.pop("rejected_by_name", None)
        return data
