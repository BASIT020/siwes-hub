# SIWES Hub - Migration Reference

Every migration currently applied to `database/data/db.sqlite3`, grouped by
application. Generated from the project (tools/generate_migrations_doc.py);
regenerate after adding migrations.

Apply commands:

```
cd backend
python manage.py migrate          # apply everything pending
python manage.py showmigrations   # inspect applied state
```

## accounts (1 migration)

* `0001_initial` - Create model User

## core (2 migrations)

* `0001_initial` - Create model SIWESSession, Create model AuditLog, Create model Placement
* `0002_initial` - Add field student to placement, Add field supervisor to placement, Add field siwes_session to placement

## organizations (1 migration)

* `0001_initial` - Create model Organization

## students (1 migration)

* `0001_initial` - Create model StudentProfile, Create model Skill

## supervisors (2 migrations)

* `0001_initial` - Create model SupervisorProfile
* `0002_supervisorprofile_is_pending` - Add field is_pending to supervisorprofile

## logs (2 migrations)

* `0001_initial` - Create model DailyLog
* `0002_initial` - Add field student to dailylog, Add field supervisor to dailylog, Create index logs_dailyl_student_86e10c_idx on field(s) student, status of model dailylog, Create constraint unique_daily_log_per_student_per_date on model dailylog

## reports (2 migrations)

* `0001_initial` - Create model WeeklyReport
* `0002_alter_weeklyreport_week_end` - Alter field week_end on weeklyreport

## attendance (2 migrations)

* `0001_initial` - Create model Attendance
* `0002_initial` - Add field student to attendance, Add field verified_by to attendance, Create index attendance__student_76a8d7_idx on field(s) student, date of model attendance, Create constraint unique_attendance_per_student_per_date on model attendance

## projects (1 migration)

* `0001_initial` - Create model StudentProject

## announcements (1 migration)

* `0001_initial` - Create model Announcement

## notifications (1 migration)

* `0001_initial` - Create model Notification


**16 migrations in total.**
