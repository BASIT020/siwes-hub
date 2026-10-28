/* ==========================================================================
   SIWES Hub - register.js
   Self-registration page (public):

   * STUDENT accounts are active immediately and the browser is signed in
     straight away, so the new student lands on their dashboard.
   * SUPERVISOR accounts stay pending until an administrator approves them
     on the Supervisors page; the API never starts a session for them.

   All validation that matters happens on the server; the checks here only
   give quick feedback before a request is sent.
   ========================================================================== */

const REGISTER_ENDPOINTS = {
  student: "/auth/register/student/",
  supervisor: "/auth/register/supervisor/",
};

async function initRegisterPage() {
  // Already signed in? There is nothing to register - go to the dashboard.
  const user = await getCurrentUser();
  if (user) {
    window.location.href = dashboardPathForRole(user.role);
    return;
  }

  if (window.lucide && window.lucide.createIcons) window.lucide.createIcons();

  const toggleStudent = document.getElementById("typeStudent");
  const toggleSupervisor = document.getElementById("typeSupervisor");
  const studentForm = document.getElementById("registerStudentForm");
  const supervisorForm = document.getElementById("registerSupervisorForm");

  function showForm(role) {
    const isStudent = role === "student";
    toggleStudent.classList.toggle("active", isStudent);
    toggleSupervisor.classList.toggle("active", !isStudent);
    studentForm.style.display = isStudent ? "" : "none";
    supervisorForm.style.display = isStudent ? "none" : "";
  }

  toggleStudent.addEventListener("click", () => showForm("student"));
  toggleSupervisor.addEventListener("click", () => showForm("supervisor"));

  studentForm.addEventListener("submit", (event) => {
    event.preventDefault();
    submitRegistration("student", studentForm);
  });
  supervisorForm.addEventListener("submit", (event) => {
    event.preventDefault();
    submitRegistration("supervisor", supervisorForm);
  });
}

/** Small client-side check, then send the form to its endpoint. */
function submitRegistration(role, form) {
  const errorBox = role === "student"
    ? document.getElementById("registerErrorStudent")
    : document.getElementById("registerErrorSupervisor");
  const submitButton = form.querySelector("button[type=submit]");

  errorBox.style.display = "none";
  form.querySelectorAll(".invalid").forEach((el) => el.classList.remove("invalid"));
  form.querySelectorAll(".field-error").forEach((el) => el.remove());

  // Frontend validation: required fields, email shape, password rules.
  const required = [...form.querySelectorAll("[required]")];
  const missing = required.filter((input) => !input.value.trim());
  if (missing.length) {
    applyFieldErrors(
      form,
      Object.fromEntries(missing.map((input) => [input.name, ["This field is required."]]))
    );
    showErrorBox(errorBox, "Please fill in the required fields (marked with *).");
    return;
  }

  const email = form.querySelector('[name="email"]').value.trim();
  if (!/^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(email)) {
    applyFieldErrors(form, { email: ["Enter a valid email address."] });
    return;
  }

  const password = form.querySelector('[name="password"]').value;
  const password2 = form.querySelector('[name="password2"]').value;
  if (password.length < 6) {
    applyFieldErrors(form, { password: ["Password must be at least 6 characters."] });
    return;
  }
  if (password !== password2) {
    applyFieldErrors(form, { password2: ["The two passwords do not match."] });
    return;
  }

  if (role === "student") {
    const matric = form.querySelector('[name="matric_number"]').value.trim();
    if (!/^[A-Za-z0-9/\-.]+$/.test(matric)) {
      applyFieldErrors(form, {
        matric_number: ["Use letters, digits, slashes, dots and hyphens only."],
      });
      return;
    }
  } else {
    const username = form.querySelector('[name="username"]').value.trim();
    if (username.length < 3) {
      applyFieldErrors(form, { username: ["Username must be at least 3 characters."] });
      return;
    }
  }

  // Build the payload with the exact field names the API expects.
  const payload = {};
  new FormData(form).forEach((value, key) => { payload[key] = value; });

  submitButton.disabled = true;
  api.post(REGISTER_ENDPOINTS[role], payload, { showErrors: false }).then((response) => {
    submitButton.disabled = false;
    if (!response.ok) {
      applyFieldErrors(form, response.data);
      const detail = response.data && typeof response.data.detail === "string"
        ? response.data.detail
        : null;
      if (detail) showErrorBox(errorBox, detail);
      else if (!response.data || !Object.keys(response.data).some((k) => k !== "detail")) {
        showErrorBox(errorBox, "Registration failed. Please check the form and try again.");
      }
      return;
    }
    if (role === "student" && response.status === 201 && response.data.role === "student") {
      // The API already signed the browser in.
      window.location.href = dashboardPathForRole("student");
      return;
    }
    showSuccessPanel(role, response.data);
  });
}

/** Swap the form column for the appropriate success message. */
function showSuccessPanel(role, data) {
  document.getElementById("registerStage").style.display = "none";
  const panel = document.getElementById("registerSuccess");
  const body = document.getElementById("successBody");
  const action = document.getElementById("successAction");

  if (role === "student") {
    document.getElementById("successTitle").textContent = "Welcome to SIWES Hub";
    body.textContent = "Your student account is ready. You are already signed in - continue to your dashboard to start your logbook.";
    action.textContent = "Go to my dashboard";
    action.href = "/pages/student-dashboard.html";
  } else {
    document.getElementById("successTitle").textContent = "Registration received";
    const username = data && data.username ? ` (${data.username})` : "";
    body.textContent =
      `Your supervisor account${username} was created but needs administrator approval. ` +
      "The SIWES office has been notified. You will be able to sign in once your account is approved.";
    action.textContent = "Back to sign in";
    action.href = "/pages/login.html";
  }
  panel.style.display = "";
  if (window.lucide && window.lucide.createIcons) window.lucide.createIcons();
}

function showErrorBox(errorBox, message) {
  errorBox.querySelector("span").textContent = message;
  errorBox.style.display = "flex";
}
