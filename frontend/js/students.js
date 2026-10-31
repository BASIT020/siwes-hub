/* ==========================================================================
   SIWES Hub - students.js
   Students page:
     admin      -> register, edit, deactivate; assign/change placements
     supervisor -> read-only list of assigned students + per-student overview
   Students only ever see themselves in this list (server-enforced) so the
   page is not linked on the student menu.
   ========================================================================== */

let studentsState = { page: 1, user: null, role: null, organizations: [], supervisors: [], sessions: [] };

async function initStudentsPage() {
  studentsState.user = await initAppShell({ page: "students", title: "Students" });
  if (!studentsState.user) return;
  studentsState.role = studentsState.user.role;

  document.getElementById("newStudentBtn").style.display = studentsState.role === "admin" ? "" : "none";
  document.getElementById("newStudentBtn").addEventListener("click", () => openStudentForm());

  ["studentsSearch", "studentsDepartment", "studentsLevel", "studentsActiveFilter"].forEach((id) => {
    const el = document.getElementById(id);
    if (!el) return;
    el.addEventListener(el.tagName.toLowerCase() === "input" ? "input" : "change", () => {
      clearTimeout(studentsState._searchTimer);
      studentsState._searchTimer = setTimeout(() => { studentsState.page = 1; renderStudents(); }, 250);
    });
  });

  if (studentsState.role === "admin") {
    // Reference data for the placement modal.
    apiGetList("/organizations/?page_size=200").then((orgs) => { studentsState.organizations = orgs; });
    apiGetList("/supervisors/?page_size=200").then((supervisors) => { studentsState.supervisors = supervisors; });
    apiGetList("/core/sessions/?page_size=100").then((sessions) => { studentsState.sessions = sessions; });
  }

  renderStudents();

  // Deep link from a dashboard card: open the student's detail modal.
  const params = new URLSearchParams(window.location.search);
  if (params.get("student")) {
    const response = await api.get(`/students/${params.get("student")}/`, { showErrors: false });
    if (response.ok) showStudentDetail(response.data);
  }
}

async function renderStudents() {
  const listRoot = document.getElementById("studentsList");
  listRoot.innerHTML = loadingBlock();

  const params = new URLSearchParams();
  params.set("page", studentsState.page);
  params.set("page_size", 12);
  const search = document.getElementById("studentsSearch")?.value;
  if (search) params.set("search", search);
  const department = document.getElementById("studentsDepartment")?.value;
  if (department) params.set("department", department);
  const level = document.getElementById("studentsLevel")?.value;
  if (level) params.set("level", level);
  const active = document.getElementById("studentsActiveFilter")?.value;
  if (active) params.set("is_active", active);

  const response = await api.getPaged(`/students/?${params.toString()}`);
  renderPager(document.getElementById("studentsPager"), response, (newPage) => {
    studentsState.page = newPage;
    renderStudents();
  });

  if (!response.results.length) {
    listRoot.innerHTML = emptyState(
      studentsState.role === "admin" ? "No students match this filter." : "You have no assigned students yet.",
      "graduation-cap");
    return;
  }

  listRoot.innerHTML = `
    <div class="table-wrap">
      <table class="data-table">
        <thead><tr><th>Student</th><th>Matric No</th><th>Department</th><th>Level</th><th>Organization</th><th>Supervisor</th><th>Status</th><th></th></tr></thead>
        <tbody>
          ${response.results.map((student) => `
            <tr>
              <td><strong>${escapeHtml(student.full_name)}</strong><br><span class="muted small">${escapeHtml(student.email || "")}</span></td>
              <td>${escapeHtml(student.matric_number)}</td>
              <td>${escapeHtml(student.department || "-")}</td>
              <td>${escapeHtml(student.level || "-")}</td>
              <td class="muted small">${escapeHtml(student.organization_name || "-")}</td>
              <td class="muted small">${escapeHtml(student.supervisor_name || "-")}</td>
              <td>${statusBadge(student.is_active ? "active" : "inactive")}</td>
              <td class="flex flex-wrap">
                <button class="btn btn-ghost btn-sm" data-view="${student.id}"><i data-lucide="eye"></i>View</button>
                ${studentsState.role === "admin" ? `
                  <button class="btn btn-outline btn-sm" data-edit="${student.id}"><i data-lucide="pencil"></i>Edit</button>
                  <button class="btn btn-ghost btn-sm" data-place="${student.id}"><i data-lucide="briefcase"></i>Placement</button>
                  <button class="btn btn-ghost btn-sm" data-deactivate="${student.id}"><i data-lucide="user-x"></i></button>` : ""}
              </td>
            </tr>`).join("")}
        </tbody>
      </table>
    </div>`;
  refreshIcons();

  const byId = new Map(response.results.map((student) => [student.id, student]));
  listRoot.querySelectorAll("[data-view]").forEach((btn) =>
    btn.addEventListener("click", () => showStudentDetail(byId.get(Number(btn.dataset.view)))));
  listRoot.querySelectorAll("[data-edit]").forEach((btn) =>
    btn.addEventListener("click", () => openStudentForm(byId.get(Number(btn.dataset.edit)))));
  listRoot.querySelectorAll("[data-place]").forEach((btn) =>
    btn.addEventListener("click", () => openPlacementForm(byId.get(Number(btn.dataset.place)))));
  listRoot.querySelectorAll("[data-deactivate]").forEach((btn) =>
    btn.addEventListener("click", async () => {
      const student = byId.get(Number(btn.dataset.deactivate));
      if (await confirmDialog(`Deactivate ${student.full_name}? Their history (logs, reports...) is kept but they can no longer sign in.`, { danger: true, okLabel: "Deactivate" })) {
        const response = await api.del(`/students/${student.id}/`);
        if (response.ok) {
          toast("Student deactivated.", "success");
          renderStudents();
        }
      }
    }));
}

/** Read-only student overview: profile + attendance summary + recent logs. */
async function showStudentDetail(student) {
  if (!student) return;
  openModal(`Student - ${escapeHtml(student.full_name)}`, `
    <div class="spinner"></div>`, { wide: true });
  const modal = document.querySelector(".modal-overlay .modal");

  const [logsResponse, summaryResponse] = await Promise.all([
    api.getPaged(`/logs/?student=${student.id}&page_size=5`),
    api.get(`/attendance/summary/?student=${student.id}`, { showErrors: false }),
  ]);

  modal.querySelector(".modal-body").innerHTML = `
    <table class="data-table">
      <tbody>
        <tr><th style="width:140px">Matric No</th><td>${escapeHtml(student.matric_number)}</td></tr>
        <tr><th>Department</th><td>${escapeHtml(student.department || "-")} · ${escapeHtml(student.faculty || "-")}</td></tr>
        <tr><th>Level</th><td>${escapeHtml(student.level || "-")}</td></tr>
        <tr><th>Status</th><td>${statusBadge(student.is_active ? "active" : "inactive")}</td></tr>
        <tr><th>Organization</th><td>${escapeHtml(student.organization_name || "-")}</td></tr>
        <tr><th>Supervisor</th><td>${escapeHtml(student.supervisor_name || "-")}</td></tr>
        <tr><th>Training</th><td>${formatDate(student.training_start_date)} to ${formatDate(student.training_end_date)}</td></tr>
      </tbody>
    </table>
    <div class="card-title mt-2"><i data-lucide="calendar-check"></i>Attendance summary</div>
    ${summaryResponse.ok
      ? `<p class="small mb-0">${summaryResponse.data.attendance_rate}% attendance - ${summaryResponse.data.present} present, ${summaryResponse.data.late} late, ${summaryResponse.data.absent} absent of ${summaryResponse.data.total_days} days.</p>`
      : `<p class="muted small">No attendance data.</p>`}
    <div class="card-title mt-2"><i data-lucide="book-open-text"></i>Most recent daily logs</div>
    ${logsResponse.results.length
      ? logsResponse.results.map((log) => `
          <div class="list-row">
            <div><div class="small"><strong>${formatDate(log.log_date)}</strong> ${statusBadge(log.status)}</div>
            <div class="muted small">${escapeHtml((log.activities || "").slice(0, 110))}</div></div>
          </div>`).join("")
      : `<p class="muted small">No daily logs recorded yet.</p>`}`;
  refreshIcons();
}

/** Admin: register / edit a student. */
function openStudentForm(existing) {
  const isEdit = Boolean(existing);
  const modal = openModal(isEdit ? `Edit student - ${escapeHtml(existing.full_name)}` : "Register student", `
    <form id="studentForm" class="form-grid">
      ${isEdit ? "" : `
      <div class="field">
        <label for="stuUsername">Username *</label>
        <input type="text" id="stuUsername" name="username" required>
      </div>
      <div class="field">
        <label for="stuPassword">Temporary password *</label>
        <input type="text" id="stuPassword" name="password" required>
        <p class="hint">At least 6 characters. Share it privately with the student.</p>
      </div>`}
      <div class="field">
        <label for="stuFullName">Full name *</label>
        <input type="text" id="stuFullName" name="full_name" value="${escapeHtml(existing?.full_name || "")}" required>
      </div>
      <div class="field">
        <label for="stuMatric">Matric number *</label>
        <input type="text" id="stuMatric" name="matric_number" value="${escapeHtml(existing?.matric_number || "")}" required>
      </div>
      <div class="field">
        <label for="stuEmail">Email</label>
        <input type="email" id="stuEmail" name="email" value="${escapeHtml(existing?.email || "")}">
      </div>
      <div class="field">
        <label for="stuPhone">Phone</label>
        <input type="tel" id="stuPhone" name="phone" value="${escapeHtml(existing?.phone || "")}">
      </div>
      <div class="field">
        <label for="stuDepartment">Department</label>
        <input type="text" id="stuDepartment" name="department" value="${escapeHtml(existing?.department || "")}" placeholder="e.g. Computer Science">
      </div>
      <div class="field">
        <label for="stuFaculty">Faculty</label>
        <input type="text" id="stuFaculty" name="faculty" value="${escapeHtml(existing?.faculty || "")}" placeholder="e.g. Engineering">
      </div>
      <div class="field">
        <label for="stuLevel">Level</label>
        <select id="stuLevel" name="level">
          <option value="">--</option>
          ${["100", "200", "300", "400", "500"].map((l) => `<option value="${l}" ${existing?.level === l ? "selected" : ""}>${l} level</option>`).join("")}
          <option value="other" ${existing?.level === "other" ? "selected" : ""}>Other</option>
        </select>
      </div>
      <div class="field">
        <label for="stuStart">Training start</label>
        <input type="date" id="stuStart" name="training_start_date" value="${existing?.training_start_date || ""}">
      </div>
      <div class="field">
        <label for="stuEnd">Training end</label>
        <input type="date" id="stuEnd" name="training_end_date" value="${existing?.training_end_date || ""}">
      </div>
    </form>
    <div class="modal-actions" style="margin-top:1rem">
      <button class="btn btn-ghost" data-cancel>Cancel</button>
      <button class="btn btn-primary" id="studentSave"><i data-lucide="save"></i>${isEdit ? "Save changes" : "Register student"}</button>
    </div>`);

  modal.querySelector("[data-cancel]").addEventListener("click", closeModal);
  modal.querySelector("#studentSave").addEventListener("click", async () => {
    const form = modal.querySelector("#studentForm");
    let payload;
    if (isEdit) {
      payload = {
        full_name: form.full_name.value.trim(),
        matric_number: form.matric_number.value.trim(),
        email: form.email.value.trim(),
        phone: form.phone.value.trim(),
        department: form.department.value.trim(),
        faculty: form.faculty.value.trim(),
        level: form.level.value,
        training_start_date: form.training_start_date.value || null,
        training_end_date: form.training_end_date.value || null,
      };
    } else {
      payload = {
        username: form.username.value.trim(),
        password: form.password.value,
        full_name: form.full_name.value.trim(),
        matric_number: form.matric_number.value.trim(),
        email: form.email.value.trim(),
        phone: form.phone.value.trim(),
        department: form.department.value.trim(),
        faculty: form.faculty.value.trim(),
        level: form.level.value,
        training_start_date: form.training_start_date.value || null,
        training_end_date: form.training_end_date.value || null,
      };
    }
    if (!payload.full_name) return toast("Full name is required.", "error");
    if (!payload.matric_number) return toast("Matric number is required.", "error");

    const response = isEdit
      ? await api.patch(`/students/${existing.id}/`, payload, { showErrors: false })
      : await api.post("/students/", payload, { showErrors: false });
    if (!response.ok) {
      applyFieldErrors(form, response.data);
      if (response.data?.detail) toast(response.data.detail, "error");
      return;
    }
    closeModal();
    toast(isEdit ? "Student updated." : "Student registered. Assign their placement next.", "success");
    studentsState.page = 1;
    renderStudents();
  });
}

/** Admin: assign / change the student's placement (org + supervisor + session). */
async function openPlacementForm(student) {
  await Promise.all([
    studentsState.organizations.length ? null : apiGetList("/organizations/?page_size=200").then((o) => { studentsState.organizations = o; }),
    studentsState.supervisors.length ? null : apiGetList("/supervisors/?page_size=200").then((s) => { studentsState.supervisors = s; }),
    studentsState.sessions.length ? null : apiGetList("/core/sessions/?page_size=100").then((s) => { studentsState.sessions = s; }),
  ]);
  // Find the student's existing placement (if any) to pre-fill.
  const placements = await apiGetList("/core/placements/?page_size=500");
  const existing = placements.find((p) => p.student === student.id);

  const modal = openModal(`Placement - ${escapeHtml(student.full_name)}`, `
    <form id="placementForm" class="form-grid">
      <div class="field full">
        <label for="plcOrg">Organization *</label>
        <select id="plcOrg" name="organization" required>
          <option value="">--</option>
          ${studentsState.organizations.map((org) =>
            `<option value="${org.id}" ${org.id === existing?.organization ? "selected" : ""}>${escapeHtml(org.name)}</option>`).join("")}
        </select>
      </div>
      <div class="field">
        <label for="plcSupervisor">Supervisor *</label>
        <select id="plcSupervisor" name="supervisor" required>
          <option value="">--</option>
          ${studentsState.supervisors
            .filter((s) => s.id === existing?.supervisor || s.status === "approved")
            .map((supervisor) => {
              const label = supervisor.id === existing?.supervisor && supervisor.status !== "approved"
                ? `${supervisor.full_name} (currently assigned)`
                : supervisor.full_name;
              return `<option value="${supervisor.id}" ${supervisor.id === existing?.supervisor ? "selected" : ""}>${escapeHtml(label)}</option>`;
            }).join("")}
        </select>
        <p class="hint">Only approved supervisors can be selected.</p>
      </div>
      <div class="field">
        <label for="plcSession">SIWES session *</label>
        <select id="plcSession" name="siwes_session" required>
          <option value="">--</option>
          ${studentsState.sessions.map((session) =>
            `<option value="${session.id}" ${session.id === existing?.siwes_session ? "selected" : ""}>${escapeHtml(session.name)}</option>`).join("")}
        </select>
      </div>
      <div class="field">
        <label for="plcStart">Start date *</label>
        <input type="date" id="plcStart" name="start_date" value="${existing?.start_date || student.training_start_date || ""}" required>
      </div>
      <div class="field">
        <label for="plcEnd">End date *</label>
        <input type="date" id="plcEnd" name="end_date" value="${existing?.end_date || student.training_end_date || ""}" required>
      </div>
      <div class="field full">
        <label for="plcRemarks">Remarks</label>
        <input type="text" id="plcRemarks" name="remarks" value="${escapeHtml(existing?.remarks || "")}">
      </div>
      ${existing ? `<div class="full form-note">This student already has a placement - saving updates it.</div>` : ""}
    </form>
    <div class="modal-actions" style="margin-top:1rem">
      <button class="btn btn-ghost" data-cancel>Cancel</button>
      <button class="btn btn-primary" id="plcSave"><i data-lucide="save"></i>${existing ? "Update placement" : "Assign placement"}</button>
    </div>`);

  modal.querySelector("[data-cancel]").addEventListener("click", closeModal);
  modal.querySelector("#plcSave").addEventListener("click", async () => {
    const form = modal.querySelector("#placementForm");
    const payload = {
      student: student.id,
      organization: Number(form.organization.value) || null,
      supervisor: Number(form.supervisor.value) || null,
      siwes_session: Number(form.siwes_session.value) || null,
      start_date: form.start_date.value,
      end_date: form.end_date.value,
      remarks: form.remarks.value.trim(),
    };
    if (!payload.organization) return toast("Choose an organization.", "error");
    if (!payload.supervisor) return toast("Choose a supervisor.", "error");
    if (!payload.siwes_session) return toast("Choose a SIWES session.", "error");

    const response = existing
      ? await api.patch(`/core/placements/${existing.id}/`, payload, { showErrors: false })
      : await api.post("/core/placements/", payload, { showErrors: false });
    if (!response.ok) {
      applyFieldErrors(form, response.data);
      if (response.data?.detail) toast(response.data.detail, "error");
      return;
    }
    closeModal();
    toast(existing ? "Placement updated." : "Placement assigned. The student can log in and start.", "success");
    renderStudents();
  });
}
