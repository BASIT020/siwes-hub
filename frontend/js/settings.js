/* ==========================================================================
   SIWES Hub - settings.js
   Settings page:
     - account summary (live from the server)
     - change password (validated by Django's password rules, server-side)
     - sign out everywhere on this device
   ========================================================================== */

async function initSettingsPage() {
  const user = await initAppShell({ page: "settings", title: "Settings" });
  if (!user) return;

  // Fill the read-only account summary.
  document.getElementById("setFullName").textContent = user.full_name || "-";
  document.getElementById("setUsername").textContent = "@" + (user.username || "-");
  document.getElementById("setEmail").textContent = user.email || "-";
  document.getElementById("setPhone").textContent = user.phone || "-";
  document.getElementById("setRole").textContent = roleLabel(user.role);

  // Profile details form (username / full name / email).
  const profileForm = document.getElementById("profileForm");
  const profileError = document.getElementById("profileError");
  profileForm.full_name.value = user.full_name || "";
  profileForm.username.value = user.username || "";
  profileForm.email.value = user.email || "";

  profileForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    profileError.style.display = "none";

    const fullName = profileForm.full_name.value.trim();
    const username = profileForm.username.value.trim();
    const email = profileForm.email.value.trim();
    if (!fullName) return showProfileError("Enter your full name.");
    if (username.length < 3) return showProfileError("Your username must be at least 3 characters.");
    if (email && !email.includes("@")) return showProfileError("Enter a valid email address.");

    const response = await api.patch("/auth/me/", {
      full_name: fullName,
      username: username,
      email: email,
    }, { showErrors: false });
    if (!response.ok) {
      const errors = response.data || {};
      const detail = errors.detail
        || (errors.username && errors.username.join(". "))
        || (errors.full_name && errors.full_name.join(". "))
        || (errors.email && errors.email.join(". "))
        || "Could not save the profile.";
      showProfileError(detail);
      return;
    }

    const updated = response.data;
    document.getElementById("setFullName").textContent = updated.full_name || "-";
    document.getElementById("setUsername").textContent = "@" + (updated.username || "-");
    document.getElementById("setEmail").textContent = updated.email || "-";
    const chip = document.getElementById("userChip");
    if (chip) {
      const avatar = chip.querySelector(".avatar");
      const name = chip.querySelector(".name");
      if (avatar) avatar.textContent = initials(updated.full_name || updated.username);
      if (name) name.textContent = updated.full_name || updated.username;
    }
    toast("Profile saved.", "success");
  });

  function showProfileError(message) {
    profileError.querySelector("span").textContent = message;
    profileError.style.display = "flex";
  }

  // Change password form.
  const form = document.getElementById("passwordForm");
  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    const errorBox = document.getElementById("passwordError");
    errorBox.style.display = "none";

    const current = form.current_password.value;
    const next = form.new_password.value;
    const confirm = form.confirm_password.value;

    if (!current) { showPasswordError("Enter your current password."); return; }
    if (next.length < 6) { showPasswordError("The new password must be at least 6 characters."); return; }
    if (next !== confirm) { showPasswordError("The two new passwords do not match."); return; }

    const response = await api.post("/auth/change-password/", {
      current_password: current,
      new_password: next,
    }, { showErrors: false });
    if (!response.ok) {
      const detail = response.data?.detail
        || (response.data?.new_password && response.data.new_password.join(". "))
        || "Could not change the password.";
      showPasswordError(detail);
      return;
    }
    form.reset();
    toast("Password changed. Use it next time you sign in.", "success");
  });

  document.getElementById("signOutBtn").addEventListener("click", async () => {
    if (await confirmDialog("Sign out of SIWES Hub?", { okLabel: "Sign out" })) {
      logoutAndRedirect();
    }
  });

  function showPasswordError(message) {
    const errorBox = document.getElementById("passwordError");
    errorBox.querySelector("span").textContent = message;
    errorBox.style.display = "flex";
  }
}
