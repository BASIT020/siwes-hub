"""Serializers for student data."""
from rest_framework import serializers

from .models import Skill, StudentProfile


class StudentProfileSerializer(serializers.ModelSerializer):
    """Full profile: administrators may write most fields."""

    full_name = serializers.CharField(source="user.full_name", read_only=True)
    username = serializers.CharField(source="user.username", read_only=True)
    email = serializers.CharField(source="user.email", read_only=True)
    phone = serializers.CharField(source="user.phone", read_only=False)
    user_id = serializers.IntegerField(source="user.pk", read_only=True)
    organization_name = serializers.SerializerMethodField()
    supervisor_name = serializers.SerializerMethodField()
    session_name = serializers.SerializerMethodField()

    class Meta:
        model = StudentProfile
        fields = [
            "id",
            "user_id",
            "username",
            "full_name",
            "matric_number",
            "department",
            "faculty",
            "level",
            "email",
            "phone",
            "training_start_date",
            "training_end_date",
            "is_active",
            "organization_name",
            "supervisor_name",
            "session_name",
            "created_at",
        ]
        read_only_fields = ["created_at", "user_id"]

    def get_organization_name(self, obj):
        placement = getattr(obj, "placement", None)
        if placement and placement.organization:
            return placement.organization.name
        return None

    def get_supervisor_name(self, obj):
        placement = getattr(obj, "placement", None)
        if placement and placement.supervisor:
            return str(placement.supervisor)
        return None

    def get_session_name(self, obj):
        placement = getattr(obj, "placement", None)
        if placement and placement.siwes_session:
            return placement.siwes_session.name
        return None

    def validate(self, attrs):
        start = attrs.get("training_start_date", getattr(self.instance, "training_start_date", None))
        end = attrs.get("training_end_date", getattr(self.instance, "training_end_date", None))
        if start and end and end < start:
            raise serializers.ValidationError(
                {"training_end_date": "Training end date cannot be earlier than start date."}
            )
        return attrs


class SelfUpdateStudentProfileSerializer(serializers.ModelSerializer):
    """
    What a student may change in their own profile: a limited, output-oriented
    read of the account fields plus the student-editable fields (department...).
    """

    full_name = serializers.CharField(source="user.full_name", read_only=True)
    matric_number = serializers.CharField(read_only=True)
    email = serializers.CharField(source="user.email", read_only=True)
    phone = serializers.CharField(source="user.phone", read_only=False, required=False)
    organization_name = serializers.SerializerMethodField()
    supervisor_name = serializers.SerializerMethodField()

    class Meta:
        model = StudentProfile
        fields = [
            "id",
            "full_name",
            "matric_number",
            "department",
            "faculty",
            "level",
            "email",
            "phone",
            "training_start_date",
            "training_end_date",
            "organization_name",
            "supervisor_name",
        ]
        read_only_fields = ["full_name", "matric_number", "email", "organization_name", "supervisor_name"]

    def get_organization_name(self, obj):
        placement = getattr(obj, "placement", None)
        return placement.organization.name if placement and placement.organization else None

    def get_supervisor_name(self, obj):
        placement = getattr(obj, "placement", None)
        return str(placement.supervisor) if placement and placement.supervisor else None

    def update(self, instance, validated_data):
        # `phone` writes through to the user account; the rest belongs to the
        # StudentProfile table.
        phone = validated_data.pop("user", {}).get("phone", None)
        if phone is not None:
            instance.user.phone = phone
            instance.user.save(update_fields=["phone"])
        return super().update(instance, validated_data)


class SkillSerializer(serializers.ModelSerializer):
    student_name = serializers.CharField(source="student.__str__", read_only=True)

    class Meta:
        model = Skill
        fields = [
            "id",
            "student",
            "student_name",
            "name",
            "description",
            "date_learned",
            "proficiency_level",
            "related_activity",
            "created_at",
        ]
        read_only_fields = ["created_at"]
