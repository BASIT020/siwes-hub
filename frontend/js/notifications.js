/* ==========================================================================
   SIWES Hub - notifications.js
   Topbar bell + dropdown listing the signed-in user's notifications.
   ========================================================================== */

/** Load unread count into the bell. */
async function refreshNotificationBell() {
  const dot = document.getElementById("notifDot");
  if (!dot) return;
  // Paginate (page_size=1) just to get `count` = the full unread total.
  const response = await api.get("/notifications/?unread=true&page=1&page_size=1", { showErrors: false });
  if (!response.ok) return;
  const data = response.data;
  const unread = typeof data.count === "number"
    ? data.count
    : (Array.isArray(data) ? data.filter((n) => !n.is_read).length : 0);
  if (unread > 0) {
    dot.style.display = "inline-flex";
    dot.textContent = unread > 99 ? "99+" : unread;
  } else {
    dot.style.display = "none";
  }
}

/** Open the notification panel content. */
async function buildNotificationPanel(panel) {
  panel.innerHTML = `<div class="spinner"></div>`;
  const response = await api.get("/notifications/?limit=15", { showErrors: false });
  if (!response.ok) {
    panel.innerHTML = `<div class="empty-state"><p>Could not load notifications.</p></div>`;
    return;
  }
  const data = response.data;
  const items = Array.isArray(data) ? data : (data.results || []);
  if (!items.length) {
    panel.innerHTML = `<div class="empty-state"><i data-lucide="bell-off"></i><p>No notifications yet.</p></div>`;
    refreshIcons();
    return;
  }
  const html = items
    .map(
      (n) => `
      <div class="notif-item ${n.is_read ? "" : "unread"}">
        <div class="title">${escapeHtml(n.title)}</div>
        <div class="muted small">${escapeHtml(n.body || "")}</div>
        <div class="when">${formatDateTime(n.created_at)}</div>
      </div>`
    )
    .join("");
  const footer = `
    <div style="padding:0.6rem 1rem; border-top:1px solid var(--border); text-align:center;">
      <button class="btn btn-ghost btn-sm" id="markAllRead">Mark all as read</button>
    </div>`;
  panel.innerHTML = html + footer;
  refreshIcons();
  panel.querySelector("#markAllRead").addEventListener("click", async () => {
    await api.post("/notifications/read-all/");
    refreshNotificationBell();
    buildNotificationPanel(panel);
  });
  // Clicking an unread item marks it read.
  panel.querySelectorAll(".notif-item.unread").forEach((item, index) => {
    item.style.cursor = "pointer";
    item.addEventListener("click", () => {
      api.post(`/notifications/${items[index].id}/read/`).then(refreshNotificationBell);
      item.classList.remove("unread");
    });
  });
}

/** Wire the topbar bell (called by navigation.js after the topbar exists). */
function initNotificationBell() {
  const bell = document.getElementById("notifBell");
  const panel = document.getElementById("notifPanel");
  if (!bell || !panel) return;

  bell.addEventListener("click", async (event) => {
    event.stopPropagation();
    const isOpen = panel.style.display === "block";
    if (isOpen) {
      panel.style.display = "none";
      return;
    }
    panel.style.display = "block";
    await buildNotificationPanel(panel);
  });
  document.addEventListener("click", (event) => {
    if (!panel.contains(event.target)) panel.style.display = "none";
  });
  refreshNotificationBell();
}
