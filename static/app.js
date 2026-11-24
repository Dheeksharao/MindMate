// MindMate – Student Well-being & Academic Support (v2.0)
// Fully Database-Driven SPA Client Engine

let currentUser = null;
let authToken = localStorage.getItem("mindmate_token") || null;
let currentView = "login";
let activeStudentProfileId = null;

let wellbeingChartInstance = null;
let studentChartInstance = null;

// Kiosk State
let kioskStudentId = null;
let kioskTeacherPin = "";
let kioskCurrentStep = 1;
const kioskAnswers = {
  mood: null,
  stress: null,
  sleep: null,
  focus: null,
  belonging: null,
  note: ""
};

// Student Self Check-in State
const selfCheckinAnswers = {
  mood: null,
  stress: null,
  sleep: null,
  focus: null,
  belonging: null
};

// ----------------- API Fetch Client -----------------

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
    throw new Error("Session expired or unauthorized. Please sign in again.");
  }

  if (response.status === 403) {
    const errData = await response.json().catch(() => ({}));
    throw new Error(errData.detail || "Access forbidden: You do not have permission for this resource.");
  }

  if (!response.ok) {
    const errData = await response.json().catch(() => ({}));
    throw new Error(errData.detail || "An error occurred with your request.");
  }

  return response.json();
}

// ----------------- App Initialization -----------------

window.addEventListener("DOMContentLoaded", async () => {
  try {
    const setupStatus = await apiFetch("/api/auth/setup-status");
    if (setupStatus.needs_setup) {
      navigate("setup");
      return;
    }
  } catch (err) {
    console.error("Setup check error:", err);
  }

  if (authToken) {
    try {
      currentUser = await apiFetch("/api/auth/me");
      updateNavForUser();
      navigateHome();
      return;
    } catch (e) {
      console.warn("Session check failed:", e.message);
      authToken = null;
      localStorage.removeItem("mindmate_token");
    }
  }
  navigate("login");
});

// ----------------- Navigation Engine -----------------

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

  // Route routing
  if (viewName === "admin-dashboard") {
    document.getElementById("nav-admin-dash").classList.add("active");
    document.getElementById("view-admin-dashboard").style.display = "block";
    loadAdminDashboard();
  } else if (viewName === "admin-teachers") {
    document.getElementById("nav-admin-teachers").classList.add("active");
    document.getElementById("view-admin-teachers").style.display = "block";
    loadAdminTeachers();
  } else if (viewName === "admin-students") {
    document.getElementById("nav-admin-students").classList.add("active");
    document.getElementById("view-admin-students").style.display = "block";
    loadAdminStudents();
  } else if (viewName === "admin-audit") {
    document.getElementById("nav-admin-audit").classList.add("active");
    document.getElementById("view-admin-audit").style.display = "block";
    loadAuditLogs();
  } else if (viewName === "teacher-dashboard") {
    document.getElementById("nav-teacher-dash").classList.add("active");
    document.getElementById("view-teacher-dashboard").style.display = "block";
    loadTeacherDashboard();
  } else if (viewName === "teacher-students") {
    document.getElementById("nav-teacher-students").classList.add("active");
    document.getElementById("view-teacher-students").style.display = "block";
    loadTeacherStudents();
  } else if (viewName === "student-profile") {
    document.getElementById("view-student-profile").style.display = "block";
    if (activeStudentProfileId) {
      loadStudentProfile(activeStudentProfileId);
    }
  } else if (viewName === "teacher-alerts") {
    document.getElementById("nav-teacher-alerts").classList.add("active");
    document.getElementById("view-teacher-alerts").style.display = "block";
    loadTeacherAlerts();
  } else if (viewName === "student-portal") {
    document.getElementById("nav-student-dash").classList.add("active");
    document.getElementById("view-student-portal").style.display = "block";
    loadStudentPortal();
  }
}

function updateNavForUser() {
  if (!currentUser) return;
  document.getElementById("user-name-display").textContent = currentUser.full_name;

  const roleBadge = document.getElementById("user-role-badge");
  const navAdmin = document.getElementById("nav-links-admin");
  const navTeacher = document.getElementById("nav-links-teacher");
  const navStudent = document.getElementById("nav-links-student");
  const subtitle = document.getElementById("nav-portal-subtitle");

  navAdmin.style.display = "none";
  navTeacher.style.display = "none";
  navStudent.style.display = "none";

  if (currentUser.role === "admin") {
    document.getElementById("user-role-icon").textContent = "🛡️";
    roleBadge.textContent = "Administrator";
    roleBadge.className = "badge badge-neutral";
    navAdmin.style.display = "flex";
    subtitle.textContent = "Administrator Portal";
  } else if (currentUser.role === "student") {
    document.getElementById("user-role-icon").textContent = "🎓";
    roleBadge.textContent = "Student";
    roleBadge.className = "badge badge-green";
    navStudent.style.display = "flex";
    subtitle.textContent = "Student Space";
  } else {
    document.getElementById("user-role-icon").textContent = "👩‍🏫";
    roleBadge.textContent = currentUser.assigned_classes || "Classroom Teacher";
    roleBadge.className = "badge badge-neutral";
    navTeacher.style.display = "flex";
    subtitle.textContent = "Teacher Portal";
  }
}

// ----------------- Initial Setup & Auth Handlers -----------------

async function handleInitialSetup(e) {
  e.preventDefault();
  const errorEl = document.getElementById("setup-error");
  errorEl.style.display = "none";

  const full_name = document.getElementById("setup-name").value.trim();
  const email = document.getElementById("setup-email").value.trim();
  const password = document.getElementById("setup-password").value;

  try {
    const data = await apiFetch("/api/auth/setup", {
      method: "POST",
      body: JSON.stringify({ full_name, email, password })
    });

    authToken = data.access_token;
    currentUser = data.user;
    localStorage.setItem("mindmate_token", authToken);

    updateNavForUser();
    navigate("admin-dashboard");
  } catch (err) {
    errorEl.textContent = err.message || "Failed to set up administrator.";
    errorEl.style.display = "block";
  }
}

async function handleLogin(e) {
  e.preventDefault();
  const errorEl = document.getElementById("login-error");
  errorEl.style.display = "none";

  const email = document.getElementById("login-email").value.trim();
  const password = document.getElementById("login-password").value;

  try {
    const data = await apiFetch("/api/auth/login", {
      method: "POST",
      body: JSON.stringify({ email, password })
    });

    authToken = data.access_token;
    currentUser = data.user;
    localStorage.setItem("mindmate_token", authToken);

    updateNavForUser();
    navigateHome();
  } catch (err) {
    errorEl.textContent = err.message || "Incorrect email or password.";
    errorEl.style.display = "block";
  }
}

function logout() {
  authToken = null;
  currentUser = null;
  localStorage.removeItem("mindmate_token");
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
  const errorEl = document.getElementById("change-password-error");

  try {
    await apiFetch("/api/auth/change-password", {
      method: "POST",
      body: JSON.stringify({ current_password, new_password })
    });
    alert("Password updated successfully.");
    closeChangePasswordModal();
  } catch (err) {
    errorEl.textContent = err.message;
    errorEl.style.display = "block";
  }
}

// ----------------- Admin Section -----------------

async function loadAdminDashboard() {
  try {
    const stats = await apiFetch("/api/dashboard");
    document.getElementById("admin-stat-teachers").textContent = stats.total_teachers;
    document.getElementById("admin-stat-students").textContent = stats.total_students;
    document.getElementById("admin-stat-classes").textContent = `${stats.total_classes} class${stats.total_classes === 1 ? '' : 'es'} enrolled`;
    document.getElementById("admin-stat-records").textContent = `${stats.total_assessments} / ${stats.total_checkins}`;
    document.getElementById("admin-stat-alerts").textContent = `${stats.total_observations} / ${stats.open_alerts_count}`;
  } catch (err) {
    console.error("Admin dashboard error:", err);
  }
}

let adminTeachersCache = [];

async function loadAdminTeachers() {
  try {
    adminTeachersCache = await apiFetch("/api/admin/teachers");
    renderAdminTeachersTable(adminTeachersCache);
  } catch (err) {
    console.error("Error loading teachers:", err);
  }
}

function filterAdminTeachers() {
  const query = document.getElementById("admin-teacher-search").value.toLowerCase().trim();
  const filtered = adminTeachersCache.filter(t => {
    return t.full_name.toLowerCase().includes(query) || t.email.toLowerCase().includes(query) || (t.assigned_classes || "").toLowerCase().includes(query);
  });
  renderAdminTeachersTable(filtered);
}

function renderAdminTeachersTable(teachers) {
  const tbody = document.getElementById("admin-teachers-table-body");
  if (!teachers || teachers.length === 0) {
    tbody.innerHTML = `
      <tr>
        <td colspan="6">
          <div class="empty-state">
            <span class="empty-state-icon">👩‍🏫</span>
            <div class="empty-state-title">No Teachers Added Yet</div>
            <p class="empty-state-desc">Create teacher accounts with email credentials and assigned classes so they can access MindMate.</p>
            <button class="btn btn-primary btn-sm" onclick="openAddTeacherModal()">+ Add First Teacher</button>
          </div>
        </td>
      </tr>
    `;
    return;
  }

  tbody.innerHTML = teachers.map(t => `
    <tr style="${t.is_active ? '' : 'opacity: 0.6;'}">
      <td>
        <strong>${escapeHtml(t.full_name)}</strong>
        <div style="font-size: 0.8rem; color: var(--text-muted);">${escapeHtml(t.email)}</div>
      </td>
      <td>
        ${t.assigned_classes ? t.assigned_classes.split(',').map(c => `<span class="badge badge-neutral" style="margin-right:3px;">${escapeHtml(c.trim())}</span>`).join('') : '<span style="color:var(--text-dim);">No classes assigned</span>'}
      </td>
      <td><span style="font-family: monospace;">${escapeHtml(t.kiosk_pin || '1234')}</span></td>
      <td>${t.student_count || 0} students</td>
      <td>
        <span class="badge ${t.is_active ? 'badge-green' : 'badge-coral'}">
          ${t.is_active ? 'Active' : 'Deactivated'}
        </span>
      </td>
      <td>
        <div style="display: flex; gap: 0.35rem;">
          <button class="btn btn-outline btn-sm" onclick="openEditTeacherModal(${t.id})">Edit</button>
          <button class="btn btn-outline btn-sm" onclick="openResetPasswordModal(${t.id}, 'teacher', '${escapeHtml(t.full_name)}')">Reset Password</button>
          <button class="btn ${t.is_active ? 'btn-coral' : 'btn-green'} btn-sm" onclick="toggleTeacherStatus(${t.id})">
            ${t.is_active ? 'Deactivate' : 'Activate'}
          </button>
        </div>
      </td>
    </tr>
  `).join("");
}

function openAddTeacherModal() {
  document.getElementById("modal-teacher-title").textContent = "Add Teacher Account";
  document.getElementById("teacher-form-id").value = "";
  document.getElementById("teacher-form-name").value = "";
  document.getElementById("teacher-form-email").value = "";
  document.getElementById("teacher-form-password").value = "";
  document.getElementById("teacher-form-password").required = true;
  document.getElementById("teacher-password-group").style.display = "block";
  document.getElementById("teacher-form-classes").value = "";
  document.getElementById("teacher-form-pin").value = "1234";
  document.getElementById("modal-teacher").style.display = "flex";
}

function openEditTeacherModal(id) {
  const t = adminTeachersCache.find(x => x.id === id);
  if (!t) return;
  document.getElementById("modal-teacher-title").textContent = "Edit Teacher Account";
  document.getElementById("teacher-form-id").value = t.id;
  document.getElementById("teacher-form-name").value = t.full_name;
  document.getElementById("teacher-form-email").value = t.email;
  document.getElementById("teacher-password-group").style.display = "none";
  document.getElementById("teacher-form-password").required = false;
  document.getElementById("teacher-form-classes").value = t.assigned_classes || "";
  document.getElementById("teacher-form-pin").value = t.kiosk_pin || "1234";
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
  const kiosk_pin = document.getElementById("teacher-form-pin").value.trim();

  try {
    if (id) {
      await apiFetch(`/api/admin/teachers/${id}`, {
        method: "PUT",
        body: JSON.stringify({ full_name, email, assigned_classes, kiosk_pin, is_active: true })
      });
    } else {
      const password = document.getElementById("teacher-form-password").value;
      await apiFetch("/api/admin/teachers", {
        method: "POST",
        body: JSON.stringify({ full_name, email, password, assigned_classes, kiosk_pin })
      });
    }
    closeTeacherModal();
    loadAdminTeachers();
  } catch (err) {
    alert(err.message);
  }
}

async function toggleTeacherStatus(teacherId) {
  try {
    await apiFetch(`/api/admin/teachers/${teacherId}/toggle-status`, { method: "POST" });
    loadAdminTeachers();
  } catch (err) {
    alert(err.message);
  }
}

// Admin Students Management
let adminStudentsCache = [];

async function loadAdminStudents() {
  try {
    const [students, teachers] = await Promise.all([
      apiFetch("/api/admin/students"),
      apiFetch("/api/admin/teachers")
    ]);
    adminStudentsCache = students;

    // Populate teacher dropdown in student modal
    const teacherSelect = document.getElementById("admin-student-form-teacher");
    teacherSelect.innerHTML = `<option value="">None / Open to Class</option>` + teachers.map(t => `<option value="${t.id}">${escapeHtml(t.full_name)} (${escapeHtml(t.assigned_classes || 'All')})</option>`).join("");

    // Populate class filter
    const classes = Array.from(new Set(students.map(s => s.class_name).filter(Boolean))).sort();
    const classFilter = document.getElementById("admin-student-class-filter");
    classFilter.innerHTML = `<option value="">All Classes</option>` + classes.map(c => `<option value="${c}">${c}</option>`).join("");

    renderAdminStudentsTable(adminStudentsCache);
  } catch (err) {
    console.error("Error loading admin students:", err);
  }
}

function filterAdminStudents() {
  const query = document.getElementById("admin-student-search").value.toLowerCase().trim();
  const classFilter = document.getElementById("admin-student-class-filter").value;

  const filtered = adminStudentsCache.filter(s => {
    if (classFilter && s.class_name !== classFilter) return false;
    if (query) {
      const matchName = s.name.toLowerCase().includes(query);
      const matchEmail = (s.student_email || "").toLowerCase().includes(query);
      return matchName || matchEmail;
    }
    return true;
  });
  renderAdminStudentsTable(filtered);
}

function renderAdminStudentsTable(students) {
  const tbody = document.getElementById("admin-students-table-body");
  if (!students || students.length === 0) {
    tbody.innerHTML = `
      <tr>
        <td colspan="7">
          <div class="empty-state">
            <span class="empty-state-icon">👥</span>
            <div class="empty-state-title">No Students Enrolled Yet</div>
            <p class="empty-state-desc">Add real students to classes, assign their teachers, and optionally grant student portal logins.</p>
            <button class="btn btn-primary btn-sm" onclick="openAdminAddStudentModal()">+ Enroll First Student</button>
          </div>
        </td>
      </tr>
    `;
    return;
  }

  tbody.innerHTML = students.map(s => `
    <tr style="${s.is_archived ? 'opacity: 0.6;' : ''}">
      <td>
        <strong>${escapeHtml(s.name)}</strong>
        <div style="font-size: 0.75rem; color: var(--text-dim);">Added on ${new Date(s.created_at).toLocaleDateString()}</div>
      </td>
      <td><span class="badge badge-neutral">${escapeHtml(s.class_name)}</span></td>
      <td>${s.teacher_name ? escapeHtml(s.teacher_name) : '<span style="color:var(--text-dim);">Open</span>'}</td>
      <td>
        <div>${escapeHtml(s.guardian_name)}</div>
        <div style="font-size: 0.75rem; color: var(--text-muted);">${escapeHtml(s.guardian_contact)}</div>
      </td>
      <td>
        ${s.student_email ? `
          <div style="font-size: 0.85rem;">${escapeHtml(s.student_email)}</div>
          <span class="badge ${s.user_active ? 'badge-green' : 'badge-coral'}" style="font-size: 0.7rem;">
            ${s.user_active ? 'Login Active' : 'Login Inactive'}
          </span>
        ` : '<span style="color:var(--text-dim); font-size:0.8rem;">No login created</span>'}
      </td>
      <td>
        ${s.is_archived ? '<span class="badge badge-coral">Archived</span>' : '<span class="badge badge-green">Enrolled</span>'}
      </td>
      <td>
        <div style="display: flex; gap: 0.35rem; flex-wrap: wrap;">
          <button class="btn btn-outline btn-sm" onclick="openAdminEditStudentModal(${s.id})">Edit</button>
          ${s.user_id ? `
            <button class="btn btn-outline btn-sm" onclick="openResetPasswordModal(${s.id}, 'student', '${escapeHtml(s.name)}')">Reset Login</button>
            <button class="btn ${s.user_active ? 'btn-coral' : 'btn-green'} btn-sm" onclick="toggleStudentLoginStatus(${s.id})">
              ${s.user_active ? 'Deactivate Login' : 'Activate Login'}
            </button>
          ` : ''}
          <button class="btn ${s.is_archived ? 'btn-green' : 'btn-coral'} btn-sm" onclick="toggleArchiveStudent(${s.id}, true)">
            ${s.is_archived ? 'Unarchive' : 'Archive'}
          </button>
        </div>
      </td>
    </tr>
  `).join("");
}

function openAdminAddStudentModal() {
  document.getElementById("modal-admin-student-title").textContent = "Enroll Student";
  document.getElementById("admin-student-form-id").value = "";
  document.getElementById("admin-student-form-name").value = "";
  document.getElementById("admin-student-form-class").value = "";
  document.getElementById("admin-student-form-guardian").value = "";
  document.getElementById("admin-student-form-contact").value = "";
  document.getElementById("admin-student-form-consent").checked = true;
  document.getElementById("admin-student-form-email").value = "";
  document.getElementById("admin-student-form-password").value = "";
  document.getElementById("admin-student-credentials-section").style.display = "block";
  document.getElementById("modal-admin-student").style.display = "flex";
}

function openAdminEditStudentModal(id) {
  const s = adminStudentsCache.find(x => x.id === id);
  if (!s) return;
  document.getElementById("modal-admin-student-title").textContent = "Edit Student";
  document.getElementById("admin-student-form-id").value = s.id;
  document.getElementById("admin-student-form-name").value = s.name;
  document.getElementById("admin-student-form-class").value = s.class_name;
  document.getElementById("admin-student-form-teacher").value = s.assigned_teacher_id || "";
  document.getElementById("admin-student-form-guardian").value = s.guardian_name;
  document.getElementById("admin-student-form-contact").value = s.guardian_contact;
  document.getElementById("admin-student-form-consent").checked = (s.consent_given === 1);
  document.getElementById("admin-student-form-email").value = s.student_email || "";
  document.getElementById("admin-student-credentials-section").style.display = s.user_id ? "block" : "none";
  document.getElementById("admin-student-password-group").style.display = "none";
  document.getElementById("modal-admin-student").style.display = "flex";
}

function closeAdminStudentModal() {
  document.getElementById("modal-admin-student").style.display = "none";
}

async function saveAdminStudent(e) {
  e.preventDefault();
  const id = document.getElementById("admin-student-form-id").value;
  const name = document.getElementById("admin-student-form-name").value.trim();
  const class_name = document.getElementById("admin-student-form-class").value.trim();
  const teacherVal = document.getElementById("admin-student-form-teacher").value;
  const assigned_teacher_id = teacherVal ? parseInt(teacherVal) : null;
  const guardian_name = document.getElementById("admin-student-form-guardian").value.trim();
  const guardian_contact = document.getElementById("admin-student-form-contact").value.trim();
  const consent_given = document.getElementById("admin-student-form-consent").checked;
  const email = document.getElementById("admin-student-form-email").value.trim();

  try {
    if (id) {
      await apiFetch(`/api/admin/students/${id}`, {
        method: "PUT",
        body: JSON.stringify({ name, class_name, assigned_teacher_id, guardian_name, guardian_contact, consent_given, email: email || null })
      });
    } else {
      const password = document.getElementById("admin-student-form-password").value;
      await apiFetch("/api/admin/students", {
        method: "POST",
        body: JSON.stringify({ name, class_name, assigned_teacher_id, guardian_name, guardian_contact, consent_given, email: email || null, password: password || null })
      });
    }
    closeAdminStudentModal();
    loadAdminStudents();
  } catch (err) {
    alert(err.message);
  }
}

async function toggleStudentLoginStatus(studentId) {
  try {
    await apiFetch(`/api/admin/students/${studentId}/toggle-status`, { method: "POST" });
    loadAdminStudents();
  } catch (err) {
    alert(err.message);
  }
}

function openResetPasswordModal(targetId, targetType, targetName) {
  document.getElementById("reset-target-id").value = targetId;
  document.getElementById("reset-target-type").value = targetType;
  document.getElementById("reset-target-name").textContent = `Setting new password for ${targetType}: "${targetName}".`;
  document.getElementById("reset-new-password").value = "";
  document.getElementById("modal-reset-password").style.display = "flex";
}

function closeResetPasswordModal() {
  document.getElementById("modal-reset-password").style.display = "none";
}

async function handleAdminResetPassword(e) {
  e.preventDefault();
  const targetId = document.getElementById("reset-target-id").value;
  const targetType = document.getElementById("reset-target-type").value;
  const new_password = document.getElementById("reset-new-password").value;

  try {
    const endpoint = targetType === "teacher" 
      ? `/api/admin/teachers/${targetId}/reset-password`
      : `/api/admin/students/${targetId}/reset-password`;

    const res = await apiFetch(endpoint, {
      method: "POST",
      body: JSON.stringify({ new_password })
    });
    alert(res.message || "Password successfully reset.");
    closeResetPasswordModal();
  } catch (err) {
    alert(err.message);
  }
}

async function loadAuditLogs() {
  try {
    const logs = await apiFetch("/api/admin/audit-logs?limit=50");
    const tbody = document.getElementById("admin-audit-table-body");
    if (!logs || logs.length === 0) {
      tbody.innerHTML = `<tr><td colspan="5"><div class="empty-state"><span class="empty-state-icon">📜</span><div class="empty-state-title">No Audit Logs Yet</div><p class="empty-state-desc">System actions, logins, and well-being record access will be logged here.</p></div></td></tr>`;
      return;
    }

    tbody.innerHTML = logs.map(l => {
      const dateStr = new Date(l.timestamp).toLocaleString();
      return `
        <tr>
          <td style="font-size: 0.8rem; color: var(--text-muted); white-space: nowrap;">${dateStr}</td>
          <td style="font-weight: 500;">${escapeHtml(l.user_email)}</td>
          <td><span class="badge badge-neutral" style="font-family: monospace;">${escapeHtml(l.action)}</span></td>
          <td>${escapeHtml(l.resource_type)} ${l.resource_id ? `#${l.resource_id}` : ''}</td>
          <td style="font-size: 0.85rem;">${escapeHtml(l.details)}</td>
        </tr>
      `;
    }).join("");
  } catch (err) {
    console.error("Failed to load audit logs:", err);
  }
}

// ----------------- Teacher Section -----------------

async function loadTeacherDashboard() {
  try {
    const data = await apiFetch("/api/dashboard");

    if (data.is_empty) {
      document.getElementById("dash-total-students").textContent = "0";
      document.getElementById("dash-class-average").textContent = "0%";
      document.getElementById("dash-open-alerts").textContent = "0";
      document.getElementById("attention-list-container").innerHTML = `
        <div class="empty-state">
          <span class="empty-state-icon">👥</span>
          <div class="empty-state-title">No Students Assigned Yet</div>
          <p class="empty-state-desc">Your account has no students assigned to your classes yet. Contact your administrator or enroll students.</p>
        </div>
      `;
      renderWellbeingChart({"Thriving": 0, "Doing okay": 0, "May benefit from support": 0});
      return;
    }

    document.getElementById("dash-total-students").textContent = data.total_students;
    document.getElementById("dash-class-average").textContent = data.class_average_mark + "%";
    document.getElementById("dash-open-alerts").textContent = data.open_alerts_count;

    const alertBadge = document.getElementById("nav-alert-badge");
    if (data.open_alerts_count > 0) {
      alertBadge.textContent = data.open_alerts_count;
      alertBadge.style.display = "inline-block";
    } else {
      alertBadge.style.display = "none";
    }

    const assigned = currentUser.assigned_classes ? currentUser.assigned_classes.split(",").join(" & ") : "assigned classes";
    document.getElementById("dash-classes-sub").textContent = `Active in ${assigned}`;

    const dist = data.wellbeing_distribution;
    document.getElementById("count-thriving").textContent = dist["Thriving"] || 0;
    document.getElementById("count-okay").textContent = dist["Doing okay"] || 0;
    document.getElementById("count-support").textContent = dist["May benefit from support"] || 0;

    renderWellbeingChart(dist);

    const attentionList = data.students_need_attention || [];
    const container = document.getElementById("attention-list-container");
    const countBadge = document.getElementById("attention-count-badge");
    countBadge.textContent = `${attentionList.length} flagged`;

    if (attentionList.length === 0) {
      container.innerHTML = `
        <div class="empty-state">
          <span class="empty-state-icon">🎉</span>
          <div class="empty-state-title">All Students on Track</div>
          <p class="empty-state-desc">All enrolled students in your classes are currently on track and thriving.</p>
        </div>
      `;
    } else {
      container.innerHTML = attentionList.map(st => `
        <div style="display: flex; justify-content: space-between; align-items: center; padding: 0.85rem 0.5rem; border-bottom: 1px solid var(--border-color);">
          <div>
            <div style="display: flex; align-items: center; gap: 0.5rem;">
              <strong>${escapeHtml(st.name)}</strong>
              <span class="badge badge-neutral" style="font-size: 0.72rem;">${escapeHtml(st.class_name)}</span>
              ${st.has_urgent ? `<span class="badge badge-urgent" style="font-size: 0.7rem;">🚨 Urgent</span>` : ''}
              <span class="badge ${st.badge_class}" style="font-size: 0.72rem;">${st.support_level}</span>
            </div>
            <div style="font-size: 0.8rem; color: var(--text-muted); margin-top: 0.25rem;">
              ${escapeHtml(st.summary_reason)}
            </div>
          </div>
          <button class="btn btn-outline btn-sm" onclick="viewStudentProfile(${st.id})">Profile →</button>
        </div>
      `).join("");
    }
  } catch (err) {
    console.error("Dashboard error:", err);
  }
}

function renderWellbeingChart(dist) {
  const ctx = document.getElementById("wellbeingDistributionChart").getContext("2d");
  if (wellbeingChartInstance) {
    wellbeingChartInstance.destroy();
  }

  wellbeingChartInstance = new Chart(ctx, {
    type: "bar",
    data: {
      labels: ["Thriving", "Doing okay", "May benefit support"],
      datasets: [{
        label: "Students",
        data: [
          dist["Thriving"] || 0,
          dist["Doing okay"] || 0,
          dist["May benefit from support"] || 0
        ],
        backgroundColor: [
          "rgba(16, 185, 129, 0.7)",
          "rgba(245, 158, 11, 0.7)",
          "rgba(251, 113, 133, 0.7)"
        ],
        borderColor: ["#10b981", "#f59e0b", "#fb7185"],
        borderWidth: 1.5,
        borderRadius: 8
      }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: { legend: { display: false } },
      scales: {
        y: {
          beginAtZero: true,
          ticks: { stepSize: 1, color: "#94a3b8" },
          grid: { color: "rgba(255, 255, 255, 0.05)" }
        },
        x: {
          ticks: { color: "#94a3b8" },
          grid: { display: false }
        }
      }
    }
  });
}

// Teacher Students List
let teacherStudentsCache = [];

async function loadTeacherStudents() {
  try {
    const [classes, students] = await Promise.all([
      apiFetch("/api/classes"),
      apiFetch("/api/students?include_archived=true")
    ]);
    teacherStudentsCache = students;

    const classSelect = document.getElementById("teacher-class-filter");
    const modalClassSelect = document.getElementById("teacher-student-form-class");

    classSelect.innerHTML = `<option value="">All My Classes</option>` + classes.map(c => `<option value="${c}">${c}</option>`).join("");
    modalClassSelect.innerHTML = classes.map(c => `<option value="${c}">${c}</option>`).join("");

    renderTeacherStudentsTable(teacherStudentsCache);
  } catch (err) {
    console.error("Error loading teacher students:", err);
  }
}

function filterTeacherStudents() {
  const query = document.getElementById("teacher-student-search").value.toLowerCase().trim();
  const selectedClass = document.getElementById("teacher-class-filter").value;
  const includeArchived = document.getElementById("teacher-include-archived").checked;

  const filtered = teacherStudentsCache.filter(st => {
    if (!includeArchived && st.is_archived) return false;
    if (selectedClass && st.class_name !== selectedClass) return false;
    if (query) {
      const matchName = st.name.toLowerCase().includes(query);
      const matchGuardian = (st.guardian_name || "").toLowerCase().includes(query);
      return matchName || matchGuardian;
    }
    return true;
  });

  renderTeacherStudentsTable(filtered);
}

function renderTeacherStudentsTable(students) {
  const tbody = document.getElementById("teacher-students-table-body");
  if (!students || students.length === 0) {
    tbody.innerHTML = `
      <tr>
        <td colspan="7">
          <div class="empty-state">
            <span class="empty-state-icon">👥</span>
            <div class="empty-state-title">No Students Found</div>
            <p class="empty-state-desc">No students are currently enrolled in your classes matching this filter.</p>
            <button class="btn btn-primary btn-sm" onclick="openTeacherAddStudentModal()">+ Enroll Student</button>
          </div>
        </td>
      </tr>
    `;
    return;
  }

  tbody.innerHTML = students.map(st => {
    const isArchived = st.is_archived === 1;
    return `
      <tr style="${isArchived ? 'opacity: 0.6;' : ''}">
        <td>
          <div style="font-weight: 600;">${escapeHtml(st.name)}</div>
          <div style="font-size: 0.75rem; color: var(--text-dim);">Added on ${new Date(st.created_at).toLocaleDateString()}</div>
        </td>
        <td><span class="badge badge-neutral">${escapeHtml(st.class_name)}</span></td>
        <td>
          <div>${escapeHtml(st.guardian_name)}</div>
          <div style="font-size: 0.75rem; color: var(--text-muted);">${escapeHtml(st.guardian_contact)}</div>
        </td>
        <td>
          ${st.consent_given ? '<span class="badge badge-green">Consent ✓</span>' : '<span class="badge badge-coral">Pending</span>'}
        </td>
        <td>
          <span class="badge ${st.badge_class}" title="${escapeHtml(st.support_reason || '')}">
            ${escapeHtml(st.support_level)}
          </span>
          <div style="font-size: 0.75rem; color: var(--text-dim); margin-top: 2px;">
            ${escapeHtml(st.support_reason || '')}
          </div>
        </td>
        <td>
          ${isArchived ? '<span class="badge badge-coral">Archived</span>' : '<span class="badge badge-green">Active</span>'}
        </td>
        <td>
          <div style="display: flex; gap: 0.35rem;">
            <button class="btn btn-primary btn-sm" onclick="viewStudentProfile(${st.id})">Profile</button>
            <button class="btn btn-outline btn-sm" onclick="openTeacherEditStudentModal(${st.id})">Edit</button>
            <button class="btn ${isArchived ? 'btn-green' : 'btn-coral'} btn-sm" onclick="toggleArchiveStudent(${st.id}, false)">
              ${isArchived ? 'Unarchive' : 'Archive'}
            </button>
          </div>
        </td>
      </tr>
    `;
  }).join("");
}

function openTeacherAddStudentModal() {
  document.getElementById("modal-teacher-student-title").textContent = "Add Student";
  document.getElementById("teacher-student-form-id").value = "";
  document.getElementById("teacher-student-form-name").value = "";
  document.getElementById("teacher-student-form-guardian").value = "";
  document.getElementById("teacher-student-form-contact").value = "";
  document.getElementById("teacher-student-form-consent").checked = true;
  document.getElementById("modal-teacher-student").style.display = "flex";
}

function openTeacherEditStudentModal(id) {
  const st = teacherStudentsCache.find(s => s.id === id);
  if (!st) return;
  document.getElementById("modal-teacher-student-title").textContent = "Edit Student";
  document.getElementById("teacher-student-form-id").value = st.id;
  document.getElementById("teacher-student-form-name").value = st.name;
  document.getElementById("teacher-student-form-class").value = st.class_name;
  document.getElementById("teacher-student-form-guardian").value = st.guardian_name;
  document.getElementById("teacher-student-form-contact").value = st.guardian_contact;
  document.getElementById("teacher-student-form-consent").checked = (st.consent_given === 1);
  document.getElementById("modal-teacher-student").style.display = "flex";
}

function closeTeacherStudentModal() {
  document.getElementById("modal-teacher-student").style.display = "none";
}

async function saveTeacherStudent(e) {
  e.preventDefault();
  const id = document.getElementById("teacher-student-form-id").value;
  const name = document.getElementById("teacher-student-form-name").value.trim();
  const class_name = document.getElementById("teacher-student-form-class").value;
  const guardian_name = document.getElementById("teacher-student-form-guardian").value.trim();
  const guardian_contact = document.getElementById("teacher-student-form-contact").value.trim();
  const consent_given = document.getElementById("teacher-student-form-consent").checked;

  const payload = { name, class_name, guardian_name, guardian_contact, consent_given };

  try {
    if (id) {
      await apiFetch(`/api/students/${id}`, { method: "PUT", body: JSON.stringify(payload) });
    } else {
      await apiFetch("/api/students", { method: "POST", body: JSON.stringify(payload) });
    }
    closeTeacherStudentModal();
    loadTeacherStudents();
  } catch (err) {
    alert(err.message);
  }
}

async function toggleArchiveStudent(id, isAdmin = false) {
  if (!confirm("Are you sure? (Students are safely archived and preserved in the database)")) return;
  try {
    await apiFetch(`/api/students/${id}/archive`, { method: "POST" });
    if (isAdmin) loadAdminStudents();
    else loadTeacherStudents();
  } catch (err) {
    alert(err.message);
  }
}

// ----------------- Student Profile View -----------------

function viewStudentProfile(studentId) {
  activeStudentProfileId = studentId;
  navigate("student-profile");
}

function returnFromStudentProfile() {
  if (currentUser && currentUser.role === "admin") {
    navigate("admin-students");
  } else {
    navigate("teacher-students");
  }
}

async function loadStudentProfile(studentId) {
  try {
    const data = await apiFetch(`/api/students/${studentId}`);
    const st = data.student;

    document.getElementById("profile-student-name").textContent = st.name;
    document.getElementById("profile-class-badge").textContent = st.class_name;
    document.getElementById("profile-guardian-info").textContent = `Guardian: ${st.guardian_name} (${st.guardian_contact})`;
    document.getElementById("profile-last-updated").textContent = `Profile verified: ${new Date().toLocaleTimeString()}`;

    if (st.teacher_name) {
      document.getElementById("profile-teacher-assigned").textContent = `Assigned Teacher: ${st.teacher_name}`;
    }

    const consentEl = document.getElementById("profile-consent-badge");
    if (st.consent_given) {
      consentEl.className = "badge badge-green";
      consentEl.textContent = "Consent Given ✓";
    } else {
      consentEl.className = "badge badge-coral";
      consentEl.textContent = "Consent Pending";
    }

    // Support Level (Rule B)
    const sup = data.support_info;
    const badgeEl = document.getElementById("profile-support-badge");
    badgeEl.className = `badge ${sup.badge_class}`;
    badgeEl.textContent = sup.level;
    document.getElementById("profile-support-reason").textContent = sup.reason;

    // Gaps (Rule C)
    const gapsContainer = document.getElementById("profile-gaps-container");
    const gaps = data.learning_gaps || [];
    if (gaps.length === 0) {
      gapsContainer.innerHTML = `<span class="badge badge-green" style="padding: 0.4rem 0.8rem;">No learning gaps identified. All subjects above benchmark!</span>`;
    } else {
      gapsContainer.innerHTML = gaps.map(g => `
        <div class="chip chip-gap">
          <strong>⚠️ ${escapeHtml(g.subject)}:</strong>
          <span>${escapeHtml(g.reason)}</span>
        </div>
      `).join("");
    }

    // Recommendations (Rule F)
    const recsContainer = document.getElementById("profile-recommendations-container");
    const recs = data.recommendations || [];
    recsContainer.innerHTML = recs.map(r => `
      <div style="background-color: var(--bg-elevated); padding: 1rem; border-radius: var(--radius-sm); border-left: 3px solid ${r.type === 'academic' ? 'var(--secondary)' : 'var(--primary)'};">
        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.35rem;">
          <strong style="color: var(--text-main); font-size: 0.95rem;">${escapeHtml(r.title)}</strong>
          <span class="badge badge-neutral" style="font-size: 0.72rem;">${escapeHtml(r.category)}</span>
        </div>
        <p style="color: var(--text-muted); font-size: 0.88rem; line-height: 1.5;">${escapeHtml(r.action)}</p>
      </div>
    `).join("");

    // Observations & Follow-ups (Stored in DB)
    renderObservations(data.observations || []);

    // Academic performance chart
    renderStudentAcademicChart(data.assessments || []);

    // Assessments table
    const assessBody = document.getElementById("profile-assessments-body");
    const assessments = data.assessments || [];
    if (assessments.length === 0) {
      assessBody.innerHTML = `<tr><td colspan="5"><div class="empty-state" style="padding: 1.5rem;"><span class="empty-state-icon">📝</span><div class="empty-state-title">No Assessments Recorded</div><p class="empty-state-desc">Click "+ Record Assessment Mark" to log academic tests.</p></div></td></tr>`;
    } else {
      assessBody.innerHTML = assessments.map(a => {
        const pct = Math.round((a.score / (a.max_score || 100)) * 100);
        const isLow = pct < 40;
        return `
          <tr>
            <td>${escapeHtml(a.date)}</td>
            <td><strong>${escapeHtml(a.subject)}</strong></td>
            <td>${a.score} / ${a.max_score || 100}</td>
            <td><span class="badge ${isLow ? 'badge-coral' : 'badge-green'}">${pct}%</span></td>
            <td style="color: var(--text-muted);">${escapeHtml(a.notes || '—')}</td>
          </tr>
        `;
      }).join("");
    }

    // Checkins table (Fernet decrypted)
    const checkinsBody = document.getElementById("profile-checkins-body");
    const checkins = data.checkins || [];
    if (checkins.length === 0) {
      checkinsBody.innerHTML = `<tr><td colspan="8"><div class="empty-state" style="padding: 1.5rem;"><span class="empty-state-icon">🌱</span><div class="empty-state-title">No Check-in Records</div><p class="empty-state-desc">Student has not submitted any MindMate check-ins yet.</p></div></td></tr>`;
    } else {
      checkinsBody.innerHTML = checkins.map(c => {
        const dateStr = new Date(c.created_at).toLocaleDateString();
        return `
          <tr>
            <td style="white-space: nowrap; color: var(--text-muted);">${dateStr}</td>
            <td><strong style="font-size: 1rem; color: #a855f7;">${c.score.toFixed(1)} / 5</strong></td>
            <td>${c.mood}/5</td>
            <td>${6 - c.stress}/5 <span style="font-size: 0.7rem; color: var(--text-dim);">(raw: ${c.stress})</span></td>
            <td>${c.sleep}/5</td>
            <td>${c.focus}/5</td>
            <td>${c.belonging}/5</td>
            <td style="font-size: 0.85rem; max-width: 280px;">
              ${c.note ? `<em>"${escapeHtml(c.note)}"</em>` : '<span style="color: var(--text-dim);">No note</span>'}
            </td>
          </tr>
        `;
      }).join("");
    }
  } catch (err) {
    alert(err.message);
    returnFromStudentProfile();
  }
}

function renderObservations(observations) {
  const container = document.getElementById("profile-observations-container");
  if (!observations || observations.length === 0) {
    container.innerHTML = `
      <div class="empty-state" style="padding: 1.5rem;">
        <span class="empty-state-icon">📋</span>
        <div class="empty-state-title">No Observations Logged</div>
        <p class="empty-state-desc">Click "+ Add Observation" to record behavioral notes and track caring follow-up plans.</p>
      </div>
    `;
    return;
  }

  container.innerHTML = observations.map(o => `
    <div style="background-color: var(--bg-elevated); padding: 1rem; border-radius: var(--radius-sm); border: 1px solid var(--border-color);">
      <div style="display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 0.5rem; flex-wrap: wrap; gap: 0.5rem;">
        <div>
          <span class="badge ${o.status === 'completed' ? 'badge-green' : 'badge-amber'}">
            ${escapeHtml(o.status.toUpperCase())}
          </span>
          <span style="font-size: 0.8rem; color: var(--text-dim); margin-left: 0.5rem;">
            Logged by ${escapeHtml(o.teacher_name)} on ${new Date(o.created_at).toLocaleDateString()}
          </span>
        </div>
        <button class="btn btn-outline btn-sm" onclick="toggleObservationStatus(${o.id}, '${o.status === 'completed' ? 'pending' : 'completed'}')">
          Mark as ${o.status === 'completed' ? 'Pending' : 'Completed ✓'}
        </button>
      </div>
      <p style="font-size: 0.92rem; color: var(--text-main); margin-bottom: 0.5rem;">${escapeHtml(o.observation_text)}</p>
      ${o.follow_up_action ? `
        <div style="font-size: 0.85rem; color: var(--primary); background: var(--primary-light); padding: 0.5rem 0.75rem; border-radius: var(--radius-sm);">
          <strong>Follow-up Action:</strong> ${escapeHtml(o.follow_up_action)}
        </div>
      ` : ''}
    </div>
  `).join("");
}

function openAddObservationModal() {
  document.getElementById("obs-student-id").value = activeStudentProfileId;
  document.getElementById("obs-text").value = "";
  document.getElementById("obs-action").value = "";
  document.getElementById("obs-status").value = "pending";
  document.getElementById("modal-observation").style.display = "flex";
}

function closeObservationModal() {
  document.getElementById("modal-observation").style.display = "none";
}

async function saveObservation(e) {
  e.preventDefault();
  const student_id = document.getElementById("obs-student-id").value;
  const observation_text = document.getElementById("obs-text").value.trim();
  const follow_up_action = document.getElementById("obs-action").value.trim();
  const status = document.getElementById("obs-status").value;

  try {
    await apiFetch(`/api/students/${student_id}/observations`, {
      method: "POST",
      body: JSON.stringify({ observation_text, follow_up_action, status })
    });
    closeObservationModal();
    loadStudentProfile(student_id);
  } catch (err) {
    alert(err.message);
  }
}

async function toggleObservationStatus(obsId, newStatus) {
  try {
    await apiFetch(`/api/observations/${obsId}/status`, {
      method: "PUT",
      body: JSON.stringify({ status: newStatus })
    });
    if (activeStudentProfileId) {
      loadStudentProfile(activeStudentProfileId);
    }
  } catch (err) {
    alert(err.message);
  }
}

function renderStudentAcademicChart(assessments) {
  const ctx = document.getElementById("studentAcademicChart").getContext("2d");
  if (studentChartInstance) {
    studentChartInstance.destroy();
  }

  const subjects = ["Mathematics", "Science", "English", "History"];
  const colorMap = {
    "Mathematics": "#3b82f6",
    "Science": "#10b981",
    "English": "#8b5cf6",
    "History": "#f59e0b"
  };

  const dates = Array.from(new Set(assessments.map(a => a.date))).sort();

  const datasets = subjects.map(subj => {
    const dataPoints = dates.map(d => {
      const match = assessments.find(a => a.subject === subj && a.date === d);
      return match ? Math.round((match.score / (match.max_score || 100)) * 100) : null;
    });

    return {
      label: subj,
      data: dataPoints,
      borderColor: colorMap[subj] || "#94a3b8",
      backgroundColor: colorMap[subj] || "#94a3b8",
      tension: 0.3,
      spanGaps: true,
      borderWidth: 2,
      pointRadius: 4
    };
  });

  studentChartInstance = new Chart(ctx, {
    type: "line",
    data: { labels: dates, datasets: datasets },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: { legend: { position: "top", labels: { color: "#94a3b8" } } },
      scales: {
        y: {
          min: 0,
          max: 100,
          ticks: { color: "#94a3b8", callback: v => v + "%" },
          grid: { color: "rgba(255, 255, 255, 0.05)" }
        },
        x: { ticks: { color: "#94a3b8" }, grid: { display: false } }
      }
    }
  });
}

function openAddMarkModal() {
  document.getElementById("mark-form-student-id").value = activeStudentProfileId;
  document.getElementById("mark-form-score").value = "";
  document.getElementById("mark-form-notes").value = "";
  document.getElementById("mark-form-date").value = new Date().toISOString().split("T")[0];
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
  const max_score = parseFloat(document.getElementById("mark-form-max").value) || 100.0;
  const date = document.getElementById("mark-form-date").value;
  const notes = document.getElementById("mark-form-notes").value.trim();

  try {
    await apiFetch("/api/assessments", {
      method: "POST",
      body: JSON.stringify({ student_id, subject, score, max_score, date, notes })
    });
    closeAddMarkModal();
    loadStudentProfile(student_id);
  } catch (err) {
    alert(err.message);
  }
}

// ----------------- Teacher Alerts -----------------

let teacherAlertsCache = [];

async function loadTeacherAlerts() {
  try {
    teacherAlertsCache = await apiFetch("/api/alerts");
    renderAlertsList("all");
  } catch (err) {
    console.error("Error loading alerts:", err);
  }
}

function filterAlerts(status) {
  document.querySelectorAll("#view-teacher-alerts .card-title button").forEach(b => b.classList.remove("active"));
  const btn = document.getElementById(`filter-alert-${status}`);
  if (btn) btn.classList.add("active");
  renderAlertsList(status);
}

function renderAlertsList(statusFilter) {
  const container = document.getElementById("alerts-list-container");
  const filtered = teacherAlertsCache.filter(a => statusFilter === "all" || a.status === statusFilter);

  if (filtered.length === 0) {
    container.innerHTML = `
      <div class="empty-state">
        <span class="empty-state-icon">✅</span>
        <div class="empty-state-title">No Alerts in this View</div>
        <p class="empty-state-desc">There are no open or flagged alerts matching this filter category.</p>
      </div>
    `;
    return;
  }

  container.innerHTML = filtered.map(a => {
    const isUrgent = a.severity === "urgent";
    const statusBadges = {
      open: "badge-coral",
      acknowledged: "badge-amber",
      snoozed: "badge-neutral",
      resolved: "badge-green"
    };

    return `
      <div class="card" style="margin-bottom: 0; ${isUrgent ? 'border: 2px solid var(--status-urgent); background-color: rgba(244, 63, 94, 0.04);' : ''}">
        <div style="display: flex; justify-content: space-between; align-items: flex-start; flex-wrap: wrap; gap: 0.75rem;">
          <div>
            <div style="display: flex; align-items: center; gap: 0.5rem; flex-wrap: wrap;">
              <h3 style="font-size: 1.1rem; color: var(--text-main);">${escapeHtml(a.title)}</h3>
              ${isUrgent ? '<span class="badge badge-urgent">🚨 URGENT SAFEGUARDING</span>' : ''}
              <span class="badge ${statusBadges[a.status] || 'badge-neutral'}">${a.status.toUpperCase()}</span>
            </div>
            <div style="font-size: 0.8rem; color: var(--text-dim); margin-top: 0.2rem;">
              Student: <strong>${escapeHtml(a.student_name)}</strong> (${escapeHtml(a.class_name)}) • Triggered: ${new Date(a.created_at).toLocaleString()}
            </div>
          </div>
          <div style="display: flex; gap: 0.4rem; flex-wrap: wrap;">
            ${a.status !== 'acknowledged' && a.status !== 'resolved' ? `
              <button class="btn btn-outline btn-sm" onclick="changeAlertStatus(${a.id}, 'acknowledged')">Acknowledge</button>
            ` : ''}
            ${a.status !== 'snoozed' && a.status !== 'resolved' ? `
              <button class="btn btn-outline btn-sm" onclick="changeAlertStatus(${a.id}, 'snoozed')">Snooze</button>
            ` : ''}
            ${a.status !== 'resolved' ? `
              <button class="btn btn-green btn-sm" onclick="changeAlertStatus(${a.id}, 'resolved')">✓ Resolve</button>
            ` : `
              <span class="badge badge-green">Resolved</span>
            `}
          </div>
        </div>

        <div style="margin-top: 0.85rem; font-size: 0.92rem; color: var(--text-muted); line-height: 1.5;">
          ${escapeHtml(a.message)}
        </div>

        ${isUrgent ? `
          <div class="alert-box alert-urgent" style="margin-top: 0.85rem; margin-bottom: 0;">
            <span style="font-size: 1.2rem;">🛡️</span>
            <div>
              <strong>Required Safeguarding Action:</strong>
              Speak with the student privately today, follow your school's safeguarding policy and involve the counsellor.
            </div>
          </div>
        ` : ''}
      </div>
    `;
  }).join("");
}

async function changeAlertStatus(alertId, newStatus) {
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

// ----------------- Student Portal Section -----------------

async function loadStudentPortal() {
  try {
    const data = await apiFetch("/api/dashboard");
    if (!data.student) {
      document.getElementById("student-portal-welcome").textContent = "Welcome to MindMate!";
      return;
    }

    const st = data.student;
    document.getElementById("student-portal-welcome").textContent = `Welcome, ${st.name}! (${st.class_name})`;

    // Support indicator
    const sup = data.support_info;
    const badge = document.getElementById("student-support-badge");
    badge.className = `badge ${sup.badge_class}`;
    badge.textContent = sup.level;

    const heading = document.getElementById("student-wellbeing-heading");
    const desc = document.getElementById("student-wellbeing-desc");
    const emoji = document.getElementById("student-wellbeing-emoji");

    if (sup.level === "Thriving") {
      emoji.textContent = "🌟";
      heading.textContent = "You're Thriving!";
      desc.textContent = "Your check-ins show balanced energy, focus, and positive connection. Keep up your wonderful momentum!";
    } else if (sup.level === "Doing okay") {
      emoji.textContent = "🌱";
      heading.textContent = "You're Doing Okay";
      desc.textContent = "Some days feel great, and some days feel busy. Your teachers are here to support your learning every step of the way.";
    } else {
      emoji.textContent = "💛";
      heading.textContent = "We're Here For You";
      desc.textContent = "It looks like school or stress might be weighing on you. Remember you don't have to carry it alone — talk to your teacher or trusted adult.";
    }

    // Assessments
    const assessContainer = document.getElementById("student-assessments-container");
    const assessments = data.assessments || [];
    if (assessments.length === 0) {
      assessContainer.innerHTML = `<div class="empty-state" style="padding:1rem;"><p>No assessment marks logged yet.</p></div>`;
    } else {
      assessContainer.innerHTML = assessments.map(a => `
        <div style="display: flex; justify-content: space-between; align-items: center; padding: 0.6rem 0; border-bottom: 1px solid var(--border-color);">
          <div>
            <strong>${escapeHtml(a.subject)}</strong>
            <span style="font-size:0.75rem; color:var(--text-muted); margin-left: 0.5rem;">${escapeHtml(a.date)}</span>
          </div>
          <div>
            <span class="badge ${Math.round((a.score/(a.max_score||100))*100) < 40 ? 'badge-coral' : 'badge-green'}">
              ${a.score} / ${a.max_score || 100} (${Math.round((a.score/(a.max_score||100))*100)}%)
            </span>
          </div>
        </div>
      `).join("");
    }

    // Recommendations & Guidance
    const recContainer = document.getElementById("student-recommendations-container");
    const recs = data.recommendations || [];
    if (recs.length === 0) {
      recContainer.innerHTML = `<p style="color:var(--text-muted);">Keep learning at your own pace and reach out to your teacher with questions.</p>`;
    } else {
      recContainer.innerHTML = recs.map(r => `
        <div style="background-color: var(--bg-elevated); padding: 0.85rem 1rem; border-radius: var(--radius-sm); border-left: 3px solid var(--primary);">
          <strong>${escapeHtml(r.title)}</strong>
          <p style="font-size: 0.85rem; color: var(--text-muted); margin-top: 0.25rem;">${escapeHtml(r.action)}</p>
        </div>
      `).join("");
    }
  } catch (err) {
    console.error("Student portal load failed:", err);
  }
}

// Student Self Check-in
const EMOJI_SETS = {
  mood: [
    { val: 1, icon: "😞", label: "Very Low" },
    { val: 2, icon: "🙁", label: "Down" },
    { val: 3, icon: "😐", label: "Okay" },
    { val: 4, icon: "🙂", label: "Good" },
    { val: 5, icon: "😄", label: "Great" }
  ],
  stress: [
    { val: 1, icon: "😌", label: "Calm" },
    { val: 2, icon: "🙂", label: "Low" },
    { val: 3, icon: "😐", label: "Moderate" },
    { val: 4, icon: "😟", label: "High" },
    { val: 5, icon: "😫", label: "Overwhelmed" }
  ],
  sleep: [
    { val: 1, icon: "🥱", label: "Very Poor" },
    { val: 2, icon: "😴", label: "Restless" },
    { val: 3, icon: "😐", label: "Fair" },
    { val: 4, icon: "🛏️", label: "Good" },
    { val: 5, icon: "🌟", label: "Refreshed" }
  ],
  focus: [
    { val: 1, icon: "🌫️", label: "Hard" },
    { val: 2, icon: "💭", label: "Distracted" },
    { val: 3, icon: "😐", label: "Okay" },
    { val: 4, icon: "🎯", label: "Focused" },
    { val: 5, icon: "🚀", label: "Sharp" }
  ],
  belonging: [
    { val: 1, icon: "👤", label: "Alone" },
    { val: 2, icon: "🌧️", label: "Isolated" },
    { val: 3, icon: "😐", label: "Neutral" },
    { val: 4, icon: "🤝", label: "Supported" },
    { val: 5, icon: "💛", label: "Valued" }
  ]
};

function openStudentSelfCheckinModal() {
  ["mood", "stress", "sleep", "focus", "belonging"].forEach(f => {
    selfCheckinAnswers[f] = null;
    renderSelfCheckinOptions(f);
  });
  document.getElementById("self-checkin-note").value = "";
  document.getElementById("self-checkin-error").style.display = "none";
  document.getElementById("modal-self-checkin").style.display = "flex";
}

function closeStudentSelfCheckinModal() {
  document.getElementById("modal-self-checkin").style.display = "none";
}

function renderSelfCheckinOptions(field) {
  const container = document.getElementById(`self-q-${field}`);
  const currentVal = selfCheckinAnswers[field];
  container.innerHTML = EMOJI_SETS[field].map(opt => `
    <button type="button" class="emoji-btn ${currentVal === opt.val ? 'selected' : ''}" onclick="selectSelfCheckinOption('${field}', ${opt.val})">
      <span class="emoji-icon">${opt.icon}</span>
      <span class="emoji-label">${opt.label}</span>
    </button>
  `).join("");
}

function selectSelfCheckinOption(field, val) {
  selfCheckinAnswers[field] = val;
  renderSelfCheckinOptions(field);
}

async function submitStudentSelfCheckin(e) {
  e.preventDefault();
  const errorEl = document.getElementById("self-checkin-error");
  errorEl.style.display = "none";

  for (let field of ["mood", "stress", "sleep", "focus", "belonging"]) {
    if (!selfCheckinAnswers[field]) {
      errorEl.textContent = `Please tap an emoji answer for question: ${field}.`;
      errorEl.style.display = "block";
      return;
    }
  }

  const note = document.getElementById("self-checkin-note").value.trim();
  const payload = { ...selfCheckinAnswers, note: note || null };

  try {
    await apiFetch("/api/students/me/checkin", {
      method: "POST",
      body: JSON.stringify(payload)
    });
    alert("Thank you! Your check-in reflection has been submitted.");
    closeStudentSelfCheckinModal();
    loadStudentPortal();
  } catch (err) {
    errorEl.textContent = err.message;
    errorEl.style.display = "block";
  }
}

// ----------------- Kiosk Check-In Mode -----------------

const KIOSK_QUESTIONS = [
  { num: 1, field: "mood", title: "How are you feeling overall today?", desc: "Tap an emoji that best represents your mood right now.", options: EMOJI_SETS.mood },
  { num: 2, field: "stress", title: "How stressed or overwhelmed do you feel?", desc: "1 is completely calm, 5 is deeply overwhelmed.", options: EMOJI_SETS.stress },
  { num: 3, field: "sleep", title: "How well did you sleep last night?", desc: "Good rest helps your energy and thinking.", options: EMOJI_SETS.sleep },
  { num: 4, field: "focus", title: "How easy is it to focus in class today?", desc: "Are you feeling dialed in or distracted?", options: EMOJI_SETS.focus },
  { num: 5, field: "belonging", title: "Do you feel supported and connected with others?", desc: "How connected do you feel to your classmates and teachers?", options: EMOJI_SETS.belonging },
  { num: 6, field: "note", title: "Anything else you want to share with your teacher?", desc: "This note is encrypted and shared privately with your teacher.", options: [] }
];

async function openKioskLauncher() {
  try {
    const students = await apiFetch("/api/students");
    const select = document.getElementById("kiosk-student-select");
    if (!students || students.length === 0) {
      alert("No students currently enrolled in your classes. Enroll a student first.");
      return;
    }
    select.innerHTML = students.map(s => `<option value="${s.id}">${s.name} (${s.class_name})</option>`).join("");

    document.getElementById("kiosk-teacher-pin").value = "";
    document.getElementById("kiosk-launch-error").style.display = "none";
    document.getElementById("kiosk-step-launch").style.display = "block";
    document.getElementById("kiosk-step-questions").style.display = "none";
    document.getElementById("kiosk-step-complete").style.display = "none";

    document.getElementById("kiosk-overlay").style.display = "flex";
  } catch (err) {
    alert(err.message);
  }
}

async function startKioskSession() {
  const pinInput = document.getElementById("kiosk-teacher-pin").value.trim();
  const studentSelect = document.getElementById("kiosk-student-select");
  const errorEl = document.getElementById("kiosk-launch-error");

  if (!pinInput) {
    errorEl.textContent = "Please enter your Teacher PIN.";
    errorEl.style.display = "block";
    return;
  }

  try {
    await apiFetch("/api/auth/verify-pin", {
      method: "POST",
      body: JSON.stringify({ pin: pinInput })
    });

    kioskTeacherPin = pinInput;
    kioskStudentId = parseInt(studentSelect.value);
    kioskCurrentStep = 1;

    ["mood", "stress", "sleep", "focus", "belonging"].forEach(f => kioskAnswers[f] = null);
    kioskAnswers.note = "";
    document.getElementById("kiosk-student-note").value = "";

    document.getElementById("kiosk-step-launch").style.display = "none";
    document.getElementById("kiosk-step-questions").style.display = "block";
    renderKioskStep();
  } catch (err) {
    errorEl.textContent = "Incorrect Teacher PIN. Please try again.";
    errorEl.style.display = "block";
  }
}

function renderKioskStep() {
  const q = KIOSK_QUESTIONS[kioskCurrentStep - 1];

  for (let i = 1; i <= 6; i++) {
    const dot = document.getElementById(`dot-${i}`);
    dot.className = "progress-dot";
    if (i === kioskCurrentStep) dot.classList.add("active");
    else if (i < kioskCurrentStep) dot.classList.add("done");
  }

  document.getElementById("kiosk-question-number").textContent = `Step ${kioskCurrentStep} of 6`;
  document.getElementById("kiosk-question-title").textContent = q.title;
  document.getElementById("kiosk-question-desc").textContent = q.desc;

  const emojiGrid = document.getElementById("kiosk-emoji-grid");
  const noteSection = document.getElementById("kiosk-note-section");
  const nextBtn = document.getElementById("kiosk-next-btn");
  const prevBtn = document.getElementById("kiosk-prev-btn");

  prevBtn.style.visibility = kioskCurrentStep > 1 ? "visible" : "hidden";

  if (q.field === "note") {
    emojiGrid.style.display = "none";
    noteSection.style.display = "block";
    nextBtn.disabled = false;
    nextBtn.textContent = "Submit Check-In ✓";
  } else {
    emojiGrid.style.display = "grid";
    noteSection.style.display = "none";
    nextBtn.textContent = "Continue →";

    const currentVal = kioskAnswers[q.field];
    nextBtn.disabled = (currentVal === null);

    emojiGrid.innerHTML = q.options.map(opt => `
      <button class="emoji-btn ${currentVal === opt.val ? 'selected' : ''}" onclick="selectKioskOption('${q.field}', ${opt.val})">
        <span class="emoji-icon">${opt.icon}</span>
        <span class="emoji-label">${opt.label}</span>
      </button>
    `).join("");
  }
}

function selectKioskOption(field, val) {
  kioskAnswers[field] = val;
  renderKioskStep();
}

function prevKioskQuestion() {
  if (kioskCurrentStep > 1) {
    kioskCurrentStep--;
    renderKioskStep();
  }
}

async function nextKioskQuestion() {
  if (kioskCurrentStep < 6) {
    kioskCurrentStep++;
    renderKioskStep();
  } else {
    kioskAnswers.note = document.getElementById("kiosk-student-note").value.trim();

    try {
      const payload = {
        student_id: kioskStudentId,
        mood: kioskAnswers.mood,
        stress: kioskAnswers.stress,
        sleep: kioskAnswers.sleep,
        focus: kioskAnswers.focus,
        belonging: kioskAnswers.belonging,
        note: kioskAnswers.note || null,
        teacher_pin: kioskTeacherPin
      };

      await apiFetch("/api/checkins/kiosk", {
        method: "POST",
        body: JSON.stringify(payload)
      });

      document.getElementById("kiosk-step-questions").style.display = "none";
      document.getElementById("kiosk-step-complete").style.display = "block";
    } catch (err) {
      alert("Error submitting check-in: " + err.message);
    }
  }
}

function promptKioskExit() {
  document.getElementById("prompt-exit-pin").value = "";
  document.getElementById("pin-prompt-error").style.display = "none";
  document.getElementById("modal-pin-prompt").style.display = "flex";
}

function closePinPrompt() {
  document.getElementById("modal-pin-prompt").style.display = "none";
}

async function confirmKioskExit(e) {
  e.preventDefault();
  const pin = document.getElementById("prompt-exit-pin").value.trim();
  const errorEl = document.getElementById("pin-prompt-error");

  try {
    await apiFetch("/api/auth/verify-pin", {
      method: "POST",
      body: JSON.stringify({ pin })
    });

    closePinPrompt();
    document.getElementById("kiosk-overlay").style.display = "none";
    if (currentView === "teacher-dashboard") loadTeacherDashboard();
    else if (currentView === "student-profile" && activeStudentProfileId) loadStudentProfile(activeStudentProfileId);
  } catch (err) {
    errorEl.textContent = "Incorrect Teacher PIN. Exit denied.";
    errorEl.style.display = "block";
  }
}

// ----------------- Utilities -----------------

function escapeHtml(str) {
  if (!str) return "";
  return String(str)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#039;");
}
