"""Organization management permission tests."""
from rest_framework.test import APIClient

from core.testing import TestCaseBase
from organizations.models import Organization


class OrganizationTests(TestCaseBase):
    def test_admin_can_create(self):
        client = APIClient()
        client.force_login(self.admin)
        response = client.post(
            "/api/organizations/",
            {"name": "New Tech Ltd", "industry": "Software", "address": "1 Test Road"},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 201)
        self.assertTrue(Organization.objects.filter(name="New Tech Ltd").exists())

    def test_students_cannot_create(self):
        client = APIClient()
        client.force_login(self.student)
        response = client.post(
            "/api/organizations/",
            {"name": "Sneaky Ltd", "industry": "Software"},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 403)
        self.assertFalse(Organization.objects.filter(name="Sneaky Ltd").exists())

    def test_duplicate_name_rejected(self):
        Organization.objects.create(name="Duplicate Ltd")
        client = APIClient()
        client.force_login(self.admin)
        response = client.post(
            "/api/organizations/", {"name": "duplicate ltd"}, content_type="application/json"
        )
        self.assertEqual(response.status_code, 400)

    def test_deactivate_keeps_record(self):
        organization = Organization.objects.create(name="Old Ltd")
        client = APIClient()
        client.force_login(self.admin)
        response = client.delete(f"/api/organizations/{organization.id}/")
        self.assertEqual(response.status_code, 204)
        organization.refresh_from_db()
        self.assertFalse(organization.is_active)
