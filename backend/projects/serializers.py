from rest_framework import serializers

from .models import StudentProject


class StudentProjectSerializer(serializers.ModelSerializer):
    student_name = serializers.CharField(source="student.__str__", read_only=True)
    matric_number = serializers.CharField(source="student.matric_number", read_only=True)
    supervisor_name = serializers.SerializerMethodField()

    class Meta:
        model = StudentProject
        fields = [
            "id",
            "student",
            "student_name",
            "matric_number",
            "title",
            "description",
            "objectives",
            "technologies",
            "status",
            "review_status",
            "submitted_at",
            "reviewed_at",
            "supervisor",
            "supervisor_name",
            "supervisor_comment",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["student", "review_status", "submitted_at", "reviewed_at", "supervisor", "supervisor_name", "supervisor_comment"]

    def get_supervisor_name(self, obj):
        return str(obj.supervisor) if obj.supervisor else None

    def validate_title(self, value):
        if not (value or "").strip():
            raise serializers.ValidationError("A project title is required.")
        return value


class ProjectReviewSerializer(serializers.Serializer):
    decision = serializers.ChoiceField(choices=["approve", "reject"])
    comment = serializers.CharField(max_length=1000, required=False, allow_blank=True)
