"""Project workflow tests."""
from datetime import date, timedelta

from rest_framework.test import APIClient

from core.testing import TestCaseBase
from projects.models import StudentProject


class ProjectTests(TestCaseBase):
    def setUp(self):
        self.student_client = APIClient()
        self.student_client.force_login(self.student)
        self.supervisor_client = APIClient()
        self.supervisor_client.force_login(self.supervisor)

    def _place_student(self):
        from organizations.models import Organization
        from core.models import Placement, SIWESSession

        organization, _ = Organization.objects.get_or_create(name="Project Org")
        session = SIWESSession.objects.create(
            name="Project Session",
            start_date=date.today(),
            end_date=date.today() + timedelta(days=90),
        )
        Placement.objects.create(
            student=self.student_profile,
            organization=organization,
            supervisor=self.supervisor_profile,
            siwes_session=session,
            is_active=True,
        )

    def test_student_creates_own_project(self):
        response = self.student_client.post(
            "/api/projects/me/",
            {"title": "Library Management CLI", "technologies": "Python, SQLite"},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()["review_status"], "not_submitted")

    def test_title_required(self):
        response = self.student_client.post(
            "/api/projects/me/", {"description": "no title"}, content_type="application/json"
        )
        self.assertEqual(response.status_code, 400)

    def test_admin_cannot_see_unassigned_others_project_detail_without_role(self):
        """Supervisors only see projects of students assigned to them."""
        self._place_student()
        self.student_client.post(
            "/api/projects/me/",
            {"title": "Assigned student's project"},
            content_type="application/json",
        )
        other_client = APIClient()
        other_client.force_login(self.other_supervisor)
        listing = other_client.get("/api/projects/")
        self.assertEqual(listing.status_code, 200)
        data = listing.json()
        results = data if isinstance(data, list) else data.get("results", [])
        self.assertEqual(len(results), 0)

    def test_submit_and_review_workflow(self):
        self._place_student()
        self.student_client.post(
            "/api/projects/me/",
            {"title": "Review Flow Project", "objectives": "Test workflow"},
            content_type="application/json",
        )
        submit = self.student_client.post("/api/projects/me/submit/")
        self.assertEqual(submit.json()["review_status"], StudentProject.REVIEW_SUBMITTED)

        me = self.student_client.get("/api/projects/me/")
        project_id = me.json()["id"]
        review = self.supervisor_client.post(
            f"/api/projects/{project_id}/review/",
            {"decision": "reject", "comment": "Needs database schema detail."},
            content_type="application/json",
        )
        self.assertEqual(review.json()["review_status"], StudentProject.REVIEW_REJECTED)

        # resubmission after rejection works
        resubmit = self.student_client.post("/api/projects/me/submit/")
        self.assertEqual(resubmit.json()["review_status"], StudentProject.REVIEW_SUBMITTED)
        self.supervisor_client.post(
            f"/api/projects/{project_id}/review/",
            {"decision": "approve", "comment": "Good."},
            content_type="application/json",
        )
        project = StudentProject.objects.get(pk=project_id)
        self.assertEqual(project.review_status, StudentProject.REVIEW_APPROVED)
        self.assertEqual(project.status, "completed")
