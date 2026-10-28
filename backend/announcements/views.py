"""
Announcement API views.

* GET    /          - visible announcements for the caller (with read state)
* POST   /          - administrators publish (audience: all/students/supervisors)
* PATCH  /<id>/     - administrators edit
* DELETE /<id>/     - administrators deactivate
* POST   /<id>/read/ - caller marks the announcement as read
"""
from django.contrib.auth import get_user_model
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from core.pagination import paginate_response
from core.utils import audit
from notifications.utils import notify

from .models import Announcement
from .serializers import AnnouncementCreateSerializer, AnnouncementSerializer

User = get_user_model()


class AnnouncementListCreateView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        queryset = Announcement.visible_for(request.user)
        audience = request.query_params.get("audience")
        if audience and request.user.is_admin_role:
            queryset = Announcement.objects.all().filter(audience=audience)
        if request.query_params.get("include_inactive") == "true" and request.user.is_admin_role:
            queryset = Announcement.objects.all()
        search = request.query_params.get("search")
        if search:
            from django.db.models import Q

            queryset = queryset.filter(Q(title__icontains=search) | Q(content__icontains=search))
        return paginate_response(
            AnnouncementSerializer, request, queryset, context={"request": request}
        )

    def post(self, request):
        if not request.user.is_admin_role:
            return Response(
                {"detail": "Only administrators can publish announcements."},
                status=status.HTTP_403_FORBIDDEN,
            )
        serializer = AnnouncementCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        announcement = serializer.save(created_by=request.user)
        audit(
            request.user,
            "ANNOUNCEMENT PUBLISHED",
            f"Published announcement '{announcement.title}' to {announcement.audience}.",
        )
        # Create personal notifications for the target audience.
        recipients = User.objects.filter(is_active=True)
        if announcement.audience == Announcement.AUDIENCE_STUDENTS:
            recipients = recipients.filter(role=User.ROLE_STUDENT)
        elif announcement.audience == Announcement.AUDIENCE_SUPERVISORS:
            recipients = recipients.filter(role=User.ROLE_SUPERVISOR)
        else:
            recipients = recipients.exclude(role=User.ROLE_ADMIN)
        for recipient in recipients:
            notify(
                recipient=recipient,
                kind="announcement",
                title="New announcement",
                body=announcement.title,
                target_url="pages/announcements.html",
            )
        return Response(
            AnnouncementSerializer(announcement, context={"request": request}).data,
            status=status.HTTP_201_CREATED,
        )


class AnnouncementDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def _get(self, request, pk):
        try:
            announcement = Announcement.objects.get(pk=pk)
        except (Announcement.DoesNotExist, ValueError):
            return None
        visible = Announcement.visible_for(request.user)
        if announcement in visible:
            return announcement
        return None

    def get(self, request, pk):
        announcement = self._get(request, pk)
        if announcement is None:
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)
        return Response(AnnouncementSerializer(announcement, context={"request": request}).data)

    def patch(self, request, pk):
        if not request.user.is_admin_role:
            return Response({"detail": "Only administrators can edit announcements."}, status=status.HTTP_403_FORBIDDEN)
        try:
            announcement = Announcement.objects.get(pk=pk)
        except Announcement.DoesNotExist:
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)
        serializer = AnnouncementCreateSerializer(announcement, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        instance = serializer.save()
        audit(request.user, "ANNOUNCEMENT UPDATED", f"Updated announcement '{instance.title}'.")
        return Response(AnnouncementSerializer(instance, context={"request": request}).data)

    def delete(self, request, pk):
        if not request.user.is_admin_role:
            return Response({"detail": "Only administrators can delete announcements."}, status=status.HTTP_403_FORBIDDEN)
        try:
            announcement = Announcement.objects.get(pk=pk)
        except Announcement.DoesNotExist:
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)
        title = announcement.title
        announcement.delete()
        audit(request.user, "ANNOUNCEMENT DELETED", f"Deleted announcement '{title}'.")
        return Response(status=status.HTTP_204_NO_CONTENT)


class AnnouncementMarkReadView(APIView):
    """POST /api/announcements/<id>/read/ - mark one announcement as read."""

    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        announcement = self._get_detail(request, pk)
        if announcement is None:
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)
        announcement.read_by.add(request.user)
        return Response({"detail": "Marked as read."})

    @staticmethod
    def _get_detail(request, pk):
        try:
            return Announcement.visible_for(request.user).get(pk=pk)
        except (Announcement.DoesNotExist, ValueError):
            return None
