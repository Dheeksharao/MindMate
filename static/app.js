// MindMate – Student Well-being & Academic Support (v3.0)
// Fully Database-Driven SPA Client Engine

// In-Memory Token Storage (Strict Security Rule: NO localStorage for sensitive auth tokens)
let authToken = null;
let currentUser = null;
let currentView = "login";
let activeStudentProfileId = null;

let wellbeingChartInstance = null;
let studentChartInstance = null;

// Adaptive Check-In Session State
let activeAdaptiveSessionId = null;
let currentQuestionData = null;
let selectedAdaptiveAnswers = [];
let isClassroomDeviceSession = false;

// ─────────────────────────────────────────────
//  API Fetch Client
// ─────────────────────────────────────────────

async function apiFetch(endpoint, options = {}) {
  const headers = {
    "Content-Type": "application/json",
    ...(options.headers || {})
  };
  if (authToken) {
    headers["Authorization"] = `Bearer ${authToken}`;
  }

  const response = await fetch(endpoint, {
    ...options,
    headers
  });

  if (response.status === 401) {
    logout();
    const errData = await response.json().catch(() => ({}));
    throw new Error(errData.detail || "Authentication required. Please sign in.");
  }

  if (response.status === 403) {
    const errData = await response.json().catch(() => ({}));
    throw new Error(errData.detail || "Access denied.");
  }

  if (!response.ok) {
    const errData = await response.json().catch(() => ({}));
    throw new Error(errData.detail || "An error occurred with your request.");
  }

  return response.json();
}

// ─────────────────────────────────────────────
//  App Initialization
// ─────────────────────────────────────────────

window.addEventListener("DOMContentLoaded", async () => {
  try {
    const setupStatus = await apiFetch("/api/auth/setup-status");
    if (setupStatus.needs_setup) {
      navigate("setup");
      return;
    }
  } catch (err) {
    console.warn("Setup check error:", err);
  }

  navigate("login");
});

// ─────────────────────────────────────────────
//  Navigation Engine
// ─────────────────────────────────────────────

function navigateHome() {
  if (!currentUser) {
    navigate("login");
    return;
  }
  if (currentUser.role === "admin") {
    navigate("admin-dashboard");
  } else if (currentUser.role === "student") {
    navigate("student-portal");
  } else {
    navigate("teacher-dashboard");
  }
}

function navigate(viewName) {
  currentView = viewName;

  const views = [
    "view-setup",
    "view-login",
    "view-admin-dashboard",
    "view-admin-teachers",
    "view-admin-students",
    "view-admin-assignments",
    "view-admin-settings",
    "view-admin-audit",
    "view-teacher-dashboard",
    "view-teacher-students",
    "view-student-profile",
    "view-teacher-alerts",
    "view-student-portal"
  ];
  views.forEach(id => {
    const el = document.getElementById(id);
    if (el) el.style.display = "none";
  });

  document.querySelectorAll(".nav-link").forEach(l => l.classList.remove("active"));
  const navBar = document.getElementById("main-nav");

  if (viewName === "setup") {
    navBar.style.display = "none";
    document.getElementById("view-setup").style.display = "block";
    return;
  }

  if (viewName === "login") {
    navBar.style.display = "none";
    document.getElementById("view-login").style.display = "block";
    return;
  }

  navBar.style.display = "flex";

  // Role Protection check
  if (!currentUser) {
    navigate("login");
    return;
  }

  const targetEl = document.getElementById(`view-${viewName}`);
  if (targetEl) targetEl.style.display = "block";

  // Dispatch data loader based on view
  if (viewName === "admin-dashboard") {
    const link = document.getElementById("nav-admin-dash");
    if (link) link.classList.add("active");
    loadAdminDashboard();
  } else if (viewName === "admin-teachers") {
    const link = document.getElementById("nav-admin-teachers");
    if (link) link.classList.add("active");
    loadAdminTeachers();
  } else if (viewName === "admin-students") {
    const link = document.getElementById("nav-admin-students");
    if (link) link.classList.add("active");
    loadAdminStudents();
  } else if (viewName === "admin-assignments") {
    const link = document.getElementById("nav-admin-assignments");
    if (link) link.classList.add("active");
    loadAdminAssignmentsView();
  } else if (viewName === "admin-settings") {
    const link = document.getElementById("nav-admin-settings");
    if (link) link.classList.add("active");
    loadAdminSettingsView();
  } else if (viewName === "admin-audit") {
    const link = document.getElementById("nav-admin-audit");
    if (link) link.classList.add("active");
    loadAuditLogs();
  } else if (viewName === "teacher-dashboard") {
    const link = document.getElementById("nav-teacher-dash");
    if (link) link.classList.add("active");
    loadTeacherDashboard();
  } else if (viewName === "teacher-students") {
    const link = document.getElementById("nav-teacher-students");
    if (link) link.classList.add("active");
    loadTeacherStudents();
  } else if (viewName === "teacher-alerts") {
    const link = document.getElementById("nav-teacher-alerts");
    if (link) link.classList.add("active");
    loadTeacherAlerts();
  } else if (viewName === "student-portal") {
    const link = document.getElementById("nav-student-dash");
    if (link) link.classList.add("active");
    loadStudentPortal();
  }
}

function updateNavForUser() {
  document.getElementById("nav-links-admin").style.display = "none";
  document.getElementById("nav-links-teacher").style.display = "none";
  document.getElementById("nav-links-student").style.display = "none";

  if (!currentUser) return;

  const roleDisplay = document.getElementById("user-role-badge");
  const nameDisplay = document.getElementById("user-name-display");
  const iconDisplay = document.getElementById("user-role-icon");
  const subtitleDisplay = document.getElementById("nav-portal-subtitle");

  nameDisplay.textContent = currentUser.full_name || currentUser.username || "User";

  if (currentUser.role === "admin") {
    document.getElementById("nav-links-admin").style.display = "flex";
    roleDisplay.textContent = "Admin";
    roleDisplay.className = "badge badge-neutral";
    iconDisplay.textContent = "⚙️";
    subtitleDisplay.textContent = "Administrator Portal";
  } else if (currentUser.role === "student") {
    document.getElementById("nav-links-student").style.display = "flex";
    roleDisplay.textContent = "Student";
    roleDisplay.className = "badge badge-green";
    iconDisplay.textContent = "🎓";
    subtitleDisplay.textContent = "Student Reflection Space";
  } else {
    document.getElementById("nav-links-teacher").style.display = "flex";
    roleDisplay.textContent = "Teacher";
    roleDisplay.className = "badge badge-primary";
    iconDisplay.textContent = "👩‍🏫";
    subtitleDisplay.textContent = "Educator Portal";
  }
}

// ─────────────────────────────────────────────
//  Authentication Handlers
// ─────────────────────────────────────────────

function selectLoginAction(action) {
  document.getElementById("tab-action-signin").classList.toggle("active", action === "signin");
  document.getElementById("tab-action-create").classList.toggle("active", action === "create");
  document.getElementById("login-signin-panel").style.display = action === "signin" ? "block" : "none";
  document.getElementById("login-create-panel").style.display = action === "create" ? "block" : "none";
}

function openForgotPasswordModal() {
  document.getElementById("forgot-identifier").value = "";
  const message = document.getElementById("forgot-password-message");
  message.style.display = "none";
  document.getElementById("modal-forgot-password").style.display = "flex";
}

function closeForgotPasswordModal() {
  document.getElementById("modal-forgot-password").style.display = "none";
}

async function handleForgotPassword(e) {
  e.preventDefault();
  const identifier = document.getElementById("forgot-identifier").value.trim();
  const message = document.getElementById("forgot-password-message");
  try {
    const res = await apiFetch("/api/auth/forgot-password", {
      method: "POST",
      body: JSON.stringify({ identifier })
    });
    message.className = "alert-box";
    message.textContent = res.message;
    message.style.display = "block";
  } catch (err) {
    message.className = "alert-box alert-urgent";
    message.textContent = err.message;
    message.style.display = "block";
  }
}

function selectLoginPortal(portal) {
  document.getElementById("tab-portal-teacher").classList.remove("active");
  document.getElementById("tab-portal-student").classList.remove("active");
  document.getElementById("tab-portal-admin").classList.remove("active");

  const tabBtn = document.getElementById(`tab-portal-${portal}`);
  if (tabBtn) tabBtn.classList.add("active");

  document.getElementById("login-portal").value = portal;
  const labelEl = document.getElementById("login-identifier-label");
  const inputEl = document.getElementById("login-identifier");
  const hintEl = document.getElementById("login-identifier-hint");
  const submitBtn = document.getElementById("login-submit-btn");
  const errorBox = document.getElementById("login-error");
  errorBox.style.display = "none";

  if (portal === "student") {
    labelEl.textContent = "Student Username";
    inputEl.placeholder = "e.g. maya9a";
    hintEl.style.display = "block";
    submitBtn.textContent = "Sign In as Student →";
  } else if (portal === "admin") {
    labelEl.textContent = "Administrator Email Address";
    inputEl.placeholder = "admin@school.edu";
    hintEl.style.display = "none";
    submitBtn.textContent = "Sign In as Administrator →";
  } else {
    labelEl.textContent = "Educator Email Address";
    inputEl.placeholder = "teacher@school.edu";
    hintEl.style.display = "none";
    submitBtn.textContent = "Sign In as Educator →";
  }
}

async function handleLogin(e) {
  e.preventDefault();
  const errorBox = document.getElementById("login-error");
  errorBox.style.display = "none";

  const portal = document.getElementById("login-portal").value;
  const identifier = document.getElementById("login-identifier").value.trim();
  const password = document.getElementById("login-password").value;

  try {
    const res = await apiFetch("/api/auth/login", {
      method: "POST",
      body: JSON.stringify({ identifier, password, portal })
    });

    authToken = res.access_token;
    currentUser = res.user;

    document.getElementById("login-password").value = "";
    updateNavForUser();

    // Check if mandatory password change is required
    if (currentUser.must_change_password) {
      document.getElementById("modal-force-change-password").style.display = "flex";
      return;
    }

    navigateHome();
  } catch (err) {
    errorBox.textContent = err.message;
    errorBox.style.display = "block";
  }
}

async function handleForceChangePassword(e) {
  e.preventDefault();
  const newPwd = document.getElementById("force-new-password").value;
  const confirmPwd = document.getElementById("force-confirm-password").value;
  const errBox = document.getElementById("force-password-error");
  errBox.style.display = "none";

  if (newPwd !== confirmPwd) {
    errBox.textContent = "New passwords do not match.";
    errBox.style.display = "block";
    return;
  }

  try {
    await apiFetch("/api/auth/force-change-password", {
      method: "POST",
      body: JSON.stringify({ new_password: newPwd })
    });
    document.getElementById("modal-force-change-password").style.display = "none";
    currentUser.must_change_password = 0;
    navigateHome();
  } catch (err) {
    errBox.textContent = err.message;
    errBox.style.display = "block";
  }
}

function logout() {
  authToken = null;
  currentUser = null;
  activeAdaptiveSessionId = null;
  currentQuestionData = null;
  document.getElementById("login-identifier").value = "";
  document.getElementById("login-password").value = "";
  navigate("login");
}

function openChangePasswordModal() {
  document.getElementById("change-current-password").value = "";
  document.getElementById("change-new-password").value = "";
  document.getElementById("change-password-error").style.display = "none";
  document.getElementById("modal-change-password").style.display = "flex";
}

function closeChangePasswordModal() {
  document.getElementById("modal-change-password").style.display = "none";
}

async function handleChangePassword(e) {
  e.preventDefault();
  const current_password = document.getElementById("change-current-password").value;
  const new_password = document.getElementById("change-new-password").value;
  const errorBox = document.getElementById("change-password-error");
  errorBox.style.display = "none";

  try {
    await apiFetch("/api/auth/change-password", {
      method: "POST",
      body: JSON.stringify({ current_password, new_password })
    });
    closeChangePasswordModal();
    alert("Password updated successfully.");
  } catch (err) {
    errorBox.textContent = err.message;
    errorBox.style.display = "block";
  }
}

// ─────────────────────────────────────────────
//  Admin Management (Teachers, Students, Assignments, Settings)
// ─────────────────────────────────────────────

let adminTeachersList = [];
let adminStudentsList = [];

async function loadAdminDashboard() {
  try {
    const data = await apiFetch("/api/dashboard");
    document.getElementById("admin-stat-teachers").textContent = data.total_teachers;
    document.getElementById("admin-stat-students").textContent = data.total_students;
    document.getElementById("admin-stat-classes").textContent = `${data.total_classes} classes enrolled`;

    const assignedCount = data.total_students - (data.unassigned_students || 0);
    document.getElementById("admin-stat-assigned").textContent = `${assignedCount} / ${data.unassigned_students || 0}`;
    document.getElementById("admin-stat-assigned-sub").textContent = `${data.unassigned_students || 0} unassigned`;

    document.getElementById("admin-stat-checkins").textContent = data.total_checkins;
    document.getElementById("admin-stat-alerts-sub").textContent = `${data.open_alerts_count} open alerts`;

    // Aggregated Well-being distribution (Admin sees aggregated numbers only)
    const dist = data.wellbeing_distribution || {};
    document.getElementById("admin-dist-well").textContent = dist["Doing Well"] || dist["Thriving"] || 0;
    document.getElementById("admin-dist-moderate").textContent = dist["Moderate Concern"] || dist["Doing okay"] || 0;
    document.getElementById("admin-dist-attention").textContent = dist["Needs Attention"] || dist["May benefit from support"] || 0;
    document.getElementById("admin-dist-nodata").textContent = dist["No data"] || 0;
  } catch (err) {
    console.error("Error loading admin dashboard:", err);
  }
}

async function loadAdminTeachers() {
  try {
    adminTeachersList = await apiFetch("/api/admin/teachers");
    renderAdminTeachers(adminTeachersList);
  } catch (err) {
    console.error("Error loading teachers:", err);
  }
}

function renderAdminTeachers(teachers) {
  const tbody = document.getElementById("admin-teachers-table-body");
  const emptyBox = document.getElementById("admin-teachers-empty");
  const tableWrap = document.getElementById("admin-teachers-table-wrap");

  if (!teachers || teachers.length === 0) {
    emptyBox.style.display = "block";
    tableWrap.style.display = "none";
    return;
  }

  emptyBox.style.display = "none";
  tableWrap.style.display = "block";

  tbody.innerHTML = teachers.map(t => `
    <tr>
      <td>
        <div style="font-weight: 600; color: var(--text-main);">${escapeHtml(t.full_name)}</div>
        <div style="font-size: 0.8rem; color: var(--text-muted);">${escapeHtml(t.email)}</div>
      </td>
      <td>
        <span class="badge badge-neutral">${escapeHtml(t.assigned_classes || "None")}</span>
      </td>
      <td>
        <span style="font-family: monospace; font-size: 0.9rem;">${escapeHtml(t.check_in_pin || "1234")}</span>
      </td>
      <td><strong>${t.student_count || 0}</strong> assigned</td>
      <td>
        <span class="badge ${t.is_active ? 'badge-green' : 'badge-neutral'}">
          ${t.is_active ? 'Active' : 'Inactive'}
        </span>
      </td>
      <td>
        <div style="display: flex; gap: 0.35rem;">
          <button class="btn btn-outline btn-sm" onclick="editTeacher(${t.id})">Edit</button>
          <button class="btn btn-outline btn-sm" onclick="openResetPasswordModal(${t.id}, 'teacher', '${escapeHtml(t.full_name)}')">Reset Pwd</button>
          <button class="btn btn-outline btn-sm" onclick="toggleTeacherActive(${t.id})">
            ${t.is_active ? 'Deactivate' : 'Activate'}
          </button>
        </div>
      </td>
    </tr>
  `).join("");
}

function filterAdminTeachers() {
  const q = document.getElementById("admin-teacher-search").value.toLowerCase();
  const filtered = adminTeachersList.filter(t =>
    t.full_name.toLowerCase().includes(q) || t.email.toLowerCase().includes(q)
  );
  renderAdminTeachers(filtered);
}

function openAddTeacherModal() {
  document.getElementById("modal-teacher-title").textContent = "Add Teacher Account";
  document.getElementById("teacher-form-id").value = "";
  document.getElementById("teacher-form-name").value = "";
  document.getElementById("teacher-form-email").value = "";
  document.getElementById("teacher-form-password").value = "";
  document.getElementById("teacher-password-group").style.display = "block";
  document.getElementById("teacher-form-classes").value = "";
  document.getElementById("teacher-form-pin").value = "1234";
  document.getElementById("modal-teacher").style.display = "flex";
}

function editTeacher(id) {
  const t = adminTeachersList.find(x => x.id === id);
  if (!t) return;
  document.getElementById("modal-teacher-title").textContent = "Edit Teacher Account";
  document.getElementById("teacher-form-id").value = t.id;
  document.getElementById("teacher-form-name").value = t.full_name;
  document.getElementById("teacher-form-email").value = t.email;
  document.getElementById("teacher-password-group").style.display = "none";
  document.getElementById("teacher-form-classes").value = t.assigned_classes || "";
  document.getElementById("teacher-form-pin").value = t.check_in_pin || "1234";
  document.getElementById("modal-teacher").style.display = "flex";
}

function closeTeacherModal() {
  document.getElementById("modal-teacher").style.display = "none";
}

async function saveTeacher(e) {
  e.preventDefault();
  const id = document.getElementById("teacher-form-id").value;
  const full_name = document.getElementById("teacher-form-name").value.trim();
  const email = document.getElementById("teacher-form-email").value.trim();
  const assigned_classes = document.getElementById("teacher-form-classes").value.trim();
  const check_in_pin = document.getElementById("teacher-form-pin").value.trim();

  try {
    if (id) {
      await apiFetch(`/api/admin/teachers/${id}`, {
        method: "PUT",
        body: JSON.stringify({ full_name, email, assigned_classes, check_in_pin, is_active: true })
      });
    } else {
      const password = document.getElementById("teacher-form-password").value;
      await apiFetch("/api/admin/teachers", {
        method: "POST",
        body: JSON.stringify({ full_name, email, password, assigned_classes, check_in_pin })
      });
    }
    closeTeacherModal();
    loadAdminTeachers();
  } catch (err) {
    alert(err.message);
  }
}

async function toggleTeacherActive(id) {
  try {
    await apiFetch(`/api/admin/teachers/${id}/toggle-status`, { method: "POST" });
    loadAdminTeachers();
  } catch (err) {
    alert(err.message);
  }
}

async function loadAdminStudents() {
  try {
    adminStudentsList = await apiFetch("/api/admin/students");
    updateAdminClassFilterOptions();
    renderAdminStudents(adminStudentsList);
  } catch (err) {
    console.error("Error loading students:", err);
  }
}

function updateAdminClassFilterOptions() {
  const classes = Array.from(new Set(adminStudentsList.map(s => s.class_name).filter(Boolean))).sort();
  const sel = document.getElementById("admin-student-class-filter");
  if (!sel) return;
  const currentVal = sel.value;
  sel.innerHTML = `<option value="">All Classes</option>` +
    classes.map(c => `<option value="${escapeHtml(c)}">${escapeHtml(c)}</option>`).join("");
  sel.value = currentVal;
}

function renderAdminStudents(students) {
  const tbody = document.getElementById("admin-students-table-body");
  const emptyBox = document.getElementById("admin-students-empty");
  const tableWrap = document.getElementById("admin-students-table-wrap");

  if (!students || students.length === 0) {
    emptyBox.style.display = "block";
    tableWrap.style.display = "none";
    return;
  }

  emptyBox.style.display = "none";
  tableWrap.style.display = "block";

  tbody.innerHTML = students.map(s => `
    <tr>
      <td>
        <div style="font-weight: 600; color: var(--text-main);">${escapeHtml(s.name)}</div>
      </td>
      <td><strong>${escapeHtml(s.roll_number || "—")}</strong></td>
      <td><span class="badge badge-neutral">${escapeHtml(s.class_name)}</span></td>
      <td>
        ${s.teacher_name ? `<span style="color: var(--primary); font-weight: 500;">${escapeHtml(s.teacher_name)}</span>` : `<span style="color: var(--status-coral); font-size: 0.8rem;">⚠️ Unassigned</span>`}
      </td>
      <td>
        ${s.student_username ? `<code style="font-family: monospace;">${escapeHtml(s.student_username)}</code>` : `<span style="color: var(--text-dim); font-size: 0.8rem;">No login</span>`}
      </td>
      <td><span style="font-size: 0.82rem; color: var(--text-muted);">${escapeHtml(s.guardian_contact)}</span></td>
      <td>
        <span class="badge ${s.user_active ? 'badge-green' : 'badge-neutral'}">
          ${s.user_active ? 'Active' : 'Inactive'}
        </span>
      </td>
      <td>
        <div style="display: flex; gap: 0.35rem;">
          <button class="btn btn-outline btn-sm" onclick="editAdminStudent(${s.id})">Edit</button>
          ${s.user_id ? `<button class="btn btn-outline btn-sm" onclick="openResetPasswordModal(${s.id}, 'student', '${escapeHtml(s.name)}')">Reset Pwd</button>` : ''}
          ${s.user_id ? `<button class="btn btn-outline btn-sm" onclick="toggleAdminStudentActive(${s.id})">${s.user_active ? 'Deactivate' : 'Activate'}</button>` : ''}
        </div>
      </td>
    </tr>
  `).join("");
}

function filterAdminStudents() {
  const q = document.getElementById("admin-student-search").value.toLowerCase();
  const classFilter = document.getElementById("admin-student-class-filter").value;
  const filtered = adminStudentsList.filter(s => {
    const matchesQ = s.name.toLowerCase().includes(q) || (s.roll_number && s.roll_number.toLowerCase().includes(q));
    const matchesClass = !classFilter || s.class_name === classFilter;
    return matchesQ && matchesClass;
  });
  renderAdminStudents(filtered);
}

async function populateTeacherDropdown(selectElementId, selectedTeacherId = null) {
  const sel = document.getElementById(selectElementId);
  if (!sel) return;
  try {
    const teachers = await apiFetch("/api/admin/teachers");
    sel.innerHTML = `<option value="">None (Unassigned)</option>` +
      teachers.filter(t => t.is_active).map(t =>
        `<option value="${t.id}" ${t.id === selectedTeacherId ? 'selected' : ''}>${escapeHtml(t.full_name)} (${escapeHtml(t.assigned_classes || 'All')})</option>`
      ).join("");
  } catch (err) {
    console.error("Error fetching teachers for dropdown:", err);
  }
}

async function openAdminAddStudentModal() {
  document.getElementById("modal-admin-student-title").textContent = "Enroll Student";
  document.getElementById("admin-student-form-id").value = "";
  document.getElementById("admin-student-form-name").value = "";
  document.getElementById("admin-student-form-roll").value = "";
  document.getElementById("admin-student-form-class").value = "";
  document.getElementById("admin-student-form-guardian").value = "";
  document.getElementById("admin-student-form-contact").value = "";
  document.getElementById("admin-student-form-consent").checked = true;
  document.getElementById("admin-student-form-username").value = "";
  document.getElementById("admin-student-form-password").value = "";
  document.getElementById("admin-student-password-group").style.display = "block";
  await populateTeacherDropdown("admin-student-form-teacher");
  document.getElementById("modal-admin-student").style.display = "flex";
}

async function editAdminStudent(id) {
  const s = adminStudentsList.find(x => x.id === id);
  if (!s) return;
  document.getElementById("modal-admin-student-title").textContent = "Edit Student";
  document.getElementById("admin-student-form-id").value = s.id;
  document.getElementById("admin-student-form-name").value = s.name;
  document.getElementById("admin-student-form-roll").value = s.roll_number || "";
  document.getElementById("admin-student-form-class").value = s.class_name;
  document.getElementById("admin-student-form-guardian").value = s.guardian_name;
  document.getElementById("admin-student-form-contact").value = s.guardian_contact;
  document.getElementById("admin-student-form-consent").checked = Boolean(s.consent_given);
  document.getElementById("admin-student-form-username").value = s.student_username || "";
  document.getElementById("admin-student-password-group").style.display = "none";
  await populateTeacherDropdown("admin-student-form-teacher", s.assigned_teacher_id);
  document.getElementById("modal-admin-student").style.display = "flex";
}

function closeAdminStudentModal() {
  document.getElementById("modal-admin-student").style.display = "none";
}

async function saveAdminStudent(e) {
  e.preventDefault();
  const id = document.getElementById("admin-student-form-id").value;
  const name = document.getElementById("admin-student-form-name").value.trim();
  const roll_number = document.getElementById("admin-student-form-roll").value.trim();
  const class_name = document.getElementById("admin-student-form-class").value.trim();
  const assigned_teacher_id = document.getElementById("admin-student-form-teacher").value || null;
  const guardian_name = document.getElementById("admin-student-form-guardian").value.trim();
  const guardian_contact = document.getElementById("admin-student-form-contact").value.trim();
  const consent_given = document.getElementById("admin-student-form-consent").checked;
  const username = document.getElementById("admin-student-form-username").value.trim();

  try {
    if (id) {
      await apiFetch(`/api/admin/students/${id}`, {
        method: "PUT",
        body: JSON.stringify({
          name, roll_number, class_name, assigned_teacher_id: assigned_teacher_id ? parseInt(assigned_teacher_id) : null,
          guardian_name, guardian_contact, consent_given, username: username || null
        })
      });
    } else {
      const password = document.getElementById("admin-student-form-password").value;
      await apiFetch("/api/admin/students", {
        method: "POST",
        body: JSON.stringify({
          name, roll_number, class_name, assigned_teacher_id: assigned_teacher_id ? parseInt(assigned_teacher_id) : null,
          guardian_name, guardian_contact, consent_given, username: username || null, password: password || null
        })
      });
    }
    closeAdminStudentModal();
    loadAdminStudents();
  } catch (err) {
    alert(err.message);
  }
}

async function toggleAdminStudentActive(id) {
  try {
    await apiFetch(`/api/admin/students/${id}/toggle-status`, { method: "POST" });
    loadAdminStudents();
  } catch (err) {
    alert(err.message);
  }
}

// ─────────────────────────────────────────────
//  Assignments & Bulk Reassignment
// ─────────────────────────────────────────────

async function loadAdminAssignmentsView() {
  try {
    const unassigned = await apiFetch("/api/admin/unassigned-students");
    document.getElementById("unassigned-count-badge").textContent = unassigned.length;
    const container = document.getElementById("unassigned-students-list");
    if (unassigned.length === 0) {
      container.innerHTML = `<div class="empty-state-box" style="margin: 0;">All enrolled students have an assigned primary mentor!</div>`;
    } else {
      container.innerHTML = unassigned.map(s => `
        <div style="display: flex; justify-content: space-between; align-items: center; padding: 0.65rem 0; border-bottom: 1px solid var(--border-color);">
          <div>
            <div style="font-weight: 600;">${escapeHtml(s.name)} (Roll ${escapeHtml(s.roll_number || '—')})</div>
            <div style="font-size: 0.78rem; color: var(--text-muted);">${escapeHtml(s.class_name)}</div>
          </div>
          <button class="btn btn-outline btn-sm" onclick="editAdminStudent(${s.id})">Assign Mentor</button>
        </div>
      `).join("");
    }

    // Teacher workload
    const teachers = await apiFetch("/api/admin/teachers");
    const workloadContainer = document.getElementById("teacher-workload-list");
    workloadContainer.innerHTML = teachers.map(t => `
      <div style="display: flex; justify-content: space-between; align-items: center; padding: 0.65rem 0; border-bottom: 1px solid var(--border-color);">
        <div>
          <div style="font-weight: 600;">${escapeHtml(t.full_name)}</div>
          <div style="font-size: 0.78rem; color: var(--text-muted);">${escapeHtml(t.assigned_classes || 'All classes')}</div>
        </div>
        <span class="badge ${t.student_count > 0 ? 'badge-primary' : 'badge-neutral'}">${t.student_count || 0} mentees</span>
      </div>
    `).join("");
  } catch (err) {
    console.error("Error loading assignments view:", err);
  }
}

async function openBulkAssignModal() {
  await populateTeacherDropdown("bulk-assign-teacher-select");
  const students = await apiFetch("/api/admin/students");
  const container = document.getElementById("bulk-students-checkboxes");
  container.innerHTML = students.map(s => `
    <label class="form-checkbox" style="display: flex; justify-content: space-between; padding: 0.35rem 0; font-size: 0.85rem;">
      <span>
        <input type="checkbox" name="bulk-student-select" value="${s.id}">
        <strong>${escapeHtml(s.name)}</strong> (${escapeHtml(s.class_name)})
      </span>
      <span style="color: var(--text-dim); font-size: 0.75rem;">Current: ${escapeHtml(s.teacher_name || 'Unassigned')}</span>
    </label>
  `).join("");
  document.getElementById("bulk-assign-reason").value = "";
  document.getElementById("modal-bulk-assign").style.display = "flex";
}

function closeBulkAssignModal() {
  document.getElementById("modal-bulk-assign").style.display = "none";
}

async function handleBulkAssignSubmit(e) {
  e.preventDefault();
  const teacherId = document.getElementById("bulk-assign-teacher-select").value;
  if (!teacherId) {
    alert("Please select a target mentor teacher.");
    return;
  }
  const checked = Array.from(document.querySelectorAll("input[name='bulk-student-select']:checked"))
    .map(el => parseInt(el.value));
  if (checked.length === 0) {
    alert("Please select at least one student to assign.");
    return;
  }
  const reason = document.getElementById("bulk-assign-reason").value.trim();

  try {
    await apiFetch("/api/admin/assignments/bulk", {
      method: "POST",
      body: JSON.stringify({
        teacher_id: parseInt(teacherId),
        student_ids: checked,
        reason
      })
    });
    closeBulkAssignModal();
    alert(`Successfully assigned ${checked.length} students.`);
    loadAdminAssignmentsView();
  } catch (err) {
    alert(err.message);
  }
}

async function loadAssignmentHistoryModal() {
  try {
    const history = await apiFetch("/api/admin/assignment-history");
    const tbody = document.getElementById("assignment-history-body");
    if (history.length === 0) {
      tbody.innerHTML = `<tr><td colspan="5" style="text-align: center; color: var(--text-muted);">No assignment changes recorded yet.</td></tr>`;
    } else {
      tbody.innerHTML = history.map(h => `
        <tr>
          <td><span style="font-size: 0.82rem;">${formatDate(h.changed_at)}</span></td>
          <td><strong>${escapeHtml(h.student_name)}</strong></td>
          <td>${escapeHtml(h.old_teacher_name || '—')}</td>
          <td><span style="color: var(--primary); font-weight: 500;">${escapeHtml(h.new_teacher_name || '—')}</span></td>
          <td><span style="font-size: 0.82rem; color: var(--text-muted);">${escapeHtml(h.reason || '—')}</span></td>
        </tr>
      `).join("");
    }
    document.getElementById("modal-assignment-history").style.display = "flex";
  } catch (err) {
    alert(err.message);
  }
}

function closeAssignmentHistoryModal() {
  document.getElementById("modal-assignment-history").style.display = "none";
}

// ─────────────────────────────────────────────
//  Admin Settings
// ─────────────────────────────────────────────

async function loadAdminSettingsView() {
  try {
    const settings = await apiFetch("/api/admin/settings");
    document.getElementById("set-sg-name").value = settings.safeguarding_contact_name || "";
    document.getElementById("set-sg-phone").value = settings.safeguarding_contact_phone || "";
    document.getElementById("set-sg-email").value = settings.safeguarding_contact_email || "";
    document.getElementById("set-reporting-window").value = settings.reporting_window_days || "30";
    document.getElementById("set-checkin-frequency").value = settings.checkin_frequency_days || "7";
  } catch (err) {
    console.error("Error loading settings:", err);
  }
}

async function handleSaveSettings(e) {
  e.preventDefault();
  const alertBox = document.getElementById("settings-alert");
  alertBox.style.display = "none";

  const safeguarding_contact_name = document.getElementById("set-sg-name").value.trim();
  const safeguarding_contact_phone = document.getElementById("set-sg-phone").value.trim();
  const safeguarding_contact_email = document.getElementById("set-sg-email").value.trim();
  const reporting_window_days = parseInt(document.getElementById("set-reporting-window").value) || 30;
  const checkin_frequency_days = parseInt(document.getElementById("set-checkin-frequency").value) || 7;

  try {
    await apiFetch("/api/admin/settings", {
      method: "PUT",
      body: JSON.stringify({
        safeguarding_contact_name,
        safeguarding_contact_phone,
        safeguarding_contact_email,
        reporting_window_days,
        checkin_frequency_days
      })
    });
    alertBox.textContent = "Settings updated successfully.";
    alertBox.style.display = "block";
  } catch (err) {
    alert(err.message);
  }
}

// ─────────────────────────────────────────────
//  Teacher Dashboard & Insights Engine
// ─────────────────────────────────────────────

async function loadTeacherDashboard() {
  try {
    const data = await apiFetch("/api/dashboard");
    document.getElementById("dash-total-students").textContent = data.total_students;
    document.getElementById("dash-class-average").textContent = `${data.class_average_mark}%`;
    document.getElementById("dash-open-alerts").textContent = data.open_alerts_count;

    // Well-being Distribution Card
    const distData = data.wellbeing_distribution;
    const distEmptyEl = document.getElementById("dash-distribution-empty");
    const distContentEl = document.getElementById("dash-distribution-content");
    const distSummaryEl = document.getElementById("dash-distribution-summary");
    const distPendingEl = document.getElementById("dash-distribution-pending");

    if (!distData || !distData.has_data) {
      distEmptyEl.style.display = "block";
      distEmptyEl.textContent = "No assessments completed yet.";
      distContentEl.style.display = "none";
      if (distSummaryEl) distSummaryEl.textContent = distData ? distData.summary_text : "Based on 0 assigned students";
      if (distPendingEl) distPendingEl.textContent = distData ? distData.pending_text : "0 pending";
    } else {
      distEmptyEl.style.display = "none";
      distContentEl.style.display = "block";
      distSummaryEl.textContent = distData.summary_text;
      distPendingEl.textContent = distData.pending_text;

      const cats = distData.categories || {};
      document.getElementById("count-thriving").textContent = cats["Doing Well"] ? `${cats["Doing Well"].count} (${cats["Doing Well"].percentage}%)` : "0 (0%)";
      document.getElementById("count-okay").textContent = cats["Moderate Concern"] ? `${cats["Moderate Concern"].count} (${cats["Moderate Concern"].percentage}%)` : "0 (0%)";
      document.getElementById("count-support").textContent = cats["Needs Attention"] ? `${cats["Needs Attention"].count} (${cats["Needs Attention"].percentage}%)` : "0 (0%)";

      renderWellbeingChart(distData.counts);
    }

    // Teaching & Learning Insights Card
    const insights = data.teaching_insights;
    if (insights) {
      document.getElementById("insight-understanding").textContent = insights.average_lesson_understanding_pct !== null ? `${insights.average_lesson_understanding_pct}%` : "—";
      document.getElementById("insight-participation").textContent = insights.classroom_participation_pct !== null ? `${insights.classroom_participation_pct}%` : "—";

      const pace = insights.teaching_pace_feedback || {};
      document.getElementById("insight-pace-headline").textContent = pace.just_right ? `${pace.just_right}% Just Right` : (pace.fast ? `${pace.fast}% Fast` : "Steady");
      document.getElementById("insight-pace-sub").textContent = `${pace.fast || 0}% Fast • ${pace.slow || 0}% Slow`;

      document.getElementById("insight-support-count").textContent = insights.academic_support_required_count || 0;

      const diffSubjectsEl = document.getElementById("insight-difficult-subjects");
      if (insights.difficult_subjects && insights.difficult_subjects.length > 0) {
        diffSubjectsEl.innerHTML = insights.difficult_subjects.map(s =>
          `<span class="badge badge-coral">${escapeHtml(s.subject)} (${s.count})</span>`
        ).join("");
      } else {
        diffSubjectsEl.innerHTML = `<span style="font-size: 0.85rem; color: var(--text-dim);">No specific subject difficulties flagged.</span>`;
      }

      const prefMethodsEl = document.getElementById("insight-preferred-methods");
      if (insights.preferred_learning_methods && insights.preferred_learning_methods.length > 0) {
        prefMethodsEl.innerHTML = insights.preferred_learning_methods.map(m =>
          `<span class="badge badge-primary">${escapeHtml(m.method)} (${m.count})</span>`
        ).join("");
      } else {
        prefMethodsEl.innerHTML = `<span style="font-size: 0.85rem; color: var(--text-dim);">No learning preferences recorded yet.</span>`;
      }
    }

    // Attention List
    renderAttentionList(data.students_need_attention || []);
  } catch (err) {
    console.error("Error loading teacher dashboard:", err);
  }
}

function renderWellbeingChart(counts) {
  const ctx = document.getElementById("wellbeingDistributionChart");
  if (!ctx) return;

  if (wellbeingChartInstance) {
    wellbeingChartInstance.destroy();
  }

  const wellCount = counts["Doing Well"] || 0;
  const modCount = counts["Moderate Concern"] || 0;
  const attnCount = counts["Needs Attention"] || 0;

  wellbeingChartInstance = new Chart(ctx, {
    type: "bar",
    data: {
      labels: ["Doing Well", "Moderate Concern", "Needs Attention"],
      datasets: [{
        label: "Students",
        data: [wellCount, modCount, attnCount],
        backgroundColor: [
          "#10b981", // green
          "#f59e0b", // amber
          "#fb7185"  // coral
        ],
        borderRadius: 6
      }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: { display: false }
      },
      scales: {
        y: {
          beginAtZero: true,
          ticks: { stepSize: 1, color: "#94a3b8" },
          grid: { color: "rgba(255,255,255,0.06)" }
        },
        x: {
          ticks: { color: "#94a3b8" },
          grid: { display: false }
        }
      }
    }
  });
}

function renderAttentionList(students) {
  const container = document.getElementById("attention-list-container");
  const emptyEl = document.getElementById("attention-list-empty");
  const badge = document.getElementById("attention-count-badge");

  badge.textContent = `${students.length} flagged`;

  if (students.length === 0) {
    emptyEl.style.display = "block";
    container.innerHTML = "";
    return;
  }

  emptyEl.style.display = "none";
  container.innerHTML = students.map(s => `
    <div style="background-color: var(--bg-elevated); border: 1px solid var(--border-color); border-radius: var(--radius-sm); padding: 0.9rem; margin-bottom: 0.65rem;">
      <div style="display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 0.4rem;">
        <div>
          <span style="font-weight: 600; cursor: pointer; color: var(--text-main);" onclick="openStudentProfile(${s.id})">
            ${escapeHtml(s.name)}
          </span>
          <span style="font-size: 0.8rem; color: var(--text-muted); margin-left: 0.5rem;">(${escapeHtml(s.class_name)}${s.roll_number ? ` • Roll ${escapeHtml(s.roll_number)}` : ''})</span>
        </div>
        <div style="display: flex; gap: 0.4rem; align-items: center;">
          <span class="badge ${s.follow_up_status === 'resolved' ? 'badge-green' : (s.follow_up_status === 'in_progress' ? 'badge-primary' : 'badge-amber')}">
            ${escapeHtml(s.follow_up_status || 'New')}
          </span>
          <button class="btn btn-outline btn-sm" onclick="openFollowUpModal(${s.id}, '${escapeHtml(s.name)}', '${s.follow_up_status || 'new'}')">Update</button>
        </div>
      </div>
      <div style="font-size: 0.85rem; color: var(--text-muted); line-height: 1.4;">
        ${escapeHtml(s.summary_reason || 'Requires teacher review.')}
      </div>
    </div>
  `).join("");
}

// ─────────────────────────────────────────────
//  Teacher Students List & Profile
// ─────────────────────────────────────────────

let teacherStudentsList = [];

async function loadTeacherStudents() {
  try {
    teacherStudentsList = await apiFetch("/api/students");
    renderTeacherStudents(teacherStudentsList);
    populateTeacherClassFilter();
  } catch (err) {
    console.error("Error loading teacher students:", err);
  }
}

function populateTeacherClassFilter() {
  const classes = Array.from(new Set(teacherStudentsList.map(s => s.class_name).filter(Boolean))).sort();
  const sel = document.getElementById("teacher-class-filter");
  if (!sel) return;
  sel.innerHTML = `<option value="">All My Classes</option>` +
    classes.map(c => `<option value="${escapeHtml(c)}">${escapeHtml(c)}</option>`).join("");
}

function renderTeacherStudents(students) {
  const tbody = document.getElementById("teacher-students-table-body");
  const emptyBox = document.getElementById("teacher-students-empty");
  const tableWrap = document.getElementById("teacher-students-table-wrap");

  if (!students || students.length === 0) {
    emptyBox.style.display = "block";
    emptyBox.textContent = "No students are currently assigned to this teacher.";
    tableWrap.style.display = "none";
    return;
  }

  emptyBox.style.display = "none";
  tableWrap.style.display = "block";

  tbody.innerHTML = students.map(s => `
    <tr>
      <td>
        <strong style="cursor: pointer; color: var(--primary);" onclick="openStudentProfile(${s.id})">
          ${escapeHtml(s.name)}
        </strong>
      </td>
      <td><strong>${escapeHtml(s.roll_number || '—')}</strong></td>
      <td><span class="badge badge-neutral">${escapeHtml(s.class_name)}</span></td>
      <td><span style="font-size: 0.82rem; color: var(--text-muted);">${escapeHtml(s.guardian_contact)}</span></td>
      <td>
        <span class="badge ${s.badge_class || 'badge-neutral'}">
          ${escapeHtml(s.support_level || 'Doing Well')}
        </span>
      </td>
      <td>
        <span class="badge ${s.consent_given ? 'badge-green' : 'badge-coral'}">
          ${s.consent_given ? 'Consent' : 'No Consent'}
        </span>
      </td>
      <td>
        <button class="btn btn-outline btn-sm" onclick="openStudentProfile(${s.id})">View Profile →</button>
      </td>
    </tr>
  `).join("");
}

function filterTeacherStudents() {
  const q = document.getElementById("teacher-student-search").value.toLowerCase();
  const classFilter = document.getElementById("teacher-class-filter").value;
  const filtered = teacherStudentsList.filter(s => {
    const matchesQ = s.name.toLowerCase().includes(q) || (s.roll_number && s.roll_number.toLowerCase().includes(q));
    const matchesClass = !classFilter || s.class_name === classFilter;
    return matchesQ && matchesClass;
  });
  renderTeacherStudents(filtered);
}

async function openStudentProfile(studentId) {
  activeStudentProfileId = studentId;
  try {
    const data = await apiFetch(`/api/students/${studentId}`);
    renderStudentProfileView(data);
    navigate("student-profile");
  } catch (err) {
    alert(err.message);
  }
}

function returnFromStudentProfile() {
  if (currentUser && currentUser.role === "admin") {
    navigate("admin-students");
  } else {
    navigate("teacher-students");
  }
}

function renderStudentProfileView(data) {
  const s = data.student;
  document.getElementById("profile-student-name").textContent = s.name;
  document.getElementById("profile-class-badge").textContent = s.class_name;
  document.getElementById("profile-roll-badge").textContent = s.roll_number ? `Roll: ${s.roll_number}` : 'Roll: —';
  document.getElementById("profile-guardian-info").textContent = `Guardian: ${s.guardian_name || '—'} (${s.guardian_contact || '—'})`;
  document.getElementById("profile-teacher-assigned").textContent = s.teacher_name ? `Mentor: ${s.teacher_name}` : 'Mentor: Unassigned';

  const consentBadge = document.getElementById("profile-consent-badge");
  consentBadge.textContent = s.consent_given ? "Consent Given" : "Consent Pending";
  consentBadge.className = `badge ${s.consent_given ? 'badge-green' : 'badge-coral'}`;

  // Support Info
  const sup = data.support_info || {};
  const supBadge = document.getElementById("profile-support-badge");
  supBadge.textContent = sup.level || "Doing Well";
  supBadge.className = `badge ${sup.badge_class || 'badge-green'}`;
  document.getElementById("profile-support-reason").textContent = sup.reason || "—";

  // Learning Gaps Chips
  const gapsContainer = document.getElementById("profile-gaps-container");
  if (!data.learning_gaps || data.learning_gaps.length === 0) {
    gapsContainer.innerHTML = `<span style="font-size: 0.85rem; color: var(--text-dim);">No academic learning gaps currently flagged.</span>`;
  } else {
    gapsContainer.innerHTML = data.learning_gaps.map(g => `
      <div class="chip chip-gap">
        ⚠️ <strong>${escapeHtml(g.subject)}</strong>: ${escapeHtml(g.reason)}
      </div>
    `).join("");
  }

  // Recommendations
  const recContainer = document.getElementById("profile-recommendations-container");
  if (!data.recommendations || data.recommendations.length === 0) {
    recContainer.innerHTML = `<p style="font-size: 0.85rem; color: var(--text-dim);">No specific action items required.</p>`;
  } else {
    recContainer.innerHTML = data.recommendations.map(r => `
      <div style="background-color: var(--bg-elevated); border: 1px solid var(--border-color); border-radius: var(--radius-sm); padding: 0.85rem;">
        <div style="font-weight: 600; color: var(--primary); margin-bottom: 0.25rem;">${escapeHtml(r.title)}</div>
        <div style="font-size: 0.85rem; color: var(--text-muted); line-height: 1.4;">${escapeHtml(r.action)}</div>
      </div>
    `).join("");
  }

  // Observations
  const obsContainer = document.getElementById("profile-observations-container");
  if (!data.observations || data.observations.length === 0) {
    obsContainer.innerHTML = `<div class="empty-state-box" style="margin: 0.5rem 0;">No teacher observations recorded yet.</div>`;
  } else {
    obsContainer.innerHTML = data.observations.map(o => `
      <div style="background-color: var(--bg-elevated); border: 1px solid var(--border-color); border-radius: var(--radius-sm); padding: 0.85rem;">
        <div style="display: flex; justify-content: space-between; margin-bottom: 0.25rem;">
          <span style="font-weight: 600; font-size: 0.88rem;">${escapeHtml(o.teacher_name || 'Teacher')}</span>
          <span class="badge ${o.status === 'resolved' ? 'badge-green' : (o.status === 'in_progress' ? 'badge-primary' : 'badge-amber')}">${escapeHtml(o.status)}</span>
        </div>
        <p style="font-size: 0.85rem; color: var(--text-main); line-height: 1.4;">${escapeHtml(o.observation_text)}</p>
        ${o.follow_up_action ? `<p style="font-size: 0.8rem; color: var(--primary); margin-top: 0.35rem;">↳ Plan: ${escapeHtml(o.follow_up_action)}</p>` : ''}
        <span style="font-size: 0.75rem; color: var(--text-dim); display: block; margin-top: 0.35rem;">${formatDate(o.created_at)}</span>
      </div>
    `).join("");
  }

  // Assessments Table
  const assBody = document.getElementById("profile-assessments-body");
  if (!data.assessments || data.assessments.length === 0) {
    assBody.innerHTML = `<tr><td colspan="5" style="text-align: center; color: var(--text-muted);">No assessments recorded yet.</td></tr>`;
  } else {
    assBody.innerHTML = data.assessments.map(a => {
      const pct = Math.round((a.score / a.max_score) * 100);
      return `
        <tr>
          <td>${escapeHtml(a.date)}</td>
          <td><strong>${escapeHtml(a.subject)}</strong></td>
          <td>${a.score} / ${a.max_score}</td>
          <td><span class="badge ${pct < 40 ? 'badge-coral' : (pct >= 75 ? 'badge-green' : 'badge-neutral')}">${pct}%</span></td>
          <td><span style="font-size: 0.82rem; color: var(--text-muted);">${escapeHtml(a.notes || '—')}</span></td>
        </tr>
      `;
    }).join("");
  }

  // Checkins Table
  const checkBody = document.getElementById("profile-checkins-body");
  if (!data.checkins || data.checkins.length === 0) {
    checkBody.innerHTML = `<tr><td colspan="8" style="text-align: center; color: var(--text-muted);">No mental health check-ins recorded yet.</td></tr>`;
  } else {
    checkBody.innerHTML = data.checkins.map(c => `
      <tr>
        <td><span style="font-size: 0.82rem;">${formatDate(c.created_at)}</span></td>
        <td><strong>${c.score ? c.score.toFixed(1) : '—'} / 5.0</strong></td>
        <td>${c.mood || '—'}</td>
        <td>${c.stress || '—'}</td>
        <td>${c.sleep || '—'}</td>
        <td>${c.focus || '—'}</td>
        <td>${c.belonging || '—'}</td>
        <td><span style="font-size: 0.82rem; color: var(--text-muted);">${escapeHtml(c.note || 'None')}</span></td>
      </tr>
    `).join("");
  }

  renderStudentAcademicChart(data.assessments || []);
}

function renderStudentAcademicChart(assessments) {
  const ctx = document.getElementById("studentAcademicChart");
  if (!ctx) return;
  if (studentChartInstance) studentChartInstance.destroy();

  if (!assessments || assessments.length === 0) {
    return;
  }

  const bySubject = {};
  assessments.forEach(a => {
    if (!bySubject[a.subject]) bySubject[a.subject] = [];
    const pct = Math.round((a.score / a.max_score) * 100);
    bySubject[a.subject].push({ date: a.date, pct });
  });

  const allDates = Array.from(new Set(assessments.map(a => a.date))).sort();
  const colors = ["#8b5cf6", "#3b82f6", "#10b981", "#f59e0b", "#fb7185"];
  let colorIdx = 0;

  const datasets = Object.keys(bySubject).map(subj => {
    const c = colors[colorIdx % colors.length];
    colorIdx++;
    const dataPoints = allDates.map(d => {
      const entry = bySubject[subj].find(x => x.date === d);
      return entry ? entry.pct : null;
    });
    return {
      label: subj,
      data: dataPoints,
      borderColor: c,
      backgroundColor: c,
      spanGaps: true,
      tension: 0.25
    };
  });

  studentChartInstance = new Chart(ctx, {
    type: "line",
    data: {
      labels: allDates,
      datasets
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: { position: "top", labels: { color: "#94a3b8" } }
      },
      scales: {
        y: {
          min: 0,
          max: 100,
          ticks: { color: "#94a3b8" },
          grid: { color: "rgba(255,255,255,0.06)" }
        },
        x: {
          ticks: { color: "#94a3b8" },
          grid: { display: false }
        }
      }
    }
  });
}

// ─────────────────────────────────────────────
//  Teacher Follow-Up Workflow Modal
// ─────────────────────────────────────────────

function openFollowUpModal(studentId, studentName, currentStatus) {
  document.getElementById("followup-student-id").value = studentId;
  document.getElementById("followup-student-name").textContent = `Follow-Up for: ${studentName}`;
  document.getElementById("followup-status-select").value = currentStatus || "new";
  document.getElementById("followup-notes").value = "";
  document.getElementById("modal-followup").style.display = "flex";
}

function closeFollowUpModal() {
  document.getElementById("modal-followup").style.display = "none";
}

async function handleFollowUpSubmit(e) {
  e.preventDefault();
  const studentId = document.getElementById("followup-student-id").value;
  const status = document.getElementById("followup-status-select").value;
  const notes = document.getElementById("followup-notes").value.trim();

  try {
    await apiFetch(`/api/students/${studentId}/follow-up`, {
      method: "PUT",
      body: JSON.stringify({ status, notes })
    });
    closeFollowUpModal();
    loadTeacherDashboard();
  } catch (err) {
    alert(err.message);
  }
}

// ─────────────────────────────────────────────
//  Teacher Observations & Assessment Marks Modals
// ─────────────────────────────────────────────

function openAddObservationModal() {
  document.getElementById("obs-student-id").value = activeStudentProfileId;
  document.getElementById("obs-text").value = "";
  document.getElementById("obs-action").value = "";
  document.getElementById("obs-status").value = "new";
  document.getElementById("modal-observation").style.display = "flex";
}

function closeObservationModal() {
  document.getElementById("modal-observation").style.display = "none";
}

async function saveObservation(e) {
  e.preventDefault();
  const studentId = document.getElementById("obs-student-id").value;
  const observation_text = document.getElementById("obs-text").value.trim();
  const follow_up_action = document.getElementById("obs-action").value.trim();
  const status = document.getElementById("obs-status").value;

  try {
    await apiFetch(`/api/students/${studentId}/observations`, {
      method: "POST",
      body: JSON.stringify({ observation_text, follow_up_action, status })
    });
    closeObservationModal();
    openStudentProfile(studentId);
  } catch (err) {
    alert(err.message);
  }
}

function openAddMarkModal() {
  document.getElementById("mark-form-student-id").value = activeStudentProfileId;
  document.getElementById("mark-form-score").value = "";
  document.getElementById("mark-form-max").value = "100";
  document.getElementById("mark-form-date").value = new Date().toISOString().split("T")[0];
  document.getElementById("mark-form-notes").value = "";
  document.getElementById("modal-mark").style.display = "flex";
}

function closeAddMarkModal() {
  document.getElementById("modal-mark").style.display = "none";
}

async function saveMark(e) {
  e.preventDefault();
  const student_id = parseInt(document.getElementById("mark-form-student-id").value);
  const subject = document.getElementById("mark-form-subject").value;
  const score = parseFloat(document.getElementById("mark-form-score").value);
  const max_score = parseFloat(document.getElementById("mark-form-max").value);
  const date = document.getElementById("mark-form-date").value;
  const notes = document.getElementById("mark-form-notes").value.trim();

  try {
    await apiFetch("/api/assessments", {
      method: "POST",
      body: JSON.stringify({ student_id, subject, score, max_score, date, notes })
    });
    closeAddMarkModal();
    openStudentProfile(student_id);
  } catch (err) {
    alert(err.message);
  }
}

// ─────────────────────────────────────────────
//  Teacher Alerts
// ─────────────────────────────────────────────

let teacherAlertsList = [];

async function loadTeacherAlerts() {
  try {
    teacherAlertsList = await apiFetch("/api/alerts");
    filterAlerts("all");
  } catch (err) {
    console.error("Error loading alerts:", err);
  }
}

function filterAlerts(status) {
  document.querySelectorAll("[id^='filter-alert-']").forEach(b => b.classList.remove("active"));
  const btn = document.getElementById(`filter-alert-${status}`);
  if (btn) btn.classList.add("active");

  const filtered = status === "all" ? teacherAlertsList : teacherAlertsList.filter(a => a.status === status);
  renderAlerts(filtered);
}

function renderAlerts(alerts) {
  const container = document.getElementById("alerts-list-container");
  if (!alerts || alerts.length === 0) {
    container.innerHTML = `<div class="empty-state-box">No alerts found matching this filter.</div>`;
    return;
  }

  container.innerHTML = alerts.map(a => `
    <div style="background-color: var(--bg-elevated); border: 1px solid ${a.severity === 'urgent' ? 'var(--status-urgent)' : 'var(--border-color)'}; border-radius: var(--radius-sm); padding: 1rem;">
      <div style="display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 0.5rem;">
        <div>
          <span class="badge ${a.severity === 'urgent' ? 'badge-coral' : 'badge-neutral'}">${a.severity.toUpperCase()}</span>
          <strong style="margin-left: 0.5rem; color: var(--text-main); font-size: 1rem;">${escapeHtml(a.title)}</strong>
        </div>
        <span class="badge ${a.status === 'open' ? 'badge-coral' : (a.status === 'resolved' ? 'badge-green' : 'badge-amber')}">${escapeHtml(a.status)}</span>
      </div>
      <p style="color: var(--text-muted); font-size: 0.9rem; line-height: 1.5;">${escapeHtml(a.message)}</p>
      <div style="display: flex; justify-content: space-between; align-items: center; margin-top: 1rem; border-top: 1px solid var(--border-color); padding-top: 0.75rem;">
        <span style="font-size: 0.75rem; color: var(--text-dim);">${formatDate(a.created_at)}</span>
        <div style="display: flex; gap: 0.4rem;">
          ${a.status !== 'acknowledged' ? `<button class="btn btn-outline btn-sm" onclick="setAlertStatus(${a.id}, 'acknowledged')">Acknowledge</button>` : ''}
          ${a.status !== 'snoozed' ? `<button class="btn btn-outline btn-sm" onclick="setAlertStatus(${a.id}, 'snoozed')">Snooze</button>` : ''}
          ${a.status !== 'resolved' ? `<button class="btn btn-primary btn-sm" onclick="setAlertStatus(${a.id}, 'resolved')">Resolve</button>` : ''}
        </div>
      </div>
    </div>
  `).join("");
}

async function setAlertStatus(alertId, newStatus) {
  try {
    await apiFetch(`/api/alerts/${alertId}/status`, {
      method: "POST",
      body: JSON.stringify({ status: newStatus })
    });
    loadTeacherAlerts();
  } catch (err) {
    alert(err.message);
  }
}

// ─────────────────────────────────────────────
//  Student Portal Engine (Strict Privacy)
// ─────────────────────────────────────────────

async function loadStudentPortal() {
  try {
    const data = await apiFetch("/api/dashboard");
    const st = data.student;
    if (st) {
      document.getElementById("student-portal-welcome").textContent = `Welcome, ${st.name}!`;
      document.getElementById("student-mentor-info").textContent = `Class: ${st.class_name}${st.roll_number ? ` • Roll: ${st.roll_number}` : ''}${data.mentor_name ? ` • Mentor: ${data.mentor_name}` : ''}`;
    }

    // Assessments
    const assContainer = document.getElementById("student-assessments-container");
    if (!data.assessments || data.assessments.length === 0) {
      assContainer.innerHTML = `<p style="font-size: 0.85rem; color: var(--text-dim);">No academic assessments posted yet.</p>`;
    } else {
      assContainer.innerHTML = data.assessments.map(a => {
        const pct = Math.round((a.score / a.max_score) * 100);
        return `
          <div style="display: flex; justify-content: space-between; align-items: center; padding: 0.6rem 0; border-bottom: 1px solid var(--border-color);">
            <div>
              <strong>${escapeHtml(a.subject)}</strong>
              <div style="font-size: 0.75rem; color: var(--text-muted);">${escapeHtml(a.date)}</div>
            </div>
            <span class="badge ${pct < 40 ? 'badge-coral' : 'badge-green'}">${pct}%</span>
          </div>
        `;
      }).join("");
    }

    // Recommendations & Guidance (Supportive strength-based tips)
    const recContainer = document.getElementById("student-recommendations-container");
    if (!data.recommendations || data.recommendations.length === 0) {
      recContainer.innerHTML = `<p style="font-size: 0.85rem; color: var(--text-dim);">Complete your daily check-in to receive personalized learning and well-being strategies!</p>`;
    } else {
      recContainer.innerHTML = data.recommendations.map(r => `
        <div style="background-color: var(--bg-elevated); border: 1px solid var(--border-color); border-radius: var(--radius-sm); padding: 0.85rem;">
          <div style="font-weight: 600; color: var(--primary); margin-bottom: 0.25rem;">🌱 ${escapeHtml(r.title)}</div>
          <div style="font-size: 0.85rem; color: var(--text-muted); line-height: 1.5;">${escapeHtml(r.action)}</div>
        </div>
      `).join("");
    }

    // Student History (Dates & Submitted Notes Only, NO internal concern scores)
    if (currentUser && currentUser.student_id) {
      const profile = await apiFetch(`/api/students/${currentUser.student_id}`);
      const historyBody = document.getElementById("student-history-body");
      if (!profile.checkins || profile.checkins.length === 0) {
        historyBody.innerHTML = `<tr><td colspan="2" style="text-align: center; color: var(--text-muted);">No check-in submissions yet.</td></tr>`;
      } else {
        historyBody.innerHTML = profile.checkins.map(c => `
          <tr>
            <td><span style="font-size: 0.85rem;">${formatDate(c.created_at)}</span></td>
            <td><span style="font-size: 0.82rem; color: var(--text-muted);">${escapeHtml(c.note || 'None recorded')}</span></td>
          </tr>
        `).join("");
      }
    }
  } catch (err) {
    console.error("Error loading student portal:", err);
  }
}

// ─────────────────────────────────────────────
//  Phase 4: Adaptive Mental Health Check-In Engine
// ─────────────────────────────────────────────

async function startStudentAdaptiveCheckIn() {
  isClassroomDeviceSession = false;
  try {
    const res = await apiFetch("/api/checkins/start", { method: "POST" });
    activeAdaptiveSessionId = res.session_id;
    currentQuestionData = res.question;
    selectedAdaptiveAnswers = [];

    document.getElementById("checkin-step-launch").style.display = "none";
    document.getElementById("checkin-step-complete").style.display = "none";
    document.getElementById("checkin-step-questions").style.display = "block";
    document.getElementById("checkin-overlay").style.display = "flex";

    renderAdaptiveQuestion(res);
  } catch (err) {
    alert(err.message);
  }
}

function openClassroomCheckInLauncher() {
  isClassroomDeviceSession = true;
  document.getElementById("checkin-teacher-pin").value = "";
  document.getElementById("checkin-launch-error").style.display = "none";

  // Populate student list for classroom device
  const sel = document.getElementById("checkin-student-select");
  sel.innerHTML = teacherStudentsList.map(s =>
    `<option value="${s.id}">${escapeHtml(s.name)} (${escapeHtml(s.class_name)}${s.roll_number ? ` • Roll ${s.roll_number}` : ''})</option>`
  ).join("");

  document.getElementById("checkin-step-launch").style.display = "block";
  document.getElementById("checkin-step-questions").style.display = "none";
  document.getElementById("checkin-step-complete").style.display = "none";
  document.getElementById("checkin-overlay").style.display = "flex";
}

async function startClassroomCheckInSession() {
  const pin = document.getElementById("checkin-teacher-pin").value.trim();
  const studentId = document.getElementById("checkin-student-select").value;
  const errEl = document.getElementById("checkin-launch-error");
  errEl.style.display = "none";

  if (!pin) {
    errEl.textContent = "Please enter your Teacher PIN.";
    errEl.style.display = "block";
    return;
  }

  try {
    await apiFetch("/api/auth/verify-pin", {
      method: "POST",
      body: JSON.stringify({ pin })
    });

    // Start checkin for student using teacher auth or token
    const res = await apiFetch("/api/checkins/start", { method: "POST" });
    activeAdaptiveSessionId = res.session_id;
    currentQuestionData = res.question;
    selectedAdaptiveAnswers = [];

    document.getElementById("checkin-step-launch").style.display = "none";
    document.getElementById("checkin-step-questions").style.display = "block";
    renderAdaptiveQuestion(res);
  } catch (err) {
    errEl.textContent = err.message;
    errEl.style.display = "block";
  }
}

function renderAdaptiveQuestion(payload) {
  const q = payload.question;
  currentQuestionData = q;
  selectedAdaptiveAnswers = [];

  document.getElementById("checkin-q-domain").textContent = q.domain;
  document.getElementById("checkin-q-progress").textContent = `Step ${payload.total_answered + 1}`;
  document.getElementById("checkin-progress-bar").style.width = `${payload.progress_pct || 10}%`;
  document.getElementById("checkin-q-text").textContent = q.question_text;
  document.getElementById("checkin-error-msg").style.display = "none";

  const container = document.getElementById("checkin-options-container");
  const noteWrap = document.getElementById("checkin-note-wrap");
  const freeText = document.getElementById("checkin-free-text");
  const preferNotBtn = document.getElementById("checkin-prefer-not-btn");
  const submitBtn = document.getElementById("checkin-submit-btn");

  freeText.value = "";
  submitBtn.disabled = true;

  preferNotBtn.style.display = q.prefer_not_to_answer ? "inline-block" : "none";

  if (q.answer_type === "optional_free_text") {
    container.innerHTML = "";
    noteWrap.style.display = "block";
    submitBtn.disabled = false;
    return;
  }

  noteWrap.style.display = "none";

  const isMulti = q.answer_type === "multi_choice";
  container.innerHTML = (q.options || []).map(opt => `
    <div class="adaptive-option-item" id="opt-item-${opt.id}" onclick="handleOptionClick('${opt.id}', ${isMulti})">
      <div class="option-checkbox-indicator">${isMulti ? '✓' : '●'}</div>
      <span>${escapeHtml(opt.label)}</span>
    </div>
  `).join("");
}

function handleOptionClick(optId, isMulti) {
  const submitBtn = document.getElementById("checkin-submit-btn");

  if (isMulti) {
    const idx = selectedAdaptiveAnswers.indexOf(optId);
    if (idx > -1) {
      selectedAdaptiveAnswers.splice(idx, 1);
      document.getElementById(`opt-item-${optId}`).classList.remove("selected");
    } else {
      selectedAdaptiveAnswers.push(optId);
      document.getElementById(`opt-item-${optId}`).classList.add("selected");
    }
  } else {
    selectedAdaptiveAnswers = [optId];
    document.querySelectorAll(".adaptive-option-item").forEach(el => el.classList.remove("selected"));
    const target = document.getElementById(`opt-item-${optId}`);
    if (target) target.classList.add("selected");
  }

  submitBtn.disabled = selectedAdaptiveAnswers.length === 0;
}

async function submitAdaptiveAnswer() {
  const submitBtn = document.getElementById("checkin-submit-btn");
  const errBox = document.getElementById("checkin-error-msg");
  errBox.style.display = "none";
  submitBtn.disabled = true;

  let answerVal = null;
  if (currentQuestionData.answer_type === "optional_free_text") {
    answerVal = document.getElementById("checkin-free-text").value.trim();
  } else if (currentQuestionData.answer_type === "multi_choice") {
    answerVal = selectedAdaptiveAnswers;
  } else {
    answerVal = selectedAdaptiveAnswers[0] || null;
  }

  const note = document.getElementById("checkin-free-text").value.trim() || null;

  try {
    const res = await apiFetch(`/api/checkins/${activeAdaptiveSessionId}/answer`, {
      method: "POST",
      body: JSON.stringify({
        question_id: currentQuestionData.id,
        answer: answerVal,
        preferred_not_to_answer: false,
        note
      })
    });

    if (res.status === "completed") {
      renderCheckInCompletion(res);
    } else {
      renderAdaptiveQuestion(res);
    }
  } catch (err) {
    errBox.textContent = err.message;
    errBox.style.display = "block";
    submitBtn.disabled = false;
  }
}

async function submitPreferNotToAnswer() {
  try {
    const res = await apiFetch(`/api/checkins/${activeAdaptiveSessionId}/answer`, {
      method: "POST",
      body: JSON.stringify({
        question_id: currentQuestionData.id,
        answer: null,
        preferred_not_to_answer: true
      })
    });

    if (res.status === "completed") {
      renderCheckInCompletion(res);
    } else {
      renderAdaptiveQuestion(res);
    }
  } catch (err) {
    alert(err.message);
  }
}

function renderCheckInCompletion(res) {
  document.getElementById("checkin-step-questions").style.display = "none";
  document.getElementById("checkin-step-complete").style.display = "block";

  const sgBox = document.getElementById("checkin-safeguarding-calm");
  const sgText = document.getElementById("checkin-safeguarding-text");

  if (res.urgent_flag && res.safeguarding_message) {
    sgText.textContent = res.safeguarding_message;
    sgBox.style.display = "flex";
  } else {
    sgBox.style.display = "none";
  }

  const guidanceBox = document.getElementById("checkin-completion-guidance");
  if (res.recommendations && res.recommendations.length > 0) {
    guidanceBox.innerHTML = res.recommendations.map(r => `
      <div style="background-color: var(--bg-elevated); border: 1px solid var(--border-color); border-radius: var(--radius-sm); padding: 0.85rem;">
        <div style="font-weight: 600; color: var(--primary); margin-bottom: 0.25rem;">🌱 ${escapeHtml(r.title)}</div>
        <div style="font-size: 0.85rem; color: var(--text-muted); line-height: 1.5;">${escapeHtml(r.action)}</div>
      </div>
    `).join("");
  } else {
    guidanceBox.innerHTML = `<p style="font-size: 0.85rem; color: var(--text-dim);">No specific strategies needed. Keep shining!</p>`;
  }
}

function finishCheckInSession() {
  document.getElementById("checkin-overlay").style.display = "none";
  activeAdaptiveSessionId = null;
  currentQuestionData = null;
  if (isClassroomDeviceSession) {
    loadTeacherDashboard();
  } else {
    loadStudentPortal();
  }
}

function exitCheckInOverlay() {
  if (isClassroomDeviceSession) {
    document.getElementById("prompt-exit-pin").value = "";
    document.getElementById("pin-prompt-error").style.display = "none";
    document.getElementById("modal-pin-prompt").style.display = "flex";
  } else {
    document.getElementById("checkin-overlay").style.display = "none";
    activeAdaptiveSessionId = null;
    currentQuestionData = null;
    loadStudentPortal();
  }
}

function closePinPrompt() {
  document.getElementById("modal-pin-prompt").style.display = "none";
}

async function confirmCheckInExit(e) {
  e.preventDefault();
  const pin = document.getElementById("prompt-exit-pin").value.trim();
  const errEl = document.getElementById("pin-prompt-error");
  errEl.style.display = "none";

  try {
    await apiFetch("/api/auth/verify-pin", {
      method: "POST",
      body: JSON.stringify({ pin })
    });
    closePinPrompt();
    document.getElementById("checkin-overlay").style.display = "none";
    activeAdaptiveSessionId = null;
    currentQuestionData = null;
    loadTeacherDashboard();
  } catch (err) {
    errEl.textContent = "Invalid PIN.";
    errEl.style.display = "block";
  }
}

// ─────────────────────────────────────────────
//  Password Reset Modal (Admin)
// ─────────────────────────────────────────────

function openResetPasswordModal(id, type, name) {
  document.getElementById("reset-target-id").value = id;
  document.getElementById("reset-target-type").value = type;
  document.getElementById("reset-target-name").textContent = `Resetting password for ${type}: ${name}`;
  document.getElementById("reset-new-password").value = "";
  document.getElementById("modal-reset-password").style.display = "flex";
}

function closeResetPasswordModal() {
  document.getElementById("modal-reset-password").style.display = "none";
}

async function handleAdminResetPassword(e) {
  e.preventDefault();
  const id = document.getElementById("reset-target-id").value;
  const type = document.getElementById("reset-target-type").value;
  const new_password = document.getElementById("reset-new-password").value;

  try {
    const endpoint = type === "teacher"
      ? `/api/admin/teachers/${id}/reset-password`
      : `/api/admin/students/${id}/reset-password`;

    await apiFetch(endpoint, {
      method: "POST",
      body: JSON.stringify({ new_password })
    });

    closeResetPasswordModal();
    alert("Password reset successfully. The user will be prompted to change it on their next login.");
  } catch (err) {
    alert(err.message);
  }
}

// ─────────────────────────────────────────────
//  Audit Logs Loader
// ─────────────────────────────────────────────

async function loadAuditLogs() {
  try {
    const logs = await apiFetch("/api/admin/audit-logs");
    const tbody = document.getElementById("admin-audit-table-body");
    if (!logs || logs.length === 0) {
      tbody.innerHTML = `<tr><td colspan="5" style="text-align: center; color: var(--text-muted);">No audit log events recorded yet.</td></tr>`;
      return;
    }
    tbody.innerHTML = logs.map(l => `
      <tr>
        <td><span style="font-size: 0.8rem;">${formatDate(l.timestamp)}</span></td>
        <td><code>${escapeHtml(l.user_email || 'System')}</code></td>
        <td><span class="badge badge-neutral">${escapeHtml(l.action)}</span></td>
        <td><span style="font-size: 0.82rem; color: var(--text-muted);">${escapeHtml(l.resource_type || '—')}</span></td>
        <td><span style="font-size: 0.85rem; color: var(--text-main);">${escapeHtml(l.details)}</span></td>
      </tr>
    `).join("");
  } catch (err) {
    console.error("Error loading audit logs:", err);
  }
}

// ─────────────────────────────────────────────
//  Utility Functions
// ─────────────────────────────────────────────

function escapeHtml(text) {
  if (!text) return "";
  return String(text)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#039;");
}

function formatDate(isoString) {
  if (!isoString) return "—";
  try {
    const d = new Date(isoString);
    return d.toLocaleString(undefined, {
      month: "short",
      day: "numeric",
      hour: "2-digit",
      minute: "2-digit"
    });
  } catch (e) {
    return isoString;
  }
}
