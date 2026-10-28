from rest_framework import serializers

from .models import Announcement


class AnnouncementSerializer(serializers.ModelSerializer):
    created_by_name = serializers.CharField(source="created_by.username", read_only=True, default=None)
    read_by_me = serializers.SerializerMethodField()

    class Meta:
        model = Announcement
        fields = [
            "id",
            "title",
            "content",
            "audience",
            "created_by",
            "created_by_name",
            "created_at",
            "updated_at",
            "is_active",
            "read_by_me",
        ]
        read_only_fields = ["created_by", "created_by_name", "created_at", "read_by_me"]

    def get_read_by_me(self, obj):
        request = self.context.get("request")
        user = getattr(request, "user", None)
        return bool(user and user.is_authenticated and obj.read_by.filter(pk=user.pk).exists())


class AnnouncementCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Announcement
        fields = ["title", "content", "audience", "is_active"]

    def validate_content(self, value):
        if not (value or "").strip():
            raise serializers.ValidationError("Announcement content is required.")
        return value

    def validate_audience(self, value):
        if value not in dict(Announcement.AUDIENCES):
            raise serializers.ValidationError("Invalid audience.")
        return value
