"""Core model and dashboard permission tests."""
from datetime import date, timedelta

from rest_framework.test import APIClient

from core.models import Placement, SIWESSession
from core.testing import PASSWORD, TestCaseBase


class DashboardTests(TestCaseBase):
    def _place(self, student_profile, supervisor_profile):
        organization = _make_organization()
        session = SIWESSession.objects.create(
            name="Session A",
            start_date=date.today() - timedelta(days=30),
            end_date=date.today() + timedelta(days=60),
        )
        Placement.objects.create(
            student=student_profile,
            organization=organization,
            supervisor=supervisor_profile,
            siwes_session=session,
            is_active=True,
        )

    def test_admin_dashboard_contains_real_totals(self):
        self._place(self.student_profile, self.supervisor_profile)
        client = APIClient()
        client.force_login(self.admin)
        response = client.get("/api/core/dashboard/")
        self.assertEqual(response.status_code, 200)
        stats = response.json()["stats"]
        self.assertEqual(stats["total_students"], 2)
        self.assertEqual(stats["active_placements"], 1)

    def test_supervisor_only_sees_assigned_students(self):
        self._place(self.student_profile, self.supervisor_profile)
        client = APIClient()
        client.force_login(self.supervisor)
        response = client.get("/api/core/dashboard/")
        assigned = response.json()["assigned_students"]
        self.assertEqual(len(assigned), 1)
        self.assertEqual(assigned[0]["full_name"], "Test Student")

    def test_unassigned_supervisor_sees_no_students(self):
        self._place(self.student_profile, self.supervisor_profile)
        client = APIClient()
        client.force_login(self.other_supervisor)
        response = client.get("/api/core/dashboard/")
        self.assertEqual(response.json()["stats"]["assigned_students"], 0)

    def test_student_cannot_update_someone_else_profile(self):
        from rest_framework.test import APIClient

        client = APIClient()
        client.force_login(self.student_other)
        response = client.patch(
            f"/api/students/{self.student_profile.id}/",
            {"department": " hacked"},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 403)


def _make_organization():
    from organizations.models import Organization

    organization, _ = Organization.objects.get_or_create(name="TestOrg Ltd")
    return organization


class PlacementTests(TestCaseBase):
    def test_one_placement_per_student(self):
        session = SIWESSession.objects.create(
            name="Session B",
            start_date=date.today(),
            end_date=date.today() + timedelta(days=90),
        )
        organization = _make_organization()
        client = APIClient()
        client.force_login(self.admin)
        payload = {
            "student": self.student_profile.id,
            "organization": organization.id,
            "supervisor": self.supervisor_profile.id,
            "siwes_session": session.id,
        }
        first = client.post("/api/core/placements/", payload, content_type="application/json")
        self.assertEqual(first.status_code, 201)
        second = client.post("/api/core/placements/", payload, content_type="application/json")
        self.assertEqual(second.status_code, 400)

    def test_student_cannot_assign_placement(self):
        session = SIWESSession.objects.create(
            name="Session C",
            start_date=date.today(),
            end_date=date.today() + timedelta(days=90),
        )
        organization = _make_organization()
        client = APIClient()
        client.force_login(self.student_other)
        response = client.post(
            "/api/core/placements/",
            {
                "student": self.student_profile.id,
                "organization": organization.id,
                "supervisor": self.supervisor_profile.id,
                "siwes_session": session.id,
            },
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 403)

    def test_invalid_dates_rejected(self):
        client = APIClient()
        client.force_login(self.admin)
        response = client.post(
            "/api/core/sessions/",
            {
                "name": "Backwards session",
                "start_date": "2030-01-01",
                "end_date": "2029-01-01",
            },
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("end_date", response.json())
