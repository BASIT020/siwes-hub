"""
Idempotent demonstration data seeder for SIWES Hub.

IMPORTANT: this command is a MANUAL tool for lecturers/examiners who want a
populated example database. It is NEVER called by START_APP.bat or by the
portable launcher, and it never resets existing user passwords unless
--refresh-passwords is given explicitly.

Running `python manage.py seed_demo`:

* Creates the three role types of demonstration accounts (1 administrator,
  2 supervisors, 6 students) plus organizations, a SIWES session, placements,
  daily logs in every status, weekly reports, attendance, skills, projects,
  announcements and notifications.

* Is safe to run repeatedly: every record is created with get_or_create on a
  natural key, so a second run adds nothing and never duplicates rows.

* Writes the generated demonstration passwords ONCE into
  database/demo_credentials.txt (labelled clearly as demonstration-only).
  Passwords are never printed to the terminal or logs.

Usage:
    python manage.py seed_demo                       # random demo passwords
    python manage.py seed_demo --password "X"        # fixed password (dev/testing)
    python manage.py seed_demo --only-accounts       # skip the sample records
"""
import secrets
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from accounts.models import User
from announcements.models import Announcement
from attendance.models import Attendance
from core.models import Placement, SIWESSession
from logs.models import DailyLog
from organizations.models import Organization
from notifications.utils import notify
from projects.models import StudentProject
from reports.models import WeeklyReport
from students.models import Skill, StudentProfile
from supervisors.models import SupervisorProfile

CREDENTIALS_FILE_NAME = "demo_credentials.txt"


def monday_of_weeks_ago(weeks):
    """A Monday `weeks` weeks in the past."""
    today = timezone.localdate()
    weekday = today.weekday()
    monday = today - timedelta(days=weekday)
    return monday - timedelta(weeks=weeks)


def past_weekday(days_ago):
    """A date `days_ago` days in the past (used for logs/attendance)."""
    return timezone.localdate() - timedelta(days=days_ago)


class Command(BaseCommand):
    help = "Create (or refresh without duplicating) the SIWES Hub demonstration data."

    def add_arguments(self, parser):
        parser.add_argument("--password", default=None, help="Fixed demonstration password (dev/testing only).")
        parser.add_argument("--only-accounts", action="store_true", help="Create accounts only, skip records.")
        parser.add_argument(
            "--refresh-passwords",
            action="store_true",
            help="Reset every demonstration account's password to the shared password "
                 "and rewrite database/demo_credentials.txt completely "
                 "(use when the file was lost or accounts were seeded earlier).",
        )

    # ================================================================== #
    def handle(self, *args, **options):
        fixed_password = options["password"]
        self._fixed_password = fixed_password
        only_accounts = options["only_accounts"]

        generated = {}
        refresh = options["refresh_passwords"]
        with transaction.atomic():
            admin = self._create_admin(fixed_password, generated)
            supervisors = self._create_supervisors(fixed_password, generated)
            students = self._create_students(fixed_password, generated)
            if refresh:
                # Re-set the shared password on every demonstration account and
                # rewrite the credentials file listing all of them.
                self._refresh_all_passwords([admin] + list(supervisors) + list(students))
                generated = self._collect_all([admin] + list(supervisors) + list(students))
            self._write_credentials(generated)
            if not only_accounts:
                organizations = self._create_organizations()
                session = self._create_session()
                self._create_placements(students, supervisors, organizations, session)
                self._create_logs(students, supervisors)
                self._create_reports(students, supervisors)
                self._create_attendance(students, supervisors)
                self._create_skills(students)
                self._create_projects(students, supervisors)
                self._create_announcements(admin)
        self.stdout.write(self.style.SUCCESS("Demonstration data is ready."))
        from core.management.commands._paths import credentials_path

        self.stdout.write(f"Demonstration credentials file: {credentials_path()}")
        self.stdout.write(
            "Accounts: admin_siwes (administrator), chioma.eze / tunde.olajide"
            " (supervisors), student1..student6 (students)."
        )

    # ------------------------------------------------------------------ #
    # Accounts
    # ------------------------------------------------------------------ #
    def _account_password(self, fixed_password):
        if fixed_password:
            return fixed_password
        # One shared random password for this seeding run.
        if not hasattr(self, "_shared_password"):
            self._shared_password = secrets.token_urlsafe(12)
        return self._shared_password

    def _make_user(self, username, full_name, email, role, fixed_password, generated):
        user, created = User.objects.get_or_create(
            username=username,
            defaults={
                "role": role,
                "full_name": full_name,
                "email": email,
                "is_active": True,
            },
        )
        if created:
            password = self._account_password(fixed_password)
            user.set_password(password)
            user.save(update_fields=["password"])
            generated.setdefault(role + "s", []).append((username, full_name))
        return user

    def _create_admin(self, fixed_password, generated):
        admin = self._make_user(
            "admin_siwes",
            "Mrs. Bola Adeyemi",
            "admin.siwes@siweshub-demo.edu",
            User.ROLE_ADMIN,
            fixed_password,
            generated,
        )
        return admin

    def _create_supervisors(self, fixed_password, generated):
        profiles = []
        for username, name, title, department, staff_id in [
            ("chioma.eze", "Dr. Chioma Eze", "Dr.", "Computer Science", "CS/1021"),
            ("tunde.olajide", "Mr. Tunde Olajide", "Mr.", "Software Engineering", "SE/0874"),
        ]:
            user = self._make_user(username, name, f"{username}@siweshub-demo.edu", User.ROLE_SUPERVISOR, fixed_password, generated)
            profile, created = SupervisorProfile.objects.get_or_create(
                user=user,
                defaults={"title": title, "department": department, "staff_id": staff_id},
            )
            role_attr = "supervisors"
            generated.setdefault(role_attr, [])
            if created:
                generated[role_attr].append((username, name))
            profiles.append(profile)
        return profiles

    def _create_students(self, fixed_password, generated):
        students = []
        demo_students = [
            # username, full_name, matric, department, faculty, level
            ("student1", "Adeola Bakare", "230591056", "Computer Science", "Science", "ND2"),
            ("student2", "Blessing Okon", "230591102", "Computer Science", "Science", "ND2"),
            ("student3", "Chidi Nwosu", "230590914", "Software Engineering", "Science", "ND1"),
            ("student4", "Fatima Bello", "230591298", "Computer Engineering", "Engineering", "HND1"),
            ("student5", "Emeka Uche", "230591033", "Computer Science", "Science", "ND2"),
            ("student6", "Grace DANIELS", "230591201", "Information Technology", "Science", "ND1"),
        ]
        for username, full_name, matric, dept, faculty, level in demo_students:
            user = self._make_user(username, full_name.title(), f"{username}@siweshub-demo.edu", User.ROLE_STUDENT, fixed_password, generated)
            profile, created = StudentProfile.objects.get_or_create(
                user=user,
                defaults={
                    "matric_number": matric,
                    "department": dept,
                    "faculty": faculty,
                    "level": level,
                    "training_start_date": monday_of_weeks_ago(5),
                },
            )
            students.append(profile)
        return students

    def _user_of(self, obj):
        """Supervisor/Student helpers return profiles; map them to their User."""
        return obj if isinstance(obj, User) else getattr(obj, "user", obj)

    def _refresh_all_passwords(self, users):
        """Force-reset the shared password for every demonstration account."""
        password = self._account_password(self._fixed_password)
        for obj in users:
            user = self._user_of(obj)
            if not user:
                continue
            user.set_password(password)
            user.save(update_fields=["password"])

    def _collect_all(self, users):
        """Rebuild the `generated` mapping listing every demo account."""
        generated = {}
        for obj in users:
            user = self._user_of(obj)
            if not user:
                continue
            generated.setdefault(user.role + "s", []).append((user.username, user.full_name))
        return generated

    def _write_credentials(self, generated):
        if not generated:
            return
        password = getattr(self, "_shared_password", self._fixed_password)
        if not password:
            return
        from core.management.commands._paths import credentials_path

        lines = [
            "SIWES HUB - DEMONSTRATION ACCOUNTS (generated locally)",
            "======================================================",
            "",
            "These accounts and passwords exist ONLY for the local demonstration",
            "of this project. Change every password before any real/production",
            "use of this software.",
            "",
        ]
        for _role, rows in sorted(generated.items()):
            for username, _name in rows:
                lines.append(f"  username: {username}")
                lines.append(f"  password: {password}")
                lines.append("")
        lines.append("(Every demonstration account above shares the same password.)")
        lines.append("")
        credentials_path().write_text("\n".join(lines), encoding="utf-8")

    # ------------------------------------------------------------------ #
    # Program data
    # ------------------------------------------------------------------ #
    def _create_organizations(self):
        data = [
            ("Crestwave Technologies Ltd", "15 Adeola Odeku St, Victoria Island, Lagos", "Software development"),
            ("Blueforge Analytics", "22 Awolowo Road, Ikoyi, Lagos", "Data analytics"),
            ("Pixelworks Digital Hub", "4 Unity Crescent, Bodija, Ibadan", "Web design & branding"),
            ("Networkx Systems", "8 Stadium Road, Port Harcourt", "Network infrastructure"),
        ]
        organizations = []
        for name, address, industry in data:
            organization, _ = Organization.objects.get_or_create(
                name=name,
                defaults={
                    "address": address,
                    "industry": industry,
                    "contact_person": "Demo contacts Listing",
                    "contact_phone": "+234 800 000 0000",
                    "contact_email": "contact@siweshub-demo.edu",
                },
            )
            if not organization.contact_person or organization.contact_person == "Demo contacts Listing":
                organization.contact_person = "Demo Contact"
                organization.contact_phone = "+234 800 000 0000"
                organization.contact_email = f"info@{name.split()[0].lower()}.demo"
                organization.save()
            organizations.append(organization)
        return organizations

    def _create_session(self):
        start = monday_of_weeks_ago(6)
        session, created = SIWESSession.objects.get_or_create(
            name="2025/2026 Session",
            defaults={
                "start_date": start,
                "end_date": start + timedelta(days=180),
                "description": "Six-month industrial training window for the demonstration cohort.",
                "is_active": True,
            },
        )
        return session

    def _create_placements(self, students, supervisors, organizations, session):
        # Leave student6 unplaced on purpose so the administrator demo flow
        # can assign them live during the defence.
        mapping = [
            (0, 0, 0),  # student -> organization index, supervisor index
            (1, 0, 0),
            (2, 1, 0),
            (3, 2, 1),
            (4, 3, 1),
        ]
        for student_index, org_index, sup_index in mapping:
            student = students[student_index]
            organization = organizations[org_index]
            supervisor = supervisors[sup_index]
            start = monday_of_weeks_ago(4)
            placement, created = Placement.objects.get_or_create(
                student=student,
                defaults={
                    "organization": organization,
                    "supervisor": supervisor,
                    "siwes_session": session,
                    "start_date": start,
                    "end_date": start + timedelta(days=120),
                    "is_active": True,
                },
            )
            if (not created) and placement.organization is None:
                placement.organization = organization
                placement.supervisor = supervisor
                placement.siwes_session = session
                placement.save()

    def _create_logs(self, students, supervisors):
        supervisors_map = {0: supervisors[0], 1: supervisors[1]}
        log_plan = [
            (0, 12, "Built the landing page of an e-commerce site with HTML/CSS.", "VS Code, Chrome DevTools", "Responsive layout design", DailyLog.STATUS_APPROVED),
            (0, 10, "Implemented the product listing API endpoints.", "Django, REST framework", "Understood serializers", DailyLog.STATUS_APPROVED),
            (0, 8, "Drafted the cart redesign.", "Figma", "Prototyping", DailyLog.STATUS_SUBMITTED),
            (0, 3, "Explored Git branching for a hotfix workflow.", "Git, GitHub", "Branch management", DailyLog.STATUS_DRAFT),
            (0, 2, "Fixed a checkout bug listed on the board.", "JavaScript", "Event handling", DailyLog.STATUS_REJECTED),
            (1, 9, "Cleaned a customer dataset with Pandas.", "Python, Pandas", "Data wrangling", DailyLog.STATUS_APPROVED),
            (1, 7, "Built a dashboard chart.", "Plotly", "Data visualization", DailyLog.STATUS_SUBMITTED),
            (1, 4, "Wrote unit tests for the reporting module.", "pytest", "Testing discipline", DailyLog.STATUS_DRAFT),
            (2, 11, "Set up a Linux VM and practiced shell navigation.", "Bash, Ubuntu", "Command line", DailyLog.STATUS_APPROVED),
            (2, 6, "Configured a web server instance.", "Nginx", "Server basics", DailyLog.STATUS_SUBMITTED),
            (3, 10, "Terminated and tested cables for a LAN.", "Crimping tool, cables", "Network cabling", DailyLog.STATUS_APPROVED),
            (3, 5, "Documented a switch rack.", "Excel", "Documentation", DailyLog.STATUS_DRAFT),
            (4, 13, "Designed social media fliers.", "Photoshop", "Graphic design", DailyLog.STATUS_SUBMITTED),
            (4, 9, "Researched brand colour palettes.", "Adobe Color", "Colour theory", DailyLog.STATUS_REJECTED),
        ]

        def today_local():
            return timezone.localdate()

        for student_index, days_ago, activities, tools, skills, status in log_plan:
            student = students[student_index]
            log_date = today_local() - timedelta(days=days_ago)
            entry, created = DailyLog.objects.get_or_create(
                student=student,
                log_date=log_date,
                defaults={
                    "activities": activities,
                    "tools_used": tools,
                    "skills_learned": skills,
                    "status": status,
                    "supervisor": (supervisors_map[0] if status in (DailyLog.STATUS_APPROVED, DailyLog.STATUS_REJECTED) and student.placement and student.placement.supervisor_id == supervisors_map[0].id else None),
                },
            )
            if not created:
                continue
            if status in (DailyLog.STATUS_SUBMITTED, DailyLog.STATUS_APPROVED, DailyLog.STATUS_REJECTED):
                entry.submitted_at = timezone.now() - timedelta(days=days_ago)
            placement = getattr(student, "placement", None)
            if status in (DailyLog.STATUS_APPROVED, DailyLog.STATUS_REJECTED):
                entry.supervisor = placement.supervisor if placement else None
                entry.reviewed_at = timezone.now() - timedelta(days=max(days_ago - 1, 0))
                entry.supervisor_comment = (
                    "Good work - concise and clear. Approved."
                    if status == DailyLog.STATUS_APPROVED
                    else "Add the exact task outcome and resend, please."
                )
            if status == DailyLog.STATUS_SUBMITTED or status in (DailyLog.STATUS_APPROVED, DailyLog.STATUS_REJECTED):
                entry.save()

    def _create_reports(self, students, supervisors):
        plans = [
            (0, 2, WeeklyReport.STATUS_APPROVED, "Completed the site landing page and product listing; started cart work."),
            (0, 1, WeeklyReport.STATUS_SUBMITTED, "Worked through the cart module and API integration."),
            (1, 2, WeeklyReport.STATUS_APPROVED, "Cleaned data and produced three dashboard charts."),
            (1, 1, WeeklyReport.STATUS_SUBMITTED, "Added report exports and automated tests."),
            (2, 1, WeeklyReport.STATUS_SUBMITTED, "Server setup basics and deployment practice."),
        ]
        for student_index, weeks_ago, status, summary in plans:
            student = students[student_index]
            week_start = monday_of_weeks_ago(weeks_ago)
            report, created = WeeklyReport.objects.get_or_create(
                student=student,
                week_start=week_start,
                defaults={
                    "week_end": week_start + timedelta(days=6),
                    "summary_of_activities": summary,
                    "challenges_faced": "Balancing speed with accuracy when learning new tools.",
                    "lessons_learned": "Version control and clear documentation speed up teamwork.",
                    "skills_acquired": "Communication, time management, Git",
                    "status": status,
                },
            )
            if created and status in (WeeklyReport.STATUS_APPROVED,):
                placement = getattr(student, "placement", None)
                report.supervisor = placement.supervisor if placement else None
                report.supervisor_comment = "Well organized week. Approved to continue."
                report.reviewed_at = timezone.now() - timedelta(days=2)
                report.save()

    def _create_attendance(self, students, supervisors):
        # Ten weekdays of history for the first five students.
        statuses_cycle = [
            Attendance.STATUS_PRESENT, Attendance.STATUS_PRESENT, Attendance.STATUS_PRESENT,
            Attendance.STATUS_PRESENT, Attendance.STATUS_ABSENT, Attendance.STATUS_PRESENT,
            Attendance.STATUS_LATE,
        ]
        days = [
            timezone.localdate() - timedelta(days=i)
            for i in range(1, 21)
            if (timezone.localdate() - timedelta(days=i)).weekday() < 5
        ]
        days = sorted(days, reverse=True)[:10]
        for student_index in range(5):
            student = students[student_index]
            supervisor = None
            placement = getattr(student, "placement", None)
            if placement:
                supervisor = placement.supervisor
            for index, day in enumerate(days):
                status = statuses_cycle[(student_index + index) % len(statuses_cycle)]
                Attendance.objects.get_or_create(
                    student=student,
                    date=day,
                    defaults={
                        "status": status,
                        "note": "Seeded demonstration record.",
                        "recorded_by": (supervisor.user if supervisor else None),
                        "verified_by": supervisor,
                        "verified_at": timezone.now() if supervisor else None,
                    },
                )

    def _create_skills(self, students):
        skill_plan = [
            (0, "Responsive web design", "intermediate", 9),
            (0, "Git version control", "intermediate", 4),
            (1, "Data cleaning with Pandas", "advanced", 8),
            (1, "Data visualization", "intermediate", 3),
            (2, "Linux command line", "beginner", 11),
            (3, "LAN cabling", "intermediate", 10),
            (4, "Graphic design", "beginner", 12),
        ]
        for student_index, name, level, days_ago in skill_plan:
            student = students[student_index]
            Skill.objects.get_or_create(
                student=student,
                name=name,
                defaults={
                    "description": f"Learned while performing day-to-day SIWES tasks ({name}).",
                    "date_learned": timezone.localdate() - timedelta(days=days_ago),
                    "proficiency_level": level,
                },
            )

    def _create_projects(self, students, supervisors):
        plans = [
            (0, "E-commerce Product Catalogue", "in_progress", "not_submitted"),
            (1, "Customer Churn Mini-Dashboard", "in_progress", "submitted"),
            (2, "Ubuntu Server Setup Guide", "completed", "approved"),
            (3, "LAN Deployment Checklist Tool", "in_progress", "submitted"),
        ]
        for student_index, title, status, review_status in plans:
            student = students[student_index]
            project, created = StudentProject.objects.get_or_create(
                student=student,
                defaults={
                    "title": title,
                    "description": f"demonstration project: {title} for SIWES deliverable.",
                    "objectives": "Apply workplace skills to a small, concrete deliverable.",
                    "technologies": "HTML, CSS, Python",
                    "status": status,
                    "review_status": review_status,
                },
            )
            if created and review_status in (StudentProject.REVIEW_APPROVED,):
                placement = getattr(student, "placement", None)
                project.supervisor = placement.supervisor if placement else None
                project.supervisor_comment = "Solid final deliverable. Approved."
                project.reviewed_at = timezone.now() - timedelta(days=1)
                project.save()

    def _create_announcements(self, admin):
        Announcement.objects.get_or_create(
            title="Welcome to the 2025/2026 SIWES session",
            defaults={
                "content": "All students should submit their placement details and begin daily logs from week 1.",
                "audience": Announcement.AUDIENCE_ALL,
                "created_by": admin,
            },
        )
        Announcement.objects.get_or_create(
            title="Weekly reports due every Monday",
            defaults={
                "content": "Remember: weekly reports must be submitted before 5 pm every Monday for review.",
                "audience": Announcement.AUDIENCE_STUDENTS,
                "created_by": admin,
            },
        )
        Announcement.objects.get_or_create(
            title="Supervisors: review pending logs",
            defaults={
                "content": "Please review pending daily logs and attendance each Friday.",
                "audience": Announcement.AUDIENCE_SUPERVISORS,
                "created_by": admin,
            },
        )
