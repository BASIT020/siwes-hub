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
    assigned_students = serializers.SerializerMethodField()

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
            "staff_id",
            "title",
            "department",
            "is_active",
            "assigned_students",
            "created_at",
        ]
        read_only_fields = ["created_at"]

    def get_assigned_students(self, obj):
        if not obj.is_active:
            return 0
        return obj.placements.filter(is_active=True).count()
