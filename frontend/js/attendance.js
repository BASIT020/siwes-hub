/* ==========================================================================
   SIWES Hub - attendance.js
   Attendance page:
     student    -> own records + live summary (read-only)
     supervisor -> record attendance for assigned students, correct records
     admin      -> record for any student, overview of the whole programme
   ========================================================================== */

let attendanceState = { page: 1, user: null, role: null, students: [] };

async function initAttendancePage() {
  attendanceState.user = await initAppShell({ page: "attendance", title: "Attendance" });
  if (!attendanceState.user) return;
  attendanceState.role = attendanceState.user.role;
  const user = attendanceState.user;

  // Only supervisors/admins can record attendance (also enforced server-side).
  document.getElementById("recordAttendanceBtn").style.display =
    attendanceState.role === "student" ? "none" : "";
  document.getElementById("recordAttendanceBtn").addEventListener("click", openAttendanceForm);
  // The per-student filter only makes sense for supervisors/admins.
  if (attendanceState.role !== "student") {
    document.getElementById("attendanceStudentFilter").style.display = "";
  }

  // Populate filters + load summary/table.
  if (attendanceState.role !== "student") {
    const students = await apiGetList("/students/?page_size=200");
    attendanceState.students = students;
    const studentSelect = document.getElementById("attendanceStudentFilter");
    const formSelect = document.getElementById("attStudent");
    students.forEach((student) => {
      const label = `${student.full_name} (${student.matric_number})`;
      if (studentSelect) {
        const option = document.createElement("option");
        option.value = student.id;
        option.textContent = label;
        studentSelect.appendChild(option);
      }
      if (formSelect) {
        const option = document.createElement("option");
        option.value = student.id;
        option.textContent = label;
        formSelect.appendChild(option);
      }
    });
  }

  ["attendanceStatusFilter", "attendanceDateFilter", "attendanceStudentFilter"].forEach((id) => {
    const el = document.getElementById(id);
    if (el) el.addEventListener("change", () => { attendanceState.page = 1; renderAttendance(); });
  });

  renderAttendanceSummary();
  renderAttendance();
}

async function renderAttendanceSummary() {
  const root = document.getElementById("attendanceSummary");
  const role = attendanceState.role;
  let path = "/attendance/summary/";
  if (role === "supervisor") {
    const selected = document.getElementById("attendanceStudentFilter");
    // Default the summary to the first assigned student until one is picked.
    const studentId = selected && selected.value ? selected.value : (attendanceState.students[0]?.id ?? "");
    path += `?student=${studentId}`;
  }
  const response = await api.get(path, { showErrors: false });
  if (!response.ok) {
    root.innerHTML = "";
    return;
  }
  const s = response.data;
  root.innerHTML = `
    <div class="stat-grid mb-2">
      ${statCard("calendar-check", s.attendance_rate + "%", "Attendance rate", "green")}
      ${statCard("check-circle-2", s.present, "Present days", "purple")}
      ${statCard("clock", s.late, "Late days", "orange")}
      ${statCard("x-circle", s.absent, "Absent days", "red")}
      ${statCard("shield-check", s.excused, "Excused days", "blue")}
    </div>`;
  refreshIcons();
}

async function renderAttendance() {
  const listRoot = document.getElementById("attendanceList");
  listRoot.innerHTML = loadingBlock();

  const params = new URLSearchParams();
  params.set("page", attendanceState.page);
  params.set("page_size", 15);
  const status = document.getElementById("attendanceStatusFilter").value;
  if (status) params.set("status", status);
  const date = document.getElementById("attendanceDateFilter").value;
  if (date) params.set("date", date);
  const student = document.getElementById("attendanceStudentFilter");
  if (student && student.value) params.set("student", student.value);

  const response = await api.getPaged(`/attendance/?${params.toString()}`);
  renderPager(document.getElementById("attendancePager"), response, (newPage) => {
    attendanceState.page = newPage;
    renderAttendance();
  });

  if (!response.results.length) {
    const emptyMessage =
      attendanceState.role === "student"
        ? "No attendance records yet. Your supervisor records your daily attendance."
        : "No attendance records match this filter.";
    listRoot.innerHTML = emptyState(emptyMessage, "calendar-check");
    return;
  }

  listRoot.innerHTML = `
    <div class="table-wrap">
      <table class="data-table">
        <thead>
          <tr><th>Date</th>${attendanceState.role !== "student" ? "<th>Student</th>" : ""}<th>Status</th><th>Note</th><th>Recorded by</th><th>Verified by</th><th></th></tr>
        </thead>
        <tbody>
          ${response.results.map((row) => `
            <tr>
              <td>${formatDate(row.date)}</td>
              ${attendanceState.role !== "student" ? `<td><strong>${escapeHtml(row.student_name)}</strong><br><span class="muted small">${escapeHtml(row.matric_number)}</span></td>` : ""}
              <td>${statusBadge(row.status)}</td>
              <td>${escapeHtml(row.note || "-")}</td>
              <td>${escapeHtml(row.recorded_by_name || "-")}</td>
              <td>${escapeHtml(row.verified_by_name || "-")}</td>
              <td class="flex flex-wrap">
                ${(attendanceState.role === "supervisor" || attendanceState.role === "admin")
                  ? `<button class="btn btn-outline btn-sm" data-edit="${row.id}"><i data-lucide="pencil"></i>Correct</button>`
                  : ""}
              </td>
            </tr>`).join("")}
        </tbody>
      </table>
    </div>`;
  refreshIcons();

  listRoot.querySelectorAll("[data-edit]").forEach((btn) =>
    btn.addEventListener("click", () => openAttendanceCorrection(
      response.results.find((row) => row.id === Number(btn.dataset.edit)))));
}

/** Supervisor/admin: record new attendance. */
function openAttendanceForm() {
  const today = new Date().toISOString().slice(0, 10);
  const modal = openModal("Record attendance", `
    <form id="attendanceForm" class="form-grid">
      <div class="field">
        <label for="attStudent">Student *</label>
        <select id="attStudent" name="student" required></select>
        <p class="hint">Only students assigned to you can be selected (administrators: everyone).</p>
      </div>
      <div class="field">
        <label for="attDate">Date *</label>
        <input type="date" id="attDate" name="date" value="${today}" max="${today}" required>
        <p class="hint">One record per student per day; no future dates.</p>
      </div>
      <div class="field full">
        <label for="attStatus">Status *</label>
        <select id="attStatus" name="status" required>
          <option value="present">Present</option>
          <option value="late">Late</option>
          <option value="absent">Absent</option>
          <option value="excused">Excused</option>
        </select>
      </div>
      <div class="field full">
        <label for="attNote">Note (optional)</label>
        <input type="text" id="attNote" name="note" placeholder="e.g. reported 1 hour late">
      </div>
    </form>
    <div class="modal-actions" style="margin-top:1rem">
      <button class="btn btn-ghost" data-cancel>Cancel</button>
      <button class="btn btn-primary" id="attSave"><i data-lucide="save"></i>Save record</button>
    </div>`);

  // Clone the pre-filled student options into the modal select.
  const source = document.getElementById("attendanceStudentFilter");
  const target = modal.querySelector("#attStudent");
  if (source && attendanceState.students.length) {
    attendanceState.students.forEach((student) => {
      const option = document.createElement("option");
      option.value = student.id;
      option.textContent = `${student.full_name} (${student.matric_number})`;
      target.appendChild(option);
    });
  }
  modal.querySelector("[data-cancel]").addEventListener("click", closeModal);
  modal.querySelector("#attSave").addEventListener("click", async () => {
    const form = modal.querySelector("#attendanceForm");
    const payload = {
      student: Number(form.student.value),
      date: form.date.value,
      status: form.status.value,
      note: form.note.value.trim(),
    };
    if (!payload.student) return toast("Choose a student.", "error");
    if (!payload.date) return toast("Pick a date.", "error");

    const response = await api.post("/attendance/", payload, { showErrors: false });
    if (!response.ok) {
      applyFieldErrors(form, response.data);
      if (response.data?.detail) toast(response.data.detail, "error");
      return;
    }
    closeModal();
    toast("Attendance recorded. The student has been notified.", "success");
    attendanceState.page = 1;
    renderAttendanceSummary();
    renderAttendance();
  });
}

/** Supervisor/admin: correct an existing record's status/note. */
function openAttendanceCorrection(record) {
  if (!record) return;
  const modal = openModal(`Correct attendance - ${escapeHtml(record.student_name)}`, `
    <div class="form-note"><strong>Date:</strong> ${formatDate(record.date)} · currently ${escapeHtml(record.status)}</div>
    <form id="attCorrectForm" class="form-grid">
      <div class="field">
        <label for="corrStatus">Status</label>
        <select id="corrStatus" name="status">
          ${["present", "late", "absent", "excused"].map((value) =>
            `<option value="${value}" ${value === record.status ? "selected" : ""}>${value}</option>`).join("")}
        </select>
      </div>
      <div class="field">
        <label for="corrNote">Note</label>
        <input type="text" id="corrNote" name="note" value="${escapeHtml(record.note || "")}">
      </div>
    </form>
    <div class="modal-actions" style="margin-top:1rem">
      <button class="btn btn-ghost" data-cancel>Cancel</button>
      <button class="btn btn-primary" id="corrSave"><i data-lucide="save"></i>Save correction</button>
    </div>`);
  modal.querySelector("[data-cancel]").addEventListener("click", closeModal);
  modal.querySelector("#corrSave").addEventListener("click", async () => {
    const form = modal.querySelector("#attCorrectForm");
    const response = await api.patch(`/attendance/${record.id}/`, {
      status: form.status.value,
      note: form.note.value.trim(),
    }, { showErrors: false });
    if (!response.ok) {
      applyFieldErrors(form, response.data);
      return;
    }
    closeModal();
    toast("Attendance corrected.", "success");
    renderAttendance();
  });
}
