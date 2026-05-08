/* ═══════════════════════════════════════════════════════════
   Control Board — Dashboard JavaScript
   ═══════════════════════════════════════════════════════════ */

const POLL_INTERVAL = 1000; // ms

function deriveHealthLabel(info) {
  if (typeof info.health === "string" && info.health.trim()) {
    return info.health.toUpperCase();
  }

  if (typeof info.operating_state === "string" && info.operating_state.trim() && info.operating_state.toUpperCase() !== "RUNNING") {
    return info.operating_state.toUpperCase();
  }

  if (info.stopping_required) return "ANOMALY";

  const issues = Array.isArray(info.issues) ? info.issues : [];
  if (issues.length > 0) return "ANOMALY";

  if ((info.switch_state || "").toUpperCase() === "OFF") return "IDLE";

  return "HEALTHY";
}

// ── Status polling ────────────────────────────────────────

async function fetchStatus() {
  try {
    const res = await fetch("/api/status");
    if (!res.ok) throw new Error(res.statusText);
    const data = await res.json();
    updateCards(data);
    setBadge("connected", "Live");
  } catch (err) {
    console.error("Status fetch failed:", err);
    setBadge("disconnected", "Offline");
  }
}

function setBadge(state, text) {
  const badge = document.getElementById("connection-badge");
  if (!badge) return;
  badge.textContent = text;
  badge.classList.toggle("connected", state === "connected");
}

function updateCards(data) {
  for (const [machineId, info] of Object.entries(data)) {
    updateCard(machineId, info);
  }
}

function updateCard(mid, info) {
  const healthEl = document.getElementById(`health-${mid}`);
  if (healthEl) {
    const health = deriveHealthLabel(info);
    healthEl.textContent = health || "OFFLINE";
    healthEl.className = "health-badge";
    if (health === "HEALTHY") healthEl.classList.add("health-healthy");
    else if (health === "ANOMALY") healthEl.classList.add("health-anomaly");
    else healthEl.classList.add("health-unknown");
  }

  // Sensor values
  setVal(`temp-${mid}`, info.temperature, 1);
  setVal(`vib-${mid}`, info.vibration, 3);
  setVal(`curr-${mid}`, info.current, 2);

  // Anomaly bar
  const prob = info.anomaly_prob;
  const anomalyVal = document.getElementById(`anomaly-val-${mid}`);
  const anomalyBar = document.getElementById(`anomaly-bar-${mid}`);
  if (anomalyVal && anomalyBar) {
    if (prob != null && prob !== undefined) {
      const pct = Math.min(Math.max(prob * 100, 0), 100);
      anomalyVal.textContent = pct.toFixed(1) + "%";
      anomalyBar.style.width = pct + "%";
      anomalyBar.className = "anomaly-bar-fill";
      if (pct >= 85) anomalyBar.classList.add("crit");
      else if (pct >= 55) anomalyBar.classList.add("warn");

      // Color the anomaly value text
      anomalyVal.style.color = pct >= 85 ? "var(--accent-red)"
                             : pct >= 55 ? "var(--accent-amber)"
                             : "var(--accent-green)";
    } else {
      anomalyVal.textContent = "—";
      anomalyBar.style.width = "0%";
    }
  }

  // Issues
  const issuesSection = document.getElementById(`issues-${mid}`);
  const issuesList = document.getElementById(`issues-list-${mid}`);
  if (issuesSection && issuesList) {
    const issues = Array.isArray(info.issues) ? [...info.issues] : [];
    if (info.pending_stop_confirmation) issues.push("PENDING_CONFIRMATION");
    if (info.stopping_required) issues.push("STOPPING_REQD");
    if (issues.length > 0) {
      issuesSection.style.visibility = "visible";
      issuesList.textContent = " " + issues.join(", ");
    } else {
      issuesSection.style.visibility= "hidden";
    }
  }

  // Switch state
  const switchEl = document.getElementById(`switch-${mid}`);
  if (switchEl) {
    const state = (info.switch_state || "").toUpperCase();
    switchEl.textContent = state || "—";
    switchEl.className = "switch-value";
    if (state === "ON") switchEl.classList.add("on");
    else if (state === "OFF") switchEl.classList.add("off");
  }

  // Highlight active button
  const btnOn = document.getElementById(`btn-on-${mid}`);
  const btnOff = document.getElementById(`btn-off-${mid}`);
  const state = (info.switch_state || "").toUpperCase();
  if (btnOn) btnOn.classList.toggle("active", state === "ON");
  if (btnOff) btnOff.classList.toggle("active", state === "OFF");
}

function setVal(id, value, decimals) {
  const el = document.getElementById(id);
  if (!el) return;
  el.textContent = value != null ? Number(value).toFixed(decimals) : "—";
}

// ── Machine Control ───────────────────────────────────────

async function sendCommand(machineId, action) {
  try {
    const res = await fetch("/api/control", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ machine_id: machineId, action }),
    });
    const data = await res.json();

    if (res.ok) {
      showToast(`${machineId} → ${action} signal sent`, "success");
      // Immediately update the UI optimistically
      const switchEl = document.getElementById(`switch-${machineId}`);
      if (switchEl) {
        switchEl.textContent = action;
        switchEl.className = "switch-value " + action.toLowerCase();
      }
    } else {
      showToast(data.error || "Command failed", "error");
    }
  } catch (err) {
    showToast("Network error: " + err.message, "error");
  }
}

// ── Admin Panel ───────────────────────────────────────────

function toggleAdminPanel() {
  const overlay = document.getElementById("admin-overlay");
  if (!overlay) return;

  const visible = overlay.style.display !== "none";
  overlay.style.display = visible ? "none" : "flex";

  if (!visible) loadUsers();
}

async function loadUsers() {
  try {
    const res = await fetch("/api/admin/users");
    if (!res.ok) return;
    const users = await res.json();

    const list = document.getElementById("user-list");
    if (!list) return;

    list.innerHTML = users.map(u => `
      <div class="user-row">
        <div class="user-row-info">
          <span class="user-row-name">${esc(u.username)} <span style="color:var(--text-dim);font-size:.75rem">(${esc(u.role)})</span></span>
          <span class="user-row-meta">Machines: ${u.machines.length ? u.machines.map(esc).join(", ") : "none"}</span>
        </div>
        <button class="btn btn-delete btn-sm" onclick="deleteUser(${u.id}, '${esc(u.username)}')">Remove</button>
      </div>
    `).join("");
  } catch (err) {
    console.error("Failed to load users:", err);
  }
}

async function addUser(e) {
  e.preventDefault();
  const username = document.getElementById("new-username").value.trim();
  const password = document.getElementById("new-password").value;
  const role = document.getElementById("new-role").value;
  const machinesRaw = document.getElementById("new-machines").value.trim();
  const machines = machinesRaw ? machinesRaw.split(",").map(s => s.trim()).filter(Boolean) : [];

  try {
    const res = await fetch("/api/admin/users", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ username, password, role, machines }),
    });
    const data = await res.json();

    if (res.ok) {
      showToast(`User "${username}" created`, "success");
      document.getElementById("add-user-form").reset();
      loadUsers();
    } else {
      showToast(data.error || "Failed to create user", "error");
    }
  } catch (err) {
    showToast("Network error", "error");
  }
}

async function deleteUser(userId, username) {
  if (!confirm(`Remove user "${username}"?`)) return;

  try {
    const res = await fetch(`/api/admin/users/${userId}`, { method: "DELETE" });
    if (res.ok) {
      showToast(`User "${username}" removed`, "success");
      loadUsers();
    } else {
      showToast("Failed to remove user", "error");
    }
  } catch (err) {
    showToast("Network error", "error");
  }
}

// ── Toast Notifications ───────────────────────────────────

function showToast(message, type = "info") {
  const container = document.getElementById("toast-container");
  if (!container) return;

  const toast = document.createElement("div");
  toast.className = `toast toast-${type}`;
  toast.textContent = message;
  container.appendChild(toast);

  setTimeout(() => {
    toast.style.opacity = "0";
    toast.style.transform = "translateY(8px)";
    toast.style.transition = ".3s ease";
    setTimeout(() => toast.remove(), 300);
  }, 3500);
}

// ── Utilities ─────────────────────────────────────────────

function esc(str) {
  const div = document.createElement("div");
  div.textContent = str;
  return div.innerHTML;
}

// ── Init ──────────────────────────────────────────────────

fetchStatus();
setInterval(fetchStatus, POLL_INTERVAL);
