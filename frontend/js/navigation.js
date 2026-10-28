/* ==========================================================================
   SIWES Hub - navigation.js
   Builds the application shell (sidebar, topbar, user chip, notification
   bell) for every authenticated page and enforces the current role.

   Usage: on each dashboard sub-page include this file then call:
       initAppShell({ page: "student-dashboard" });
   `page` is the filename stem the sidebar highlights.
   ========================================================================== */

const NAV_LINKS = {
  student: [
    { section: "Overview" },
    { page: "student-dashboard", label: "Dashboard", icon: "layout-dashboard", href: "/pages/student-dashboard.html" },
    { section: "Training records" },
    { page: "daily-logs", label: "Daily Logs", icon: "book-open-text", href: "/pages/daily-logs.html" },
    { page: "weekly-reports", label: "Weekly Reports", icon: "calendar-days", href: "/pages/weekly-reports.html" },
    { page: "attendance", label: "Attendance", icon: "calendar-check", href: "/pages/attendance.html" },
    { page: "projects", label: "My Project", icon: "folder-git-2", href: "/pages/projects.html" },
    { section: "Other" },
    { page: "announcements", label: "Announcements", icon: "megaphone", href: "/pages/announcements.html" },
    { page: "profile", label: "Profile", icon: "user-round", href: "/pages/profile.html" },
    { page: "settings", label: "Settings", icon: "settings", href: "/pages/settings.html" },
  ],
  supervisor: [
    { section: "Overview" },
    { page: "supervisor-dashboard", label: "Dashboard", icon: "layout-dashboard", href: "/pages/supervisor-dashboard.html" },
    { section: "Monitoring" },
    { page: "students", label: "My Students", icon: "users-round", href: "/pages/students.html" },
    { page: "daily-logs", label: "Daily Logs", icon: "book-open-text", href: "/pages/daily-logs.html" },
    { page: "weekly-reports", label: "Weekly Reports", icon: "calendar-days", href: "/pages/weekly-reports.html" },
    { page: "attendance", label: "Attendance", icon: "calendar-check", href: "/pages/attendance.html" },
    { page: "projects", label: "Projects", icon: "folder-git-2", href: "/pages/projects.html" },
    { section: "Other" },
    { page: "announcements", label: "Announcements", icon: "megaphone", href: "/pages/announcements.html" },
    { page: "profile", label: "Profile", icon: "user-round", href: "/pages/profile.html" },
    { page: "settings", label: "Settings", icon: "settings", href: "/pages/settings.html" },
  ],
  admin: [
    { section: "Overview" },
    { page: "admin-dashboard", label: "Dashboard", icon: "layout-dashboard", href: "/pages/admin-dashboard.html" },
    { section: "People" },
    { page: "students", label: "Students", icon: "graduation-cap", href: "/pages/students.html" },
    { page: "supervisors", label: "Supervisors", icon: "users-round", href: "/pages/supervisors.html" },
    { page: "organizations", label: "Organizations", icon: "building-2", href: "/pages/organizations.html" },
    { section: "Monitoring" },
    { page: "daily-logs", label: "Daily Logs", icon: "book-open-text", href: "/pages/daily-logs.html" },
    { page: "weekly-reports", label: "Weekly Reports", icon: "calendar-days", href: "/pages/weekly-reports.html" },
    { page: "attendance", label: "Attendance", icon: "calendar-check", href: "/pages/attendance.html" },
    { page: "projects", label: "Projects", icon: "folder-git-2", href: "/pages/projects.html" },
    { section: "Programme" },
    { page: "announcements", label: "Announcements", icon: "megaphone", href: "/pages/announcements.html" },
    { page: "profile", label: "Profile", icon: "user-round", href: "/pages/profile.html" },
    { page: "settings", label: "Settings", icon: "settings", href: "/pages/settings.html" },
  ],
};

function initials(name) {
  return String(name || "?")
    .split(" ")
    .filter(Boolean)
    .slice(0, 2)
    .map((part) => part[0].toUpperCase())
    .join("");
}

function roleLabel(role) {
  return { student: "Student", supervisor: "Supervisor", admin: "Administrator" }[role] || role;
}

function sidebarHtml(user, currentPage) {
  const links = NAV_LINKS[user.role] || [];
  return links
    .map((link) => {
      if (link.section) return `<div class="nav-section">${escapeHtml(link.section)}</div>`;
      const active = link.page === currentPage ? "active" : "";
      return `<a class="nav-link ${active}" href="${link.href}"><i data-lucide="${link.icon}"></i>${escapeHtml(link.label)}</a>`;
    })
    .join("");
}

function topbarHtml(user, title) {
  return `
    <button class="menu-toggle" id="menuToggle" aria-label="Toggle menu"><i data-lucide="menu"></i></button>
    <h1>${escapeHtml(title)}</h1>
    <button class="bell" id="notifBell" aria-label="Notifications">
      <i data-lucide="bell"></i><span class="dot" id="notifDot" style="display:none"></span>
    </button>
    <button class="user-chip" id="userChip" title="Account">
      <span class="avatar">${escapeHtml(initials(user.full_name))}</span>
      <span>
        <span class="name">${escapeHtml(user.full_name || user.username)}</span><br>
        <span class="role">${escapeHtml(roleLabel(user.role))}</span>
      </span>
    </button>
    <div class="notif-panel" id="notifPanel" style="display:none; position:fixed;"></div>`;
}

/**
 * Build sidebar + topbar; returns the user (or redirects when wrong role).
 * Requires the page to have: #sidebar, #topbar containers.
 */
async function initAppShell(options) {
  const user = await requireRole(...(options.roles || ["student", "supervisor", "admin"]));
  if (!user) return null;

  const sidebar = document.getElementById("sidebar");
  const topbar = document.getElementById("topbar");
  if (sidebar) {
    sidebar.innerHTML = `
      <a class="brand" href="${dashboardPathForRole(user.role)}">
        <span class="logo-icon"><i data-lucide="graduation-cap"></i></span>
        <span class="name">SIWES Hub</span>
      </a>
      <nav>${sidebarHtml(user, options.page)}</nav>
      <div class="sidebar-footer">SIWES Management &amp; Monitoring Portal</div>`;
  }
  if (topbar) {
    topbar.innerHTML = topbarHtml(user, options.title || "SIWES Hub");
    topbar.style.position = "relative";

    document.getElementById("menuToggle").addEventListener("click", () => {
      document.body.classList.toggle("sidebar-open");
    });
    document.getElementById("userChip").addEventListener("click", () => {
      window.location.href = "/pages/settings.html";
    });
    initNotificationBell();
  }
  refreshIcons();
  return user;
}

/** Close any open modal via Escape. */
document.addEventListener("keydown", (event) => {
  if (event.key === "Escape") closeModal();
});
