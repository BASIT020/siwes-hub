-- =====================================================================
-- SIWES Hub - full SQLite schema
-- Generated from the Django migrations (python tools/generate_docs.py).
-- Do not edit by hand: changing a model requires a new Django migration.
-- =====================================================================

-- table accounts_user
CREATE TABLE "accounts_user" ("id" integer NOT NULL PRIMARY KEY AUTOINCREMENT, "password" varchar(128) NOT NULL, "last_login" datetime NULL, "is_superuser" bool NOT NULL, "username" varchar(150) NOT NULL UNIQUE, "first_name" varchar(150) NOT NULL, "last_name" varchar(150) NOT NULL, "is_staff" bool NOT NULL, "is_active" bool NOT NULL, "date_joined" datetime NOT NULL, "email" varchar(254) NOT NULL, "phone" varchar(20) NOT NULL, "full_name" varchar(150) NOT NULL, "role" varchar(20) NOT NULL);

-- table accounts_user_groups
CREATE TABLE "accounts_user_groups" ("id" integer NOT NULL PRIMARY KEY AUTOINCREMENT, "user_id" bigint NOT NULL REFERENCES "accounts_user" ("id") DEFERRABLE INITIALLY DEFERRED, "group_id" integer NOT NULL REFERENCES "auth_group" ("id") DEFERRABLE INITIALLY DEFERRED);

-- table accounts_user_user_permissions
CREATE TABLE "accounts_user_user_permissions" ("id" integer NOT NULL PRIMARY KEY AUTOINCREMENT, "user_id" bigint NOT NULL REFERENCES "accounts_user" ("id") DEFERRABLE INITIALLY DEFERRED, "permission_id" integer NOT NULL REFERENCES "auth_permission" ("id") DEFERRABLE INITIALLY DEFERRED);

-- table announcements_announcement
CREATE TABLE "announcements_announcement" ("id" integer NOT NULL PRIMARY KEY AUTOINCREMENT, "title" varchar(200) NOT NULL, "content" text NOT NULL, "audience" varchar(20) NOT NULL, "created_at" datetime NOT NULL, "updated_at" datetime NOT NULL, "is_active" bool NOT NULL, "created_by_id" bigint NULL REFERENCES "accounts_user" ("id") DEFERRABLE INITIALLY DEFERRED);

-- table announcements_announcement_read_by
CREATE TABLE "announcements_announcement_read_by" ("id" integer NOT NULL PRIMARY KEY AUTOINCREMENT, "announcement_id" bigint NOT NULL REFERENCES "announcements_announcement" ("id") DEFERRABLE INITIALLY DEFERRED, "user_id" bigint NOT NULL REFERENCES "accounts_user" ("id") DEFERRABLE INITIALLY DEFERRED);

-- table attendance_attendance
CREATE TABLE "attendance_attendance" ("id" integer NOT NULL PRIMARY KEY AUTOINCREMENT, "date" date NOT NULL, "status" varchar(20) NOT NULL, "note" varchar(250) NOT NULL, "verified_at" datetime NULL, "created_at" datetime NOT NULL, "recorded_by_id" bigint NOT NULL REFERENCES "accounts_user" ("id") DEFERRABLE INITIALLY DEFERRED, "student_id" bigint NOT NULL REFERENCES "students_studentprofile" ("id") DEFERRABLE INITIALLY DEFERRED, "verified_by_id" bigint NULL REFERENCES "supervisors_supervisorprofile" ("id") DEFERRABLE INITIALLY DEFERRED, CONSTRAINT "unique_attendance_per_student_per_date" UNIQUE ("student_id", "date"));

-- table auth_group
CREATE TABLE "auth_group" ("id" integer NOT NULL PRIMARY KEY AUTOINCREMENT, "name" varchar(150) NOT NULL UNIQUE);

-- table auth_group_permissions
CREATE TABLE "auth_group_permissions" ("id" integer NOT NULL PRIMARY KEY AUTOINCREMENT, "group_id" integer NOT NULL REFERENCES "auth_group" ("id") DEFERRABLE INITIALLY DEFERRED, "permission_id" integer NOT NULL REFERENCES "auth_permission" ("id") DEFERRABLE INITIALLY DEFERRED);

-- table auth_permission
CREATE TABLE "auth_permission" ("id" integer NOT NULL PRIMARY KEY AUTOINCREMENT, "content_type_id" integer NOT NULL REFERENCES "django_content_type" ("id") DEFERRABLE INITIALLY DEFERRED, "codename" varchar(100) NOT NULL, "name" varchar(255) NOT NULL);

-- table core_auditlog
CREATE TABLE "core_auditlog" ("id" integer NOT NULL PRIMARY KEY AUTOINCREMENT, "action" varchar(120) NOT NULL, "detail" text NOT NULL, "timestamp" datetime NOT NULL, "actor_id" bigint NULL REFERENCES "accounts_user" ("id") DEFERRABLE INITIALLY DEFERRED);

-- table core_placement
CREATE TABLE "core_placement" ("id" integer NOT NULL PRIMARY KEY AUTOINCREMENT, "start_date" date NULL, "end_date" date NULL, "is_active" bool NOT NULL, "remarks" text NOT NULL, "created_at" datetime NOT NULL, "updated_at" datetime NOT NULL, "organization_id" bigint NULL REFERENCES "organizations_organization" ("id") DEFERRABLE INITIALLY DEFERRED, "student_id" bigint NOT NULL UNIQUE REFERENCES "students_studentprofile" ("id") DEFERRABLE INITIALLY DEFERRED, "supervisor_id" bigint NULL REFERENCES "supervisors_supervisorprofile" ("id") DEFERRABLE INITIALLY DEFERRED, "siwes_session_id" bigint NULL REFERENCES "core_siwessession" ("id") DEFERRABLE INITIALLY DEFERRED);

-- table core_siwessession
CREATE TABLE "core_siwessession" ("id" integer NOT NULL PRIMARY KEY AUTOINCREMENT, "name" varchar(120) NOT NULL UNIQUE, "start_date" date NOT NULL, "end_date" date NOT NULL, "description" text NOT NULL, "is_active" bool NOT NULL, "created_at" datetime NOT NULL);

-- table django_admin_log
CREATE TABLE "django_admin_log" ("id" integer NOT NULL PRIMARY KEY AUTOINCREMENT, "object_id" text NULL, "object_repr" varchar(200) NOT NULL, "action_flag" smallint unsigned NOT NULL CHECK ("action_flag" >= 0), "change_message" text NOT NULL, "content_type_id" integer NULL REFERENCES "django_content_type" ("id") DEFERRABLE INITIALLY DEFERRED, "user_id" bigint NOT NULL REFERENCES "accounts_user" ("id") DEFERRABLE INITIALLY DEFERRED, "action_time" datetime NOT NULL);

-- table django_content_type
CREATE TABLE "django_content_type" ("id" integer NOT NULL PRIMARY KEY AUTOINCREMENT, "app_label" varchar(100) NOT NULL, "model" varchar(100) NOT NULL);

-- table django_migrations
CREATE TABLE "django_migrations" ("id" integer NOT NULL PRIMARY KEY AUTOINCREMENT, "app" varchar(255) NOT NULL, "name" varchar(255) NOT NULL, "applied" datetime NOT NULL);

-- table django_session
CREATE TABLE "django_session" ("session_key" varchar(40) NOT NULL PRIMARY KEY, "session_data" text NOT NULL, "expire_date" datetime NOT NULL);

-- table logs_dailylog
CREATE TABLE "logs_dailylog" ("id" integer NOT NULL PRIMARY KEY AUTOINCREMENT, "log_date" date NOT NULL, "activities" text NOT NULL, "tools_used" varchar(250) NOT NULL, "skills_learned" varchar(250) NOT NULL, "hours_spent" decimal NULL, "remarks" text NOT NULL, "status" varchar(20) NOT NULL, "submitted_at" datetime NULL, "supervisor_comment" text NOT NULL, "reviewed_at" datetime NULL, "created_at" datetime NOT NULL, "updated_at" datetime NOT NULL, "student_id" bigint NOT NULL REFERENCES "students_studentprofile" ("id") DEFERRABLE INITIALLY DEFERRED, "supervisor_id" bigint NULL REFERENCES "supervisors_supervisorprofile" ("id") DEFERRABLE INITIALLY DEFERRED, CONSTRAINT "unique_daily_log_per_student_per_date" UNIQUE ("student_id", "log_date"));

-- table notifications_notification
CREATE TABLE "notifications_notification" ("id" integer NOT NULL PRIMARY KEY AUTOINCREMENT, "kind" varchar(40) NOT NULL, "title" varchar(150) NOT NULL, "body" text NOT NULL, "target_url" varchar(200) NOT NULL, "is_read" bool NOT NULL, "created_at" datetime NOT NULL, "recipient_id" bigint NOT NULL REFERENCES "accounts_user" ("id") DEFERRABLE INITIALLY DEFERRED);

-- table organizations_organization
CREATE TABLE "organizations_organization" ("id" integer NOT NULL PRIMARY KEY AUTOINCREMENT, "name" varchar(150) NOT NULL UNIQUE, "address" varchar(250) NOT NULL, "contact_person" varchar(120) NOT NULL, "contact_phone" varchar(20) NOT NULL, "contact_email" varchar(254) NOT NULL, "industry" varchar(120) NOT NULL, "is_active" bool NOT NULL, "created_at" datetime NOT NULL, "updated_at" datetime NOT NULL);

-- table projects_studentproject
CREATE TABLE "projects_studentproject" ("id" integer NOT NULL PRIMARY KEY AUTOINCREMENT, "title" varchar(200) NOT NULL, "description" text NOT NULL, "objectives" text NOT NULL, "technologies" varchar(250) NOT NULL, "status" varchar(20) NOT NULL, "review_status" varchar(20) NOT NULL, "submitted_at" datetime NULL, "reviewed_at" datetime NULL, "supervisor_comment" text NOT NULL, "created_at" datetime NOT NULL, "updated_at" datetime NOT NULL, "student_id" bigint NOT NULL UNIQUE REFERENCES "students_studentprofile" ("id") DEFERRABLE INITIALLY DEFERRED, "supervisor_id" bigint NULL REFERENCES "supervisors_supervisorprofile" ("id") DEFERRABLE INITIALLY DEFERRED);

-- table reports_weeklyreport
CREATE TABLE "reports_weeklyreport" ("id" integer NOT NULL PRIMARY KEY AUTOINCREMENT, "week_start" date NOT NULL, "summary_of_activities" text NOT NULL, "challenges_faced" text NOT NULL, "lessons_learned" text NOT NULL, "skills_acquired" varchar(250) NOT NULL, "status" varchar(20) NOT NULL, "submitted_at" datetime NULL, "supervisor_comment" text NOT NULL, "reviewed_at" datetime NULL, "created_at" datetime NOT NULL, "updated_at" datetime NOT NULL, "student_id" bigint NOT NULL REFERENCES "students_studentprofile" ("id") DEFERRABLE INITIALLY DEFERRED, "supervisor_id" bigint NULL REFERENCES "supervisors_supervisorprofile" ("id") DEFERRABLE INITIALLY DEFERRED, "week_end" date NULL, CONSTRAINT "unique_weekly_report_per_student_per_week" UNIQUE ("student_id", "week_start"));

-- table students_skill
CREATE TABLE "students_skill" ("id" integer NOT NULL PRIMARY KEY AUTOINCREMENT, "name" varchar(120) NOT NULL, "description" text NOT NULL, "date_learned" date NOT NULL, "proficiency_level" varchar(20) NOT NULL, "created_at" datetime NOT NULL, "related_activity_id" bigint NULL REFERENCES "logs_dailylog" ("id") DEFERRABLE INITIALLY DEFERRED, "student_id" bigint NOT NULL REFERENCES "students_studentprofile" ("id") DEFERRABLE INITIALLY DEFERRED, CONSTRAINT "unique_skill_per_student" UNIQUE ("student_id", "name"));

-- table students_studentprofile
CREATE TABLE "students_studentprofile" ("id" integer NOT NULL PRIMARY KEY AUTOINCREMENT, "matric_number" varchar(30) NOT NULL UNIQUE, "department" varchar(120) NOT NULL, "faculty" varchar(120) NOT NULL, "level" varchar(20) NOT NULL, "training_start_date" date NULL, "training_end_date" date NULL, "is_active" bool NOT NULL, "created_at" datetime NOT NULL, "updated_at" datetime NOT NULL, "user_id" bigint NOT NULL UNIQUE REFERENCES "accounts_user" ("id") DEFERRABLE INITIALLY DEFERRED);

-- table supervisors_supervisorprofile
CREATE TABLE "supervisors_supervisorprofile" ("id" integer NOT NULL PRIMARY KEY AUTOINCREMENT, "staff_id" varchar(30) NOT NULL, "title" varchar(80) NOT NULL, "department" varchar(120) NOT NULL, "is_active" bool NOT NULL, "created_at" datetime NOT NULL, "user_id" bigint NOT NULL UNIQUE REFERENCES "accounts_user" ("id") DEFERRABLE INITIALLY DEFERRED, "is_pending" bool NOT NULL);

-- index accounts_us_role_1fa9a5_idx
CREATE INDEX "accounts_us_role_1fa9a5_idx" ON "accounts_user" ("role");

-- index accounts_user_groups_group_id_bd11a704
CREATE INDEX "accounts_user_groups_group_id_bd11a704" ON "accounts_user_groups" ("group_id");

-- index accounts_user_groups_user_id_52b62117
CREATE INDEX "accounts_user_groups_user_id_52b62117" ON "accounts_user_groups" ("user_id");

-- index accounts_user_groups_user_id_group_id_59c0b32f_uniq
CREATE UNIQUE INDEX "accounts_user_groups_user_id_group_id_59c0b32f_uniq" ON "accounts_user_groups" ("user_id", "group_id");

-- index accounts_user_user_permissions_permission_id_113bb443
CREATE INDEX "accounts_user_user_permissions_permission_id_113bb443" ON "accounts_user_user_permissions" ("permission_id");

-- index accounts_user_user_permissions_user_id_e4f0a161
CREATE INDEX "accounts_user_user_permissions_user_id_e4f0a161" ON "accounts_user_user_permissions" ("user_id");

-- index accounts_user_user_permissions_user_id_permission_id_2ab516c2_uniq
CREATE UNIQUE INDEX "accounts_user_user_permissions_user_id_permission_id_2ab516c2_uniq" ON "accounts_user_user_permissions" ("user_id", "permission_id");

-- index announcemen_audienc_39c897_idx
CREATE INDEX "announcemen_audienc_39c897_idx" ON "announcements_announcement" ("audience", "is_active");

-- index announcements_announcement_created_by_id_79d7d337
CREATE INDEX "announcements_announcement_created_by_id_79d7d337" ON "announcements_announcement" ("created_by_id");

-- index announcements_announcement_read_by_announcement_id_8b3fec89
CREATE INDEX "announcements_announcement_read_by_announcement_id_8b3fec89" ON "announcements_announcement_read_by" ("announcement_id");

-- index announcements_announcement_read_by_announcement_id_user_id_243cf1f2_uniq
CREATE UNIQUE INDEX "announcements_announcement_read_by_announcement_id_user_id_243cf1f2_uniq" ON "announcements_announcement_read_by" ("announcement_id", "user_id");

-- index announcements_announcement_read_by_user_id_ff239c83
CREATE INDEX "announcements_announcement_read_by_user_id_ff239c83" ON "announcements_announcement_read_by" ("user_id");

-- index attendance__student_76a8d7_idx
CREATE INDEX "attendance__student_76a8d7_idx" ON "attendance_attendance" ("student_id", "date");

-- index attendance_attendance_recorded_by_id_d160f67d
CREATE INDEX "attendance_attendance_recorded_by_id_d160f67d" ON "attendance_attendance" ("recorded_by_id");

-- index attendance_attendance_student_id_94863613
CREATE INDEX "attendance_attendance_student_id_94863613" ON "attendance_attendance" ("student_id");

-- index attendance_attendance_verified_by_id_0f32e0a4
CREATE INDEX "attendance_attendance_verified_by_id_0f32e0a4" ON "attendance_attendance" ("verified_by_id");

-- index auth_group_permissions_group_id_b120cbf9
CREATE INDEX "auth_group_permissions_group_id_b120cbf9" ON "auth_group_permissions" ("group_id");

-- index auth_group_permissions_group_id_permission_id_0cd325b0_uniq
CREATE UNIQUE INDEX "auth_group_permissions_group_id_permission_id_0cd325b0_uniq" ON "auth_group_permissions" ("group_id", "permission_id");

-- index auth_group_permissions_permission_id_84c5c92e
CREATE INDEX "auth_group_permissions_permission_id_84c5c92e" ON "auth_group_permissions" ("permission_id");

-- index auth_permission_content_type_id_2f476e4b
CREATE INDEX "auth_permission_content_type_id_2f476e4b" ON "auth_permission" ("content_type_id");

-- index auth_permission_content_type_id_codename_01ab375a_uniq
CREATE UNIQUE INDEX "auth_permission_content_type_id_codename_01ab375a_uniq" ON "auth_permission" ("content_type_id", "codename");

-- index core_auditlog_actor_id_ab091f3c
CREATE INDEX "core_auditlog_actor_id_ab091f3c" ON "core_auditlog" ("actor_id");

-- index core_placement_organization_id_cb4dda46
CREATE INDEX "core_placement_organization_id_cb4dda46" ON "core_placement" ("organization_id");

-- index core_placement_siwes_session_id_2555fda0
CREATE INDEX "core_placement_siwes_session_id_2555fda0" ON "core_placement" ("siwes_session_id");

-- index core_placement_supervisor_id_f356f27d
CREATE INDEX "core_placement_supervisor_id_f356f27d" ON "core_placement" ("supervisor_id");

-- index django_admin_log_content_type_id_c4bce8eb
CREATE INDEX "django_admin_log_content_type_id_c4bce8eb" ON "django_admin_log" ("content_type_id");

-- index django_admin_log_user_id_c564eba6
CREATE INDEX "django_admin_log_user_id_c564eba6" ON "django_admin_log" ("user_id");

-- index django_content_type_app_label_model_76bd3d3b_uniq
CREATE UNIQUE INDEX "django_content_type_app_label_model_76bd3d3b_uniq" ON "django_content_type" ("app_label", "model");

-- index django_session_expire_date_a5c62663
CREATE INDEX "django_session_expire_date_a5c62663" ON "django_session" ("expire_date");

-- index logs_dailyl_student_86e10c_idx
CREATE INDEX "logs_dailyl_student_86e10c_idx" ON "logs_dailylog" ("student_id", "status");

-- index logs_dailylog_student_id_c36b1f48
CREATE INDEX "logs_dailylog_student_id_c36b1f48" ON "logs_dailylog" ("student_id");

-- index logs_dailylog_supervisor_id_89cfb23d
CREATE INDEX "logs_dailylog_supervisor_id_89cfb23d" ON "logs_dailylog" ("supervisor_id");

-- index notificatio_recipie_4e3567_idx
CREATE INDEX "notificatio_recipie_4e3567_idx" ON "notifications_notification" ("recipient_id", "is_read");

-- index notifications_notification_recipient_id_d055f3f0
CREATE INDEX "notifications_notification_recipient_id_d055f3f0" ON "notifications_notification" ("recipient_id");

-- index projects_studentproject_supervisor_id_f0fedd11
CREATE INDEX "projects_studentproject_supervisor_id_f0fedd11" ON "projects_studentproject" ("supervisor_id");

-- index reports_wee_student_3bf186_idx
CREATE INDEX "reports_wee_student_3bf186_idx" ON "reports_weeklyreport" ("student_id", "status");

-- index reports_weeklyreport_student_id_e20e3672
CREATE INDEX "reports_weeklyreport_student_id_e20e3672" ON "reports_weeklyreport" ("student_id");

-- index reports_weeklyreport_supervisor_id_1761beda
CREATE INDEX "reports_weeklyreport_supervisor_id_1761beda" ON "reports_weeklyreport" ("supervisor_id");

-- index students_skill_related_activity_id_a91a7afb
CREATE INDEX "students_skill_related_activity_id_a91a7afb" ON "students_skill" ("related_activity_id");

-- index students_skill_student_id_bbd3f745
CREATE INDEX "students_skill_student_id_bbd3f745" ON "students_skill" ("student_id");
