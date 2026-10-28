"""
Organization views.

Everyone (authenticated) may read organization info; only administrators
create, update or deactivate organizations.
"""
import copy

from django.db.models import Q
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from core.pagination import paginate_response
from core.utils import audit

from .models import Organization
from .serializers import OrganizationSerializer


class OrganizationListCreateView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        queryset = Organization.objects.all()
        search = request.query_params.get("search")
        if search:
            queryset = queryset.filter(
                Q(name__icontains=search)
                | Q(industry__icontains=search)
                | Q(address__icontains=search)
            )
        is_active = request.query_params.get("is_active")
        if is_active in ("true", "false"):
            queryset = queryset.filter(is_active=(is_active == "true"))
        return paginate_response(OrganizationSerializer, request, queryset)

    def post(self, request):
        if not request.user.is_admin_role:
            return Response({"detail": "Only administrators can add organizations."}, status=status.HTTP_403_FORBIDDEN)
        name = (request.data.get("name") or "").strip()
        if not name:
            return Response({"name": "Organization name is required."}, status=status.HTTP_400_BAD_REQUEST)
        if Organization.objects.filter(name__iexact=name).exists():
            return Response({"name": "An organization with that name already exists."}, status=status.HTTP_400_BAD_REQUEST)
        serializer = OrganizationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        organization = serializer.save()
        audit(request.user, "ORGANIZATION ADDED", f"Added organization '{organization.name}'.")
        return Response(OrganizationSerializer(organization).data, status=status.HTTP_201_CREATED)


class OrganizationDetailView(APIView):
    """GET everyone, PATCH/DELETE (deactivate) administrators only."""

    def _get(self, request, pk):
        try:
            return Organization.objects.get(pk=pk)
        except (Organization.DoesNotExist, ValueError):
            return None

    def get(self, request, pk):
        organization = self._get(request, pk)
        if organization is None:
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)
        return Response(OrganizationSerializer(organization).data)

    def patch(self, request, pk):
        if not request.user.is_admin_role:
            return Response({"detail": "Only administrators can edit organizations."}, status=status.HTTP_403_FORBIDDEN)
        organization = self._get(request, pk)
        if organization is None:
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)
        serializer = OrganizationSerializer(organization, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        instance = serializer.save()
        audit(request.user, "ORGANIZATION UPDATED", f"Updated organization '{instance.name}'.")
        return Response(OrganizationSerializer(instance).data)

    def delete(self, request, pk):
        """Deactivate (PROTECT keeps past placements intact)."""
        if not request.user.is_admin_role:
            return Response({"detail": "Only administrators can do this."}, status=status.HTTP_403_FORBIDDEN)
        organization = self._get(request, pk)
        if organization is None:
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)
        organization.is_active = False
        organization.save(update_fields=["is_active"])
        audit(request.user, "ORGANIZATION DEACTIVATED", f"Deactivated organization '{organization.name}'.")
        return Response(status=status.HTTP_204_NO_CONTENT)
