# SIWES Hub - API Documentation

All endpoints live under `/api/` and use **session authentication** with **CSRF
protection** (the frontend sends the `X-CSRFToken` header from the `csrftoken`
cookie). Every request must be authenticated unless stated otherwise.

Conventions:

* Successful list requests return a JSON **array** when `?page=` is omitted,
  or `{count, pages, page, results}` when paginated.
* Errors return `{"detail": "..."}` (or field errors as
  `{"field": ["message", ...]}`) with a proper 4xx status code.
* Roles mentioned per endpoint are enforced server-side.

## Endpoint index

| Method(s) | Endpoint | View |
|---|---|---|
| GET | `/django-admin/` |  |
| GET | `/django-admin/login/` |  |
| GET | `/django-admin/logout/` |  |
| GET | `/django-admin/password_change/` |  |
| GET | `/django-admin/password_change/done/` |  |
| GET | `/django-admin/autocomplete/` |  |
| GET | `/django-admin/jsi18n/` |  |
| GET | `/django-admin/r/<int:content_type_id>/<path:object_id>/` |  |
| GET | `/django-admin/auth/group/` |  |
| GET | `/django-admin/auth/group/add/` |  |
| GET | `/django-admin/auth/group/<path:object_id>/history/` |  |
| GET | `/django-admin/auth/group/<path:object_id>/delete/` |  |
| GET | `/django-admin/auth/group/<path:object_id>/change/` |  |
| GET, POST, PUT, PATCH, DELETE | `/django-admin/auth/group/<path:object_id>/` | RedirectView |
| GET | `/django-admin/accounts/user/<id>/password/` |  |
| GET | `/django-admin/accounts/user/` |  |
| GET | `/django-admin/accounts/user/add/` |  |
| GET | `/django-admin/accounts/user/<path:object_id>/history/` |  |
| GET | `/django-admin/accounts/user/<path:object_id>/delete/` |  |
| GET | `/django-admin/accounts/user/<path:object_id>/change/` |  |
| GET, POST, PUT, PATCH, DELETE | `/django-admin/accounts/user/<path:object_id>/` | RedirectView |
| GET | `/django-admin/core/siwessession/` |  |
| GET | `/django-admin/core/siwessession/add/` |  |
| GET | `/django-admin/core/siwessession/<path:object_id>/history/` |  |
| GET | `/django-admin/core/siwessession/<path:object_id>/delete/` |  |
| GET | `/django-admin/core/siwessession/<path:object_id>/change/` |  |
| GET, POST, PUT, PATCH, DELETE | `/django-admin/core/siwessession/<path:object_id>/` | RedirectView |
| GET | `/django-admin/core/placement/` |  |
| GET | `/django-admin/core/placement/add/` |  |
| GET | `/django-admin/core/placement/<path:object_id>/history/` |  |
| GET | `/django-admin/core/placement/<path:object_id>/delete/` |  |
| GET | `/django-admin/core/placement/<path:object_id>/change/` |  |
| GET, POST, PUT, PATCH, DELETE | `/django-admin/core/placement/<path:object_id>/` | RedirectView |
| GET | `/django-admin/core/auditlog/` |  |
| GET | `/django-admin/core/auditlog/add/` |  |
| GET | `/django-admin/core/auditlog/<path:object_id>/history/` |  |
| GET | `/django-admin/core/auditlog/<path:object_id>/delete/` |  |
| GET | `/django-admin/core/auditlog/<path:object_id>/change/` |  |
| GET, POST, PUT, PATCH, DELETE | `/django-admin/core/auditlog/<path:object_id>/` | RedirectView |
| GET | `/django-admin/organizations/organization/` |  |
| GET | `/django-admin/organizations/organization/add/` |  |
| GET | `/django-admin/organizations/organization/<path:object_id>/history/` |  |
| GET | `/django-admin/organizations/organization/<path:object_id>/delete/` |  |
| GET | `/django-admin/organizations/organization/<path:object_id>/change/` |  |
| GET, POST, PUT, PATCH, DELETE | `/django-admin/organizations/organization/<path:object_id>/` | RedirectView |
| GET | `/django-admin/logs/dailylog/` |  |
| GET | `/django-admin/logs/dailylog/add/` |  |
| GET | `/django-admin/logs/dailylog/<path:object_id>/history/` |  |
| GET | `/django-admin/logs/dailylog/<path:object_id>/delete/` |  |
| GET | `/django-admin/logs/dailylog/<path:object_id>/change/` |  |
| GET, POST, PUT, PATCH, DELETE | `/django-admin/logs/dailylog/<path:object_id>/` | RedirectView |
| GET | `/django-admin/reports/weeklyreport/` |  |
| GET | `/django-admin/reports/weeklyreport/add/` |  |
| GET | `/django-admin/reports/weeklyreport/<path:object_id>/history/` |  |
| GET | `/django-admin/reports/weeklyreport/<path:object_id>/delete/` |  |
| GET | `/django-admin/reports/weeklyreport/<path:object_id>/change/` |  |
| GET, POST, PUT, PATCH, DELETE | `/django-admin/reports/weeklyreport/<path:object_id>/` | RedirectView |
| GET | `/django-admin/projects/studentproject/` |  |
| GET | `/django-admin/projects/studentproject/add/` |  |
| GET | `/django-admin/projects/studentproject/<path:object_id>/history/` |  |
| GET | `/django-admin/projects/studentproject/<path:object_id>/delete/` |  |
| GET | `/django-admin/projects/studentproject/<path:object_id>/change/` |  |
| GET, POST, PUT, PATCH, DELETE | `/django-admin/projects/studentproject/<path:object_id>/` | RedirectView |
| GET | `/django-admin/announcements/announcement/` |  |
| GET | `/django-admin/announcements/announcement/add/` |  |
| GET | `/django-admin/announcements/announcement/<path:object_id>/history/` |  |
| GET | `/django-admin/announcements/announcement/<path:object_id>/delete/` |  |
| GET | `/django-admin/announcements/announcement/<path:object_id>/change/` |  |
| GET, POST, PUT, PATCH, DELETE | `/django-admin/announcements/announcement/<path:object_id>/` | RedirectView |
| GET | `/django-admin/^(?P<app_label>auth|accounts|core|organizations|logs|reports|projects|announcements)/$` |  |
| GET | `/api/auth/csrf/` | csrf |
| POST | `/api/auth/login/` | LoginView |
| POST | `/api/auth/logout/` | LogoutView |
| GET | `/api/auth/me/` | MeView |
| POST | `/api/auth/change-password/` | ChangePasswordView |
| POST | `/api/auth/register/student/` | RegisterStudentView |
| POST | `/api/auth/register/supervisor/` | RegisterSupervisorView |
| GET | `/api/core/dashboard/` | DashboardView |
| GET | `/api/core/^sessions/$` |  |
| GET | `/api/core/^sessions\.(?P<format>[a-z0-9]+)/?$` |  |
| GET | `/api/core/^sessions/(?P<pk>[^/.]+)/$` |  |
| GET | `/api/core/^sessions/(?P<pk>[^/.]+)\.(?P<format>[a-z0-9]+)/?$` |  |
| GET | `/api/core/^placements/$` |  |
| GET | `/api/core/^placements\.(?P<format>[a-z0-9]+)/?$` |  |
| GET | `/api/core/^placements/(?P<pk>[^/.]+)/$` |  |
| GET | `/api/core/^placements/(?P<pk>[^/.]+)\.(?P<format>[a-z0-9]+)/?$` |  |
| GET | `/api/core/` | APIRootView |
| GET | `/api/core/<drf_format_suffix:format>` | APIRootView |
| GET | `/api/users/` | UserListCreateView |
| GET | `/api/users/<int:pk>/` | UserDetailView |
| GET | `/api/users/<int:pk>/reset-password/` | UserPasswordResetView |
| GET, POST | `/api/organizations/` | OrganizationListCreateView |
| GET, PATCH, DELETE | `/api/organizations/<int:pk>/` | OrganizationDetailView |
| GET, POST | `/api/students/` | StudentListCreateView |
| GET, PATCH | `/api/students/me/` | MyStudentProfileView |
| GET, PATCH, DELETE | `/api/students/<int:pk>/` | StudentDetailView |
| GET, POST | `/api/students/skills/` | SkillListCreateView |
| GET | `/api/students/skills/<int:pk>/` | SkillDetailView |
| GET, POST | `/api/supervisors/` | SupervisorListCreateView |
| GET, PATCH | `/api/supervisors/<int:pk>/` | SupervisorDetailView |
| GET, POST | `/api/logs/` | DailyLogListCreateView |
| GET, PATCH, DELETE | `/api/logs/<int:pk>/` | DailyLogDetailView |
| POST | `/api/logs/<int:pk>/submit/` | DailyLogSubmitView |
| POST | `/api/logs/<int:pk>/review/` | DailyLogReviewView |
| GET, POST | `/api/reports/` | WeeklyReportListCreateView |
| GET, PATCH, DELETE | `/api/reports/<int:pk>/` | WeeklyReportDetailView |
| POST | `/api/reports/<int:pk>/submit/` | WeeklyReportSubmitView |
| POST | `/api/reports/<int:pk>/review/` | WeeklyReportReviewView |
| GET, POST | `/api/attendance/` | AttendanceListCreateView |
| GET | `/api/attendance/summary/` | AttendanceSummaryView |
| GET, PATCH | `/api/attendance/<int:pk>/` | AttendanceDetailView |
| GET, POST, PATCH | `/api/projects/me/` | MyProjectView |
| POST | `/api/projects/me/submit/` | MyProjectSubmitView |
| GET | `/api/projects/` | ProjectListView |
| POST | `/api/projects/<int:pk>/review/` | ProjectReviewView |
| GET, POST | `/api/announcements/` | AnnouncementListCreateView |
| GET, PATCH, DELETE | `/api/announcements/<int:pk>/` | AnnouncementDetailView |
| POST | `/api/announcements/<int:pk>/read/` | AnnouncementMarkReadView |
| GET | `/api/notifications/` | NotificationListView |
| POST | `/api/notifications/read-all/` | NotificationMarkAllReadView |
| POST | `/api/notifications/<int:pk>/read/` | NotificationMarkReadView |

## Key workflows

### Authentication (accounts)
- `POST /api/auth/login/` `{username, password}` -> sets the session cookie. Throttled to 5 failures per 10 minutes per username.
- `POST /api/auth/logout/` - ends the session.
- `GET /api/auth/me/` - current user (id, username, full_name, role, dashboard hints).
- `GET /api/auth/csrf/` - ensures the CSRF cookie exists.
- `POST /api/auth/register/student/` (public) `{full_name, email, matric_number, password, password2[, department, faculty, level]}` -> creates the user (role student is set server-side, password hashed) plus the StudentProfile; username becomes the matric number; the session starts immediately. Validation errors (duplicate email/matric, weak password) come back as 400 field errors; throttled to 8 registrations per IP per window.
- `POST /api/auth/register/supervisor/` (public) `{username, full_name, email, password, password2[, title, staff_id, department]}` -> creates user + SupervisorProfile with the account inactive (`is_pending`); returns `status=pending_approval` and notifies every administrator. No session starts.
- `GET /api/supervisors/?pending=true` (admin) - only the self-registered supervisors that still await approval (drives the Pending Supervisor Approvals banner on the Supervisors page).
- Administrator approval: `PATCH /api/supervisors/<id>/` `{is_active: true}` on a pending supervisor activates the paired user account (audit `SUPERVISOR APPROVED`, the supervisor is notified). `{is_active: false}` on a pending supervisor **rejects** the registration (audit `SUPERVISOR REJECTED`, the applicant is notified, the account stays unable to sign in). Deactivating an already-active supervisor is audited separately (`SUPERVISOR DEACTIVATED`). The serializer exposes `user_is_active`/`is_pending`.

### Daily logs (logs)
- `GET /api/logs/` - students see their own logs; supervisors see their assigned students' logs; filters: `?status=draft|submitted|approved|rejected`, `?student=<id>`.
- `POST /api/logs/` (student) - create draft; one log per date, duplicates get 400.
- `PATCH /api/logs/<id>/` (student owner, draft/rejected only).
- `POST /api/logs/<id>/submit/` (student owner).
- `POST /api/logs/<id>/review/` (supervisor) `{decision: approved|rejected, comment}` - comment required when rejecting; notifies the student; audit-logged.

### Weekly reports (reports)
- Same pattern: `GET/POST /api/reports/`, `PATCH /api/reports/<id>/`, `POST /api/reports/<id>/submit/`, `POST /api/reports/<id>/review/`.

### Attendance (attendance)
- `GET /api/attendance/` - records scoped to role (`?student=`, `?date=`).
- `POST /api/attendance/` (supervisor/admin) `{student, date, status, remarks}`.
- `PATCH /api/attendance/<id>/` (supervisor/admin).
- `GET /api/attendance/summary/` - per-role summary incl. attendance rate.

### Projects (projects)
- `GET /api/projects/me/` (student) / `GET /api/projects/` (supervisor/admin).
- `POST /api/projects/` (student, one per student), `PATCH`, `POST /api/projects/<id>/submit/`, `POST /api/projects/<id>/review/`.

### Students & skills (students)
- `GET /api/students/` (supervisor/admin, filters), `POST /api/students/` (admin creates account+profile), `GET/PATCH /api/students/me/` (student own profile), `GET/PATCH/DELETE /api/students/<id>/` (admin).
- Skills: `GET/POST /api/students/skills/`, `PATCH/DELETE /api/students/skills/<id>/` (student owns own skills).

### Supervisors (supervisors)
- `GET /api/supervisors/`, `POST` (admin), `GET/PATCH /api/supervisors/<id>/`, `GET /api/supervisors/me/`.

### Organisations & placements (organizations, core)
- `GET/POST /api/organizations/`, `GET/PATCH/DELETE /api/organizations/<id>/`.
- `GET/POST /api/core/placements/`, `GET/PATCH /api/core/placements/<id>/` (admin assigns student -> organisation + supervisor).
- SIWES sessions: `GET/POST /api/core/sessions/`, `PATCH /api/core/sessions/<id>/` (one active session).

### Dashboard, announcements, notifications
- `GET /api/core/dashboard/` - live role-specific statistics.
- `GET/POST /api/announcements/`, `PATCH/DELETE /api/announcements/<id>/` (admin), `POST /api/announcements/<id>/read/` (per-user read state).
- `GET /api/notifications/` (`?unread=true`, `?page=`), `POST /api/notifications/<id>/read/`, `POST /api/notifications/read-all/`.

### Audit & users
- `GET /api/core/audit/` (admin) - audit trail, newest first.
- `GET/POST /api/users/`, `GET/PATCH /api/users/<id>/` (admin user management, password changes included).
