/* ==========================================================================
   SIWES Hub - auth.js
   Current-user handling shared by every page that needs to know who is
   signed in. The server is always the source of truth (GET /api/auth/me/).
   ========================================================================== */

/** Fetch (and cache for this page load) the signed-in user, or null. */
async function getCurrentUser() {
  if (window.APP.user !== undefined) return window.APP.user;
  const response = await api.get("/auth/me/", { showErrors: false });
  window.APP.user = response.ok ? response.data : null;
  return window.APP.user;
}

/** Home page for a role. */
function dashboardPathForRole(role) {
  return {
    student: "/pages/student-dashboard.html",
    supervisor: "/pages/supervisor-dashboard.html",
    admin: "/pages/admin-dashboard.html",
  }[role] || "/pages/landing.html";
}

/**
 * Guard for app pages: require a signed-in user with one of `allowedRoles`.
 * Wrong role -> sent to their own dashboard; not signed in -> login page.
 */
async function requireRole(...allowedRoles) {
  const user = await getCurrentUser();
  if (!user) {
    window.location.href = "/pages/login.html";
    return null;
  }
  if (!allowedRoles.includes(user.role)) {
    window.location.href = dashboardPathForRole(user.role);
    return null;
  }
  return user;
}

/** Log out and return to the login page. */
async function logoutAndRedirect() {
  await api.post("/auth/logout/");
  window.location.href = "/pages/login.html";
}

/* ------------------------------------------------------------------ */
/* Login page logic (only runs on login.html)                           */
/* ------------------------------------------------------------------ */
async function initLoginPage() {
  const user = await getCurrentUser();
  if (user) {
    window.location.href = dashboardPathForRole(user.role);
    return;
  }

  const form = document.getElementById("loginForm");
  const errorBox = document.getElementById("loginError");
  const submitButton = form.querySelector("button[type=submit]");

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    errorBox.style.display = "none";
    const username = form.username.value.trim();
    const password = form.password.value;

    // Small client-side validation, real validation happens server-side.
    let problem = "";
    if (!username) problem = "Please enter your username or email.";
    else if (!password) problem = "Please enter your password.";
    if (problem) {
      errorBox.querySelector("span").textContent = problem;
      errorBox.style.display = "flex";
      return;
    }

    submitButton.disabled = true;
    const response = await api.post("/auth/login/", { username, password });
    submitButton.disabled = false;

    if (!response.ok) {
      errorBox.querySelector("span").textContent =
        (response.data && response.data.detail) || "Login failed. Try again.";
      errorBox.style.display = "flex";
      return;
    }
    window.location.href = dashboardPathForRole(response.data.role);
  });
}
