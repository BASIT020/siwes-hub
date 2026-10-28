/* ==========================================================================
   SIWES Hub - ui.js
   Reusable interface helpers: modals, confirm dialogs, empty states and
   simple pagination controls. Used by the page scripts.
   ========================================================================== */

/** Open a modal. `title` text, `bodyHtml` string, returns modal element. */
function openModal(title, bodyHtml, { wide = false } = {}) {
  closeModal();
  const overlay = document.createElement("div");
  overlay.className = "modal-overlay";
  overlay.innerHTML = `
    <div class="modal ${wide ? "modal-wide" : ""}">
      <h3><i data-lucide="square-pen"></i>${escapeHtml(title)}</h3>
      <div class="modal-body">${bodyHtml}</div>
      <div class="modal-actions">
        <button class="btn btn-ghost" data-close>Cancel</button>
      </div>
    </div>`;
  if (!overlay.querySelector(".modal .modal-actions [data-action]")) {
    // bodyHtml may define its own action buttons; keep Cancel only.
  }
  document.body.appendChild(overlay);
  overlay.addEventListener("mousedown", (event) => {
    if (event.target === overlay) closeModal();
  });
  overlay.querySelector("[data-close]").addEventListener("click", closeModal);
  refreshIcons();
  return overlay.querySelector(".modal");
}

/** Close any open modal. */
function closeModal() {
  document.querySelectorAll(".modal-overlay").forEach((overlay) => overlay.remove());
}

/**
 * Confirmation dialog (used before destructive actions).
 * Returns Promise<boolean>.
 */
function confirmDialog(message, { okLabel = "Yes, continue", danger = false } = {}) {
  return new Promise((resolve) => {
    const modal = document.createElement("div");
    modal.className = "modal-overlay";
    modal.innerHTML = `
      <div class="modal" style="width:min(430px, 96%)">
        <h3><i data-lucide="triangle-alert"></i>Are you sure?</h3>
        <div class="modal-body muted">${escapeHtml(message)}</div>
        <div class="modal-actions">
          <button class="btn btn-ghost" data-no>Cancel</button>
          <button class="btn ${danger ? "btn-danger" : "btn-primary"}" data-yes>${escapeHtml(okLabel)}</button>
        </div>
      </div>`;
    document.body.appendChild(modal);
    modal.querySelector("[data-no]").addEventListener("click", () => { modal.remove(); resolve(false); });
    modal.querySelector("[data-yes]").addEventListener("click", () => { modal.remove(); resolve(true); });
    modal.addEventListener("mousedown", (event) => {
      if (event.target === modal) { modal.remove(); resolve(false); }
    });
    refreshIcons();
  });
}

/** Empty-state block for lists and tables. */
function emptyState(message, icon = "inbox") {
  return `
    <div class="empty-state">
      <i data-lucide="${icon}"></i>
      <p>${escapeHtml(message)}</p>
    </div>`;
}

/** Loading block. */
function loadingBlock() {
  return `<div class="spinner"></div>`;
}

/**
 * Simple pager under a table. calls `onPage(newPage)`.
 * `pageState` is {page, pages, count}.
 */
function renderPager(container, pageState, onPage) {
  if (!pageState || !pageState.pages || pageState.pages <= 1) {
    container.innerHTML = pageState && pageState.count ? `<div class="pagination">${pageState.count} record(s)</div>` : "";
    return;
  }
  container.innerHTML = `
    <div class="pagination">
      <button id="pagePrev" ${pageState.page <= 1 ? "disabled" : ""}>&#8592; Prev</button>
      <span>Page ${pageState.page} of ${pageState.pages} (${pageState.count} records)</span>
      <button id="pageNext" ${pageState.page >= pageState.pages ? "disabled" : ""}>Next &#8594;</button>
    </div>`;
  const prev = container.querySelector("#pagePrev");
  const next = container.querySelector("#pageNext");
  if (prev) prev.addEventListener("click", () => onPage(pageState.page - 1));
  if (next) next.addEventListener("click", () => onPage(pageState.page + 1));
}

/** Perform a form PATCH/POST and surface DRF field errors under inputs. */
function applyFieldErrors(form, data) {  form.querySelectorAll(".field-error").forEach((el) => el.remove());
  form.querySelectorAll(".invalid").forEach((el) => el.classList.remove("invalid"));
  if (!data || typeof data !== "object") return;
  for (const [field, messages] of Object.entries(data)) {
    const input = form.querySelector(`[name="${field}"]`);
    if (input) {
      input.classList.add("invalid");
      const errorLine = document.createElement("div");
      errorLine.className = "field-error";
      errorLine.textContent = Array.isArray(messages) ? messages.join(". ") : String(messages);
      input.closest(".field").appendChild(errorLine);
    }
  }
}

/** One metric card (shared by dashboards and page summaries). */
function statCard(icon, value, label, tone = "purple") {
  return `
    <div class="stat-card">
      <span class="icon-chip ${tone === "purple" ? "" : tone}"><i data-lucide="${icon}"></i></span>
      <span>
        <span class="stat-num">${escapeHtml(String(value ?? 0))}</span><br>
        <span class="stat-label">${escapeHtml(label)}</span>
      </span>
    </div>`;
}
