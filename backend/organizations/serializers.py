"""Serializers for organizations."""
from rest_framework import serializers

from .models import Organization


class OrganizationSerializer(serializers.ModelSerializer):
    placed_students = serializers.SerializerMethodField()

    class Meta:
        model = Organization
        fields = [
            "id",
            "name",
            "address",
            "contact_person",
            "contact_phone",
            "contact_email",
            "industry",
            "is_active",
            "placed_students",
            "created_at",
        ]
        read_only_fields = ["created_at", "placed_students"]

    def get_placed_students(self, obj):
        return obj.placements.filter(is_active=True).count()
