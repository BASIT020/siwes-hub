/* ==========================================================================
   SIWES Hub - profile.js
   Profile page:
     student    -> edit contact/academic details + manage learned skills
     supervisor -> own institutional details (read-only)
     admin      -> account details (read-only; edits happen via settings)
   ========================================================================== */

let profileState = { role: null, skills: [] };

async function initProfilePage() {
  const user = await initAppShell({ page: "profile", title: "My Profile" });
  if (!user) return;
  profileState.role = user.role;

  const isStudent = user.role === "student";
  document.getElementById("accountCard").style.display = isStudent ? "" : "none";
  document.getElementById("skillsSection").style.display = isStudent ? "" : "none";
  document.getElementById("editableFields").style.display = isStudent ? "" : "none";
  document.getElementById("readOnlyFields").style.display = isStudent ? "none" : "";

  await loadProfile();
  if (isStudent) {
    await loadSkills();
    document.getElementById("newSkillBtn").addEventListener("click", () => openSkillForm());
  }
}

async function loadProfile() {
  const root = document.getElementById("profileRoot");
  const response = await api.get(profileState.role === "student" ? "/students/me/" : "/auth/me/", { showErrors: false });
  if (!response.ok) {
    root.innerHTML = emptyState("Could not load your profile.", "triangle-alert");
    return;
  }
  const data = response.data;

  if (profileState.role === "student") {
    document.getElementById("pfFullName").textContent = data.full_name || "-";
    document.getElementById("pfMatric").textContent = data.matric_number || "-";
    document.getElementById("pfEmail").textContent = data.email || "-";
    document.getElementById("pfDepartment").value = data.department || "";
    document.getElementById("pfFaculty").value = data.faculty || "";
    document.getElementById("pfLevel").value = data.level || "";
    document.getElementById("pfPhone").value = data.phone || "";
    document.getElementById("pfStart").value = data.training_start_date || "";
    document.getElementById("pfEnd").value = data.training_end_date || "";
    document.getElementById("pfOrg").textContent = data.organization_name || "Not assigned yet";
    document.getElementById("pfSupervisor").textContent = data.supervisor_name || "Not assigned yet";
  } else if (profileState.role === "supervisor" && window.APP.user?.supervisor_id) {
    const supervisorId = window.APP.user.supervisor_id;
    const detail = await api.get(`/supervisors/${supervisorId}/`, { showErrors: false });
    const supervisor = detail.ok ? detail.data : data;
    document.getElementById("roName").textContent = supervisor.full_name || "-";
    document.getElementById("roUsername").textContent = "@" + (supervisor.username || "-");
    document.getElementById("roEmail").textContent = supervisor.email || "-";
    document.getElementById("roRole").textContent = roleLabel(supervisor.role || "supervisor");
    document.getElementById("roDetails").innerHTML = `
      <tr><th style="width:150px">Title</th><td>${escapeHtml(supervisor.title || "-")}</td></tr>
      <tr><th>Staff ID</th><td>${escapeHtml(supervisor.staff_id || "-")}</td></tr>
      <tr><th>Department</th><td>${escapeHtml(supervisor.department || "-")}</td></tr>
      <tr><th>Assigned students</th><td>${supervisor.assigned_students}</td></tr>`;
  } else {
    document.getElementById("roRole").textContent = "Administrator";
    document.getElementById("roName").textContent = data.full_name || "-";
    document.getElementById("roUsername").textContent = "@" + (data.username || "-");
    document.getElementById("roEmail").textContent = data.email || "-";
    document.getElementById("roDetails").innerHTML = `
      <tr><th style="width:150px">Role</th><td>Administrator</td></tr>`;
  }
  refreshIcons();
}

async function saveProfile() {
  const form = document.getElementById("profileForm");
  const payload = {
    department: form.department.value.trim(),
    faculty: form.faculty.value.trim(),
    level: form.level.value,
    phone: form.phone.value.trim(),
  };
  const payload2 = {
    ...payload,
    training_start_date: form.training_start_date.value || null,
    training_end_date: form.training_end_date.value || null,
  };
  const response = await api.patch("/students/me/", payload2, { showErrors: false });
  if (!response.ok) {
    applyFieldErrors(form, response.data);
    return;
  }
  toast("Profile saved.", "success");
  loadProfile();
}

/* ------------------------------------------------------------------ */
/* Skills (students)                                                    */
/* ------------------------------------------------------------------ */
async function loadSkills() {
  const listRoot = document.getElementById("skillsList");
  listRoot.innerHTML = loadingBlock();
  profileState.skills = await apiGetList("/students/skills/");

  if (!profileState.skills.length) {
    listRoot.innerHTML = emptyState("No skills recorded yet. Add the ones you learned during training.", "sparkles");
    return;
  }

  listRoot.innerHTML = `
    <div class="table-wrap">
      <table class="data-table">
        <thead><tr><th>Skill</th><th>Proficiency</th><th>Learned</th><th>Related activity</th><th></th></tr></thead>
        <tbody>
          ${profileState.skills.map((skill) => `
            <tr>
              <td><strong>${escapeHtml(skill.name)}</strong>${skill.description ? `<br><span class="muted small">${escapeHtml(skill.description)}</span>` : ""}</td>
              <td class="muted small">${escapeHtml(skill.proficiency_level || "-")}</td>
              <td>${formatDate(skill.date_learned)}</td>
              <td class="muted small">${escapeHtml(skill.related_activity || "-")}</td>
              <td class="flex flex-wrap">
                <button class="btn btn-outline btn-sm" data-skill-edit="${skill.id}"><i data-lucide="pencil"></i></button>
                <button class="btn btn-ghost btn-sm" data-skill-delete="${skill.id}"><i data-lucide="trash-2"></i></button>
              </td>
            </tr>`).join("")}
        </tbody>
      </table>
    </div>`;
  refreshIcons();

  const byId = new Map(profileState.skills.map((skill) => [skill.id, skill]));
  listRoot.querySelectorAll("[data-skill-edit]").forEach((btn) =>
    btn.addEventListener("click", () => openSkillForm(byId.get(Number(btn.dataset.skillEdit)))));
  listRoot.querySelectorAll("[data-skill-delete]").forEach((btn) =>
    btn.addEventListener("click", async () => {
      const skill = byId.get(Number(btn.dataset.skillDelete));
      if (await confirmDialog(`Remove "${skill.name}" from your skills?`, { danger: true, okLabel: "Remove" })) {
        const response = await api.del(`/students/skills/${skill.id}/`);
        if (response.ok) {
          toast("Skill removed.", "success");
          loadSkills();
        }
      }
    }));
}

function openSkillForm(existing) {
  const isEdit = Boolean(existing);
  const modal = openModal(isEdit ? `Edit skill - ${escapeHtml(existing.name)}` : "Add skill", `
    <form id="skillForm" class="form-grid">
      <div class="field full">
        <label for="skillName">Skill name *</label>
        <input type="text" id="skillName" name="name" value="${escapeHtml(existing?.name || "")}" required placeholder="e.g. Git version control">
      </div>
      <div class="field">
        <label for="skillProficiency">Proficiency</label>
        <select id="skillProficiency" name="proficiency_level">
          ${["beginner", "intermediate", "advanced"].map((level) =>
            `<option value="${level}" ${existing?.proficiency_level === level ? "selected" : ""}>${level}</option>`).join("")}
        </select>
      </div>
      <div class="field">
        <label for="skillDate">Date learned</label>
        <input type="date" id="skillDate" name="date_learned" value="${existing?.date_learned || new Date().toISOString().slice(0, 10)}">
      </div>
      <div class="field full">
        <label for="skillDescription">Description</label>
        <input type="text" id="skillDescription" name="description" value="${escapeHtml(existing?.description || "")}" placeholder="Short description of what you can do now">
      </div>
      <div class="field full">
        <label for="skillActivity">Related activity</label>
        <input type="text" id="skillActivity" name="related_activity" value="${escapeHtml(existing?.related_activity || "")}" placeholder="e.g. Built during daily log #12">
      </div>
    </form>
    <div class="modal-actions" style="margin-top:1rem">
      <button class="btn btn-ghost" data-cancel>Cancel</button>
      <button class="btn btn-primary" id="skillSave"><i data-lucide="save"></i>${isEdit ? "Save changes" : "Add skill"}</button>
    </div>`);

  modal.querySelector("[data-cancel]").addEventListener("click", closeModal);
  modal.querySelector("#skillSave").addEventListener("click", async () => {
    const form = modal.querySelector("#skillForm");
    const payload = {
      name: form.name.value.trim(),
      proficiency_level: form.proficiency_level.value,
      date_learned: form.date_learned.value || null,
      description: form.description.value.trim(),
      related_activity: form.related_activity.value.trim(),
    };
    if (!payload.name) return toast("Skill name is required.", "error");

    const response = isEdit
      ? await api.patch(`/students/skills/${existing.id}/`, payload, { showErrors: false })
      : await api.post("/students/skills/", payload, { showErrors: false });
    if (!response.ok) {
      applyFieldErrors(form, response.data);
      if (response.data?.detail) toast(response.data.detail, "error");
      return;
    }
    closeModal();
    toast(isEdit ? "Skill updated." : "Skill added.", "success");
    loadSkills();
  });
}
