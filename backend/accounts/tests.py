"""Authentication and role-based-access tests (spec section 19)."""
from django.contrib.auth import get_user_model
from django.test import Client

from core.testing import PASSWORD, TestCaseBase

User = get_user_model()


class AuthenticationTests(TestCaseBase):
    def test_valid_login_redirects_to_role_data(self):
        client = Client()
        response = self.logged_client(self.student).get("/api/auth/me/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["role"], "student")

    def test_invalid_login_rejected(self):
        client = Client()
        response = client.post(
            "/api/auth/login/",
            {"username": "student1", "password": "wrongpassword"},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 401)

    def test_inactive_account_cannot_login(self):
        self.student.is_active = False
        self.student.save()
        client = Client()
        response = client.post(
            "/api/auth/login/",
            {"username": "student1", "password": PASSWORD},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 403)
        self.assertIn("deactivated", response.json()["detail"].lower())

    def test_anonymous_access_is_rejected(self):
        client = Client()
        for url in [
            "/api/core/dashboard/",
            "/api/logs/",
            "/api/reports/",
            "/api/students/",
            "/api/attendance/summary/",
            "/api/users/",
        ]:
            response = client.get(url)
            self.assertIn(response.status_code, (401, 403), f"{url} gave {response.status_code}")

    def test_student_cannot_access_admin_endpoints(self):
        client = self.logged_client(self.student)
        response = client.get("/api/users/")
        self.assertEqual(response.status_code, 403)

    def test_supervisor_cannot_access_admin_endpoints(self):
        client = self.logged_client(self.supervisor)
        response = client.get("/api/users/")
        self.assertEqual(response.status_code, 403)

    def test_student_cannot_escalate_to_admin_via_api(self):
        client = self.logged_client(self.student)
        response = client.post(
            "/api/users/",
            {
                "username": "evil_admin",
                "role": "admin",
                "password": "VeryStrong#1",
            },
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 403)
        self.assertFalse(User.objects.filter(username="evil_admin").exists())

    def test_logout_ends_session(self):
        client = self.logged_client(self.student)
        client.post("/api/auth/logout/")
        response = client.get("/api/auth/me/")
        self.assertEqual(response.status_code, 403)

    def test_password_hashing_is_not_plaintext(self):
        self.student.refresh_from_db()
        self.assertNotEqual(self.student.password, PASSWORD)
        self.assertTrue(self.student.password.startswith("pbkdf2_"))


STUDENT_PAYLOAD = {
    "full_name": "Ada Obi",
    "email": "ada.obi@register.test",
    "matric_number": "2377991001",
    "password": "Reg#Pass123",
    "password2": "Reg#Pass123",
}


def _clear_rate_limiters():
    """Reset the in-memory throttle state between tests (fresh module state)."""
    from accounts import views as accounts_views

    accounts_views._registration_hits.clear()
    accounts_views._failed_logins.clear()


class StudentRegistrationTests(TestCaseBase):
    """Public self-registration -> real DB user + profile, signed in at once."""

    def setUp(self):
        super().setUp()
        _clear_rate_limiters()

    def test_registration_creates_user_profile_and_session(self):
        from students.models import StudentProfile

        client = Client()
        response = client.post(
            "/api/auth/register/student/",
            STUDENT_PAYLOAD,
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 201, response.json())
        self.assertEqual(response.json()["role"], "student")

        user = User.objects.get(username=STUDENT_PAYLOAD["matric_number"])
        self.assertEqual(user.role, "student")
        self.assertTrue(user.is_active)
        self.assertTrue(user.check_password(STUDENT_PAYLOAD["password"]))
        self.assertNotEqual(user.password, STUDENT_PAYLOAD["password"])
        self.assertTrue(StudentProfile.objects.filter(
            user=user, matric_number=STUDENT_PAYLOAD["matric_number"]
        ).exists())

        # The registration already started a session (no new login needed).
        me = client.get("/api/auth/me/")
        self.assertEqual(me.status_code, 200)
        self.assertEqual(me.json()["username"], user.username)

        # An audit trail row exists for the self-registration.
        from core.models import AuditLog

        self.assertTrue(AuditLog.objects.filter(
            actor=user, action="STUDENT REGISTRATION").exists())

    def test_duplicate_email_is_rejected_case_insensitively(self):
        client = Client()
        first = client.post(
            "/api/auth/register/student/", STUDENT_PAYLOAD, content_type="application/json")
        self.assertEqual(first.status_code, 201)

        again = dict(STUDENT_PAYLOAD, matric_number="2377991002")
        again["email"] = STUDENT_PAYLOAD["email"].upper()
        response = client.post(
            "/api/auth/register/student/", again, content_type="application/json")
        self.assertEqual(response.status_code, 400)
        self.assertIn("email", response.json())

    def test_duplicate_matric_number_is_rejected(self):
        client = Client()
        payload = dict(STUDENT_PAYLOAD, matric_number="2305999001")  # fixture matric
        response = client.post(
            "/api/auth/register/student/", payload, content_type="application/json")
        self.assertEqual(response.status_code, 400)
        self.assertIn("matric_number", response.json())

    def test_matric_matching_existing_signin_username_is_rejected(self):
        client = Client()
        payload = dict(STUDENT_PAYLOAD, matric_number="student1")  # fixture username
        response = client.post(
            "/api/auth/register/student/", payload, content_type="application/json")
        self.assertEqual(response.status_code, 400)

    def test_invalid_submissions_are_rejected(self):
        client = Client()
        cases = [
            ("password mismatch", {**STUDENT_PAYLOAD, "password2": "Different#9"}),
            ("short password", {**STUDENT_PAYLOAD, "password": "abc", "password2": "abc"}),
            ("numeric-only password", {**STUDENT_PAYLOAD, "password": "123456", "password2": "123456"}),
            ("digits in full name", {**STUDENT_PAYLOAD, "full_name": "Ada 09"}),
            ("blank full name", {**STUDENT_PAYLOAD, "full_name": "   "}),
            ("missing matric", {k: v for k, v in STUDENT_PAYLOAD.items() if k != "matric_number"}),
            ("bad email", {**STUDENT_PAYLOAD, "email": "not-an-email"}),
        ]
        for label, payload in cases:
            response = client.post(
                "/api/auth/register/student/", payload, content_type="application/json")
            self.assertEqual(response.status_code, 400, f"{label} -> {response.json()}")

        # None of the failures created any user.
        self.assertFalse(User.objects.filter(email=STUDENT_PAYLOAD["email"]).exists())

    def test_public_registration_cannot_create_staff_or_admin_role(self):
        client = Client()
        payload = {
            **STUDENT_PAYLOAD,
            "role": "admin",
            "is_staff": True,
            "is_superuser": True,
        }
        response = client.post(
            "/api/auth/register/student/", payload, content_type="application/json")
        self.assertEqual(response.status_code, 201, response.json())
        user = User.objects.get(username=STUDENT_PAYLOAD["matric_number"])
        self.assertEqual(user.role, "student")
        self.assertFalse(user.is_staff)
        self.assertFalse(user.is_superuser)


SUPERVISOR_PAYLOAD = {
    "username": "m.bello",
    "full_name": "Musa Bello",
    "email": "musa.bello@register.test",
    "title": "Dr.",
    "department": "Chemical Engineering",
    "password": "Reg#Pass123",
    "password2": "Reg#Pass123",
}


class SupervisorRegistrationTests(TestCaseBase):
    """Public supervisor registration -> pending account needing approval."""

    def setUp(self):
        super().setUp()
        _clear_rate_limiters()

    def register(self, client, **overrides):
        from supervisors.models import SupervisorProfile

        payload = {**SUPERVISOR_PAYLOAD, **overrides}
        response = client.post(
            "/api/auth/register/supervisor/",
            payload,
            content_type="application/json",
        )
        profile = SupervisorProfile.objects.filter(user__username=payload["username"]).first()
        return response, profile

    def test_registration_creates_pending_account(self):
        client = Client()
        response, profile = self.register(client)
        self.assertEqual(response.status_code, 201, response.json())
        self.assertEqual(response.json()["status"], "pending_approval")

        user = profile.user
        self.assertEqual(user.role, "supervisor")
        self.assertFalse(user.is_active)
        self.assertTrue(user.check_password(SUPERVISOR_PAYLOAD["password"]))
        self.assertTrue(profile.is_pending)
        self.assertFalse(profile.is_active)
        self.assertEqual(profile.title, "Dr.")

    def test_pending_supervisor_cannot_sign_in_yet(self):
        client = Client()
        response, _ = self.register(client)
        self.assertEqual(response.status_code, 201)
        # No session was started by the registration.
        self.assertIn(client.get("/api/auth/me/").status_code, (401, 403))

        login = client.post(
            "/api/auth/login/",
            {"username": SUPERVISOR_PAYLOAD["username"], "password": SUPERVISOR_PAYLOAD["password"]},
            content_type="application/json",
        )
        self.assertEqual(login.status_code, 403)
        self.assertIn("approval", login.json()["detail"].lower())

    def test_administrators_are_notified_of_pending_registration(self):
        from notifications.models import Notification

        client = Client()
        self.register(client)
        self.assertTrue(Notification.objects.filter(
            recipient=self.admin, kind="account",
            title__icontains="approval").exists())

    def test_duplicate_username_is_rejected(self):
        client = Client()
        response, profile = self.register(client)
        self.assertEqual(response.status_code, 201)

        from supervisors.models import SupervisorProfile

        again, _ = self.register(client, username=SUPERVISOR_PAYLOAD["username"].upper())
        self.assertEqual(again.status_code, 400)
        self.assertIn("username", again.json())
        self.assertFalse(SupervisorProfile.objects.filter(user__username__iexact="m.bello").exclude(
            pk=profile.pk).exists())  # no third account was created
        profile.refresh_from_db()  # first account unchanged

    def test_invalid_submissions_are_rejected(self):
        client = Client()
        cases = [
            ("short username", {**SUPERVISOR_PAYLOAD, "username": "ab"}),
            ("missing email", {k: v for k, v in SUPERVISOR_PAYLOAD.items() if k != "email"}),
            ("mismatched passwords", {**SUPERVISOR_PAYLOAD, "password2": "Different#9"}),
        ]
        for label, payload in cases:
            response = client.post(
                "/api/auth/register/supervisor/", payload, content_type="application/json")
            self.assertEqual(response.status_code, 400, f"{label} -> {response.json()}")


class SupervisorApprovalTests(TestCaseBase):
    """Administrator approves via PATCH /api/supervisors/<id>/ {is_active: true}."""

    def setUp(self):
        super().setUp()
        _clear_rate_limiters()
        self.client = Client()
        self.registration = self.client.post(
            "/api/auth/register/supervisor/",
            SUPERVISOR_PAYLOAD,
            content_type="application/json",
        )
        self.assertEqual(self.registration.status_code, 201, self.registration.json())
        from supervisors.models import SupervisorProfile

        self.profile = SupervisorProfile.objects.get(user__username=SUPERVISOR_PAYLOAD["username"])
        self.user = self.profile.user

    def test_admin_approval_activates_the_user_account(self):
        admin_client = self.logged_client(self.admin)
        response = admin_client.patch(
            f"/api/supervisors/{self.profile.id}/",
            {"is_active": True},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200, response.json())
        self.user.refresh_from_db()
        self.profile.refresh_from_db()
        self.assertTrue(self.user.is_active)
        self.assertFalse(self.profile.is_pending)

        # The approved supervisor can now sign in.
        login = self.client.post(
            "/api/auth/login/",
            {"username": SUPERVISOR_PAYLOAD["username"], "password": SUPERVISOR_PAYLOAD["password"]},
            content_type="application/json",
        )
        self.assertEqual(login.status_code, 200)

        # Notification + audit trail entries exist.
        from core.models import AuditLog
        from notifications.models import Notification

        self.assertTrue(AuditLog.objects.filter(action="SUPERVISOR APPROVED").exists())
        self.assertTrue(Notification.objects.filter(
            recipient=self.user, title__icontains="approved").exists())

    def test_non_admin_cannot_approve(self):
        for actor in (self.student, self.supervisor):
            actor_client = self.logged_client(actor)
            response = actor_client.patch(
                f"/api/supervisors/{self.profile.id}/",
                {"is_active": True},
                content_type="application/json",
            )
            self.assertEqual(response.status_code, 403)
            self.user.refresh_from_db()
            self.assertFalse(self.user.is_active)

    def test_reactivating_uses_the_same_endpoint(self):
        # A deactivated (non-pending) supervisor is re-activated the same way.
        self.profile.is_pending = False
        self.profile.save()
        admin_client = self.logged_client(self.admin)
        response = admin_client.patch(
            f"/api/supervisors/{self.profile.id}/",
            {"is_active": True},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        self.user.refresh_from_db()
        self.assertTrue(self.user.is_active)

    def test_admin_can_reject_a_pending_registration(self):
        admin_client = self.logged_client(self.admin)
        response = admin_client.patch(
            f"/api/supervisors/{self.profile.id}/",
            {"is_active": False},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200, response.json())
        self.user.refresh_from_db()
        self.profile.refresh_from_db()
        self.assertFalse(self.user.is_active)
        self.assertFalse(self.profile.is_pending)
        self.assertFalse(self.profile.is_active)

        # A rejected account can never sign in.
        login = self.client.post(
            "/api/auth/login/",
            {"username": SUPERVISOR_PAYLOAD["username"], "password": SUPERVISOR_PAYLOAD["password"]},
            content_type="application/json",
        )
        self.assertEqual(login.status_code, 403)

        # Audit trail + notification for the applicant exist.
        from core.models import AuditLog
        from notifications.models import Notification

        self.assertTrue(AuditLog.objects.filter(action="SUPERVISOR REJECTED").exists())
        self.assertTrue(Notification.objects.filter(
            recipient=self.user, title__icontains="declined").exists())

    def test_deactivating_a_working_supervisor_is_not_a_rejection(self):
        # The fixture supervisor is an active admin-registered account.
        admin_client = self.logged_client(self.admin)
        response = admin_client.patch(
            f"/api/supervisors/{self.supervisor_profile.id}/",
            {"is_active": False},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        from core.models import AuditLog

        self.assertTrue(AuditLog.objects.filter(action="SUPERVISOR DEACTIVATED").exists())
        self.assertFalse(AuditLog.objects.filter(action="SUPERVISOR REJECTED").exists())

    def test_pending_filter_lists_only_pending_registrations(self):
        admin_client = self.logged_client(self.admin)
        response = admin_client.get("/api/supervisors/?pending=true&page=1&page_size=50")
        self.assertEqual(response.status_code, 200)
        usernames = {row["username"] for row in response.json()["results"]}
        self.assertIn(SUPERVISOR_PAYLOAD["username"], usernames)
        self.assertNotIn("supervisor1", usernames)  # fixture supervisor is active

    def test_non_admin_cannot_use_pending_filter(self):
        for actor in (self.student, self.supervisor):
            actor_client = self.logged_client(actor)
            response = actor_client.get("/api/supervisors/?pending=true&page_size=50")
            self.assertEqual(response.status_code, 403)
