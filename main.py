import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, List, Dict, Any

from fastapi import FastAPI, Depends, HTTPException, status, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel, Field

from database import init_db, get_db
from crypto import encrypt_note, decrypt_note
from auth import (
    hash_password,
    verify_password,
    authenticate_user,
    create_access_token,
    get_current_user,
    check_teacher_class_access,
    check_student_record_access,
    require_teacher,
    require_admin,
    require_student,
    require_teacher_or_admin,
    GENERIC_LOGIN_ERROR,
    INACTIVE_ERROR,
    UNASSIGNED_ERROR,
)
from logic import (
    calculate_checkin_score,
    evaluate_support_level,
    evaluate_learning_gaps,
    check_safety_keywords,
    generate_recommendations,
    SAFEGUARDING_MESSAGE,
    DISCLAIMER_TEXT,
)

BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"

# Initialize SQLite database (runs migrations automatically)
init_db()

app = FastAPI(
    title="MindMate – Student Well-being & Academic Support",
    version="3.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─────────────────────────────────────────────
#  Helpers
# ─────────────────────────────────────────────

def _now() -> str:
    return datetime.now(timezone.utc).isoformat()

def write_audit_log(conn, user_id: Optional[int], user_email: str, action: str,
                    resource_type: str, resource_id: Optional[int], details: str):
    conn.execute(
        """
        INSERT INTO audit_logs (user_id, user_email, action, resource_type, resource_id, details, timestamp)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (user_id, user_email, action, resource_type, resource_id, details, _now())
    )

def _get_setting(conn, key: str, default: str = "") -> str:
    row = conn.execute("SELECT value FROM settings WHERE key = ?", (key,)).fetchone()
    return row["value"] if row else default

def _get_student_or_404(cursor, student_id: int):
    cursor.execute("SELECT * FROM students WHERE id = ?", (student_id,))
    s = cursor.fetchone()
    if not s:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Student not found.")
    return dict(s)

def _build_public_user(u: dict) -> dict:
    return {
        "id": u["id"],
        "email": u.get("email") or "",
        "username": u.get("username") or "",
        "full_name": u["full_name"],
        "role": u["role"],
        "is_active": u.get("is_active", 1),
        "assigned_classes": u.get("assigned_classes", ""),
        "check_in_pin": u.get("check_in_pin", "1234"),
        "must_change_password": u.get("must_change_password", 0),
    }

# ─────────────────────────────────────────────
#  Request Models
# ─────────────────────────────────────────────

class SetupAdminRequest(BaseModel):
    email: str
    password: str
    full_name: str

class LoginRequest(BaseModel):
    identifier: str           # email or username
    password: str
    portal: str = "teacher"   # 'admin', 'teacher', 'student'

class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str

class ForceChangePasswordRequest(BaseModel):
    new_password: str         # used when must_change_password=1 (no current needed from admin reset)

class ResetPasswordRequest(BaseModel):
    new_password: str

class PinVerifyRequest(BaseModel):
    pin: str

class TeacherCreateRequest(BaseModel):
    email: str
    password: str
    full_name: str
    assigned_classes: str = ""
    check_in_pin: str = "1234"

class TeacherUpdateRequest(BaseModel):
    email: str
    full_name: str
    assigned_classes: str = ""
    check_in_pin: str = "1234"
    is_active: bool = True

class StudentCreateRequest(BaseModel):
    name: str
    class_name: str
    roll_number: str = ""
    guardian_name: str
    guardian_contact: str
    consent_given: bool = True
    assigned_teacher_id: Optional[int] = None
    username: Optional[str] = None      # student login username
    password: Optional[str] = None

class StudentUpdateRequest(BaseModel):
    name: str
    class_name: str
    roll_number: str = ""
    guardian_name: str
    guardian_contact: str
    consent_given: bool = True
    assigned_teacher_id: Optional[int] = None
    username: Optional[str] = None

class BulkAssignRequest(BaseModel):
    student_ids: List[int]
    teacher_id: int
    reason: str = ""

class AssessmentCreateRequest(BaseModel):
    student_id: int
    subject: str
    score: float
    max_score: float = 100.0
    date: str
    notes: Optional[str] = ""

class CheckinRequest(BaseModel):
    student_id: int
    mood: int = Field(..., ge=1, le=5)
    stress: int = Field(..., ge=1, le=5)
    sleep: int = Field(..., ge=1, le=5)
    focus: int = Field(..., ge=1, le=5)
    belonging: int = Field(..., ge=1, le=5)
    note: Optional[str] = None
    teacher_pin: str

class StudentSelfCheckinRequest(BaseModel):
    mood: int = Field(..., ge=1, le=5)
    stress: int = Field(..., ge=1, le=5)
    sleep: int = Field(..., ge=1, le=5)
    focus: int = Field(..., ge=1, le=5)
    belonging: int = Field(..., ge=1, le=5)
    note: Optional[str] = None

class ObservationCreateRequest(BaseModel):
    observation_text: str
    follow_up_action: Optional[str] = ""
    status: str = "new"

class ObservationStatusRequest(BaseModel):
    status: str

class AlertStatusUpdateRequest(BaseModel):
    status: str

class SettingsUpdateRequest(BaseModel):
    safeguarding_contact_name: str = ""
    safeguarding_contact_phone: str = ""
    safeguarding_contact_email: str = ""
    reporting_window_days: int = 30
    checkin_frequency_days: int = 7

# ─────────────────────────────────────────────
#  PHASE 1 – Setup & Auth
# ─────────────────────────────────────────────

@app.get("/api/auth/setup-status")
def get_setup_status():
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) AS count FROM users WHERE role = 'admin' AND is_active = 1")
        admin_count = cursor.fetchone()["count"]
        return {"needs_setup": (admin_count == 0), "admin_count": admin_count}

@app.post("/api/auth/setup")
def setup_initial_admin(req: SetupAdminRequest):
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) AS count FROM users WHERE role = 'admin' AND is_active = 1")
        if cursor.fetchone()["count"] > 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Administrator account already established. Please sign in."
            )
        if len(req.password) < 8:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Password must be at least 8 characters.")
        now = _now()
        cursor.execute("""
            INSERT INTO users (email, username, password_hash, full_name, role, is_active,
                               assigned_classes, check_in_pin, must_change_password,
                               failed_login_attempts, lockout_until, created_at, updated_at)
            VALUES (?, NULL, ?, ?, 'admin', 1, '', '9999', 0, 0, NULL, ?, ?)
        """, (req.email.strip().lower(), hash_password(req.password), req.full_name.strip(), now, now))
        user_id = cursor.lastrowid
        cursor.execute("SELECT * FROM users WHERE id = ?", (user_id,))
        user_dict = dict(cursor.fetchone())
        token = create_access_token(user_dict)
        write_audit_log(conn, user_id, user_dict["email"], "INITIAL_ADMIN_SETUP", "USER", user_id,
                        "Initial system administrator account created.")
        return {"access_token": token, "token_type": "bearer", "user": _build_public_user(user_dict)}

@app.post("/api/auth/login")
def login(req: LoginRequest):
    portal = req.portal.strip().lower()
    if portal not in ("admin", "teacher", "student"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid portal.")

    user_dict = authenticate_user(req.identifier, req.password, portal)
    token = create_access_token(user_dict)

    # For students, attach student_id
    student_id = None
    with get_db() as conn:
        if user_dict["role"] == "student":
            row = conn.execute("SELECT id FROM students WHERE user_id = ?", (user_dict["id"],)).fetchone()
            if row:
                student_id = row["id"]

        write_audit_log(conn, user_dict["id"], user_dict.get("email") or user_dict.get("username", ""),
                        "LOGIN", "USER", user_dict["id"],
                        f"User logged in via '{portal}' portal")

    pub = _build_public_user(user_dict)
    pub["student_id"] = student_id
    return {"access_token": token, "token_type": "bearer", "user": pub}

@app.get("/api/auth/me")
def get_me(current_user: dict = Depends(get_current_user)):
    student_id = None
    class_name = None
    if current_user["role"] == "student":
        with get_db() as conn:
            row = conn.execute("SELECT id, class_name FROM students WHERE user_id = ?",
                               (current_user["id"],)).fetchone()
            if row:
                student_id = row["id"]
                class_name = row["class_name"]
    pub = _build_public_user(current_user)
    pub["student_id"] = student_id
    pub["class_name"] = class_name
    return pub

@app.post("/api/auth/change-password")
def change_password(req: ChangePasswordRequest, current_user: dict = Depends(get_current_user)):
    if len(req.new_password) < 8:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Password must be at least 8 characters.")
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT password_hash FROM users WHERE id = ?", (current_user["id"],))
        row = cursor.fetchone()
        if not row or not verify_password(req.current_password, row["password_hash"]):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Current password is incorrect.")
        now = _now()
        cursor.execute("UPDATE users SET password_hash = ?, must_change_password = 0, updated_at = ? WHERE id = ?",
                       (hash_password(req.new_password), now, current_user["id"]))
        write_audit_log(conn, current_user["id"], current_user.get("email", ""),
                        "CHANGE_PASSWORD", "USER", current_user["id"], "User changed their password.")
        return {"success": True, "message": "Password updated successfully."}

@app.post("/api/auth/force-change-password")
def force_change_password(req: ForceChangePasswordRequest, current_user: dict = Depends(get_current_user)):
    """Used when must_change_password=1. No current password needed."""
    if not current_user.get("must_change_password"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                            detail="Password change not required for this account.")
    if len(req.new_password) < 8:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Password must be at least 8 characters.")
    with get_db() as conn:
        now = _now()
        conn.execute("UPDATE users SET password_hash = ?, must_change_password = 0, updated_at = ? WHERE id = ?",
                     (hash_password(req.new_password), now, current_user["id"]))
        write_audit_log(conn, current_user["id"], current_user.get("email", ""),
                        "FORCE_CHANGE_PASSWORD", "USER", current_user["id"],
                        "User completed mandatory password change.")
        return {"success": True, "message": "Password updated. Please sign in again."}

@app.post("/api/auth/verify-pin")
def verify_check_in_pin(req: PinVerifyRequest, current_user: dict = Depends(get_current_user)):
    pin = req.pin.strip()
    stored = current_user.get("check_in_pin", "1234")
    if pin == stored:
        return {"valid": True}
    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid PIN.")

# ─────────────────────────────────────────────
#  PHASE 2 – Admin: Teachers
# ─────────────────────────────────────────────

@app.get("/api/admin/teachers")
def list_teachers(current_user: dict = Depends(require_admin)):
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT u.id, u.email, u.full_name, u.role, u.is_active, u.assigned_classes,
                   u.check_in_pin, u.created_at, u.must_change_password,
                   COUNT(s.id) AS student_count
            FROM users u
            LEFT JOIN students s ON s.assigned_teacher_id = u.id AND s.is_archived = 0
            WHERE u.role = 'teacher'
            GROUP BY u.id
            ORDER BY u.full_name ASC
        """)
        return [dict(r) for r in cursor.fetchall()]

@app.post("/api/admin/teachers", status_code=status.HTTP_201_CREATED)
def create_teacher(req: TeacherCreateRequest, current_user: dict = Depends(require_admin)):
    if len(req.password) < 8:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Password must be at least 8 characters.")
    with get_db() as conn:
        cursor = conn.cursor()
        email_clean = req.email.strip().lower()
        cursor.execute("SELECT id FROM users WHERE LOWER(email) = ?", (email_clean,))
        if cursor.fetchone():
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                                detail="An account with this email already exists.")
        now = _now()
        cursor.execute("""
            INSERT INTO users (email, username, password_hash, full_name, role, is_active,
                               assigned_classes, check_in_pin, must_change_password,
                               failed_login_attempts, lockout_until, created_at, updated_at)
            VALUES (?, NULL, ?, ?, 'teacher', 1, ?, ?, 0, 0, NULL, ?, ?)
        """, (email_clean, hash_password(req.password), req.full_name.strip(),
              req.assigned_classes.strip(), req.check_in_pin.strip(), now, now))
        teacher_id = cursor.lastrowid
        write_audit_log(conn, current_user["id"], current_user.get("email", ""),
                        "CREATE_TEACHER", "USER", teacher_id,
                        f"Admin created teacher account '{req.full_name}' ({req.email})")
        cursor.execute("SELECT * FROM users WHERE id = ?", (teacher_id,))
        return dict(cursor.fetchone())

@app.put("/api/admin/teachers/{teacher_id}")
def update_teacher(teacher_id: int, req: TeacherUpdateRequest, current_user: dict = Depends(require_admin)):
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM users WHERE id = ? AND role = 'teacher'", (teacher_id,))
        if not cursor.fetchone():
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Teacher not found.")
        email_clean = req.email.strip().lower()
        cursor.execute("SELECT id FROM users WHERE LOWER(email) = ? AND id != ?", (email_clean, teacher_id))
        if cursor.fetchone():
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Email already in use by another account.")
        now = _now()
        cursor.execute("""
            UPDATE users SET email = ?, full_name = ?, assigned_classes = ?, check_in_pin = ?,
                            is_active = ?, updated_at = ?
            WHERE id = ?
        """, (email_clean, req.full_name.strip(), req.assigned_classes.strip(),
              req.check_in_pin.strip(), 1 if req.is_active else 0, now, teacher_id))
        write_audit_log(conn, current_user["id"], current_user.get("email", ""),
                        "UPDATE_TEACHER", "USER", teacher_id, f"Admin updated teacher '{req.full_name}'")
        cursor.execute("SELECT * FROM users WHERE id = ?", (teacher_id,))
        return dict(cursor.fetchone())

@app.post("/api/admin/teachers/{teacher_id}/reset-password")
def reset_teacher_password(teacher_id: int, req: ResetPasswordRequest,
                            current_user: dict = Depends(require_admin)):
    if len(req.new_password) < 8:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Password must be at least 8 characters.")
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id, full_name, email FROM users WHERE id = ? AND role = 'teacher'", (teacher_id,))
        teacher = cursor.fetchone()
        if not teacher:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Teacher not found.")
        now = _now()
        cursor.execute(
            "UPDATE users SET password_hash = ?, must_change_password = 1, updated_at = ? WHERE id = ?",
            (hash_password(req.new_password), now, teacher_id)
        )
        write_audit_log(conn, current_user["id"], current_user.get("email", ""),
                        "RESET_PASSWORD", "USER", teacher_id,
                        f"Admin reset password for teacher '{teacher['full_name']}' – forced change on next login")
        return {"success": True, "message": f"Password for {teacher['full_name']} reset. They must change it on next login."}

@app.post("/api/admin/teachers/{teacher_id}/toggle-status")
def toggle_teacher_status(teacher_id: int, current_user: dict = Depends(require_admin)):
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id, full_name, is_active FROM users WHERE id = ? AND role = 'teacher'", (teacher_id,))
        teacher = cursor.fetchone()
        if not teacher:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Teacher not found.")
        new_status = 0 if teacher["is_active"] else 1
        cursor.execute("UPDATE users SET is_active = ?, updated_at = ? WHERE id = ?",
                       (new_status, _now(), teacher_id))
        action = "DEACTIVATE_USER" if new_status == 0 else "ACTIVATE_USER"
        write_audit_log(conn, current_user["id"], current_user.get("email", ""), action, "USER", teacher_id,
                        f"Teacher '{teacher['full_name']}' set to {'Active' if new_status else 'Inactive'}")
        return {"id": teacher_id, "is_active": new_status}

# ─────────────────────────────────────────────
#  PHASE 2 – Admin: Students
# ─────────────────────────────────────────────

@app.get("/api/admin/students")
def admin_list_students(current_user: dict = Depends(require_admin)):
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT s.id, s.name, s.class_name, s.roll_number, s.guardian_name, s.guardian_contact,
                   s.consent_given, s.is_archived, s.user_id, s.assigned_teacher_id,
                   s.created_at, s.updated_at,
                   u.email AS student_email, u.username AS student_username, u.is_active AS user_active,
                   t.full_name AS teacher_name
            FROM students s
            LEFT JOIN users u ON s.user_id = u.id
            LEFT JOIN users t ON s.assigned_teacher_id = t.id
            ORDER BY s.class_name ASC, s.name ASC
        """)
        return [dict(r) for r in cursor.fetchall()]

@app.post("/api/admin/students", status_code=status.HTTP_201_CREATED)
def admin_create_student(req: StudentCreateRequest, current_user: dict = Depends(require_admin)):
    with get_db() as conn:
        cursor = conn.cursor()
        user_id = None
        now = _now()

        if req.username and req.username.strip():
            uname = req.username.strip().lower()
            cursor.execute("SELECT id FROM users WHERE LOWER(username) = ?", (uname,))
            if cursor.fetchone():
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                                    detail="A login account with this username already exists.")
            pwd = req.password or "Student@123"
            cursor.execute("""
                INSERT INTO users (email, username, password_hash, full_name, role, is_active,
                                   assigned_classes, check_in_pin, must_change_password,
                                   failed_login_attempts, lockout_until, created_at, updated_at)
                VALUES (NULL, ?, ?, ?, 'student', 1, '', '0000', 0, 0, NULL, ?, ?)
            """, (uname, hash_password(pwd), req.name.strip(), now, now))
            user_id = cursor.lastrowid

        cursor.execute("""
            INSERT INTO students (user_id, assigned_teacher_id, name, roll_number, class_name,
                                  guardian_name, guardian_contact, consent_given, is_archived,
                                  created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, 0, ?, ?)
        """, (user_id, req.assigned_teacher_id, req.name.strip(), req.roll_number.strip(),
              req.class_name.strip(), req.guardian_name.strip(), req.guardian_contact.strip(),
              1 if req.consent_given else 0, now, now))
        student_id = cursor.lastrowid

        # Log assignment history if teacher assigned
        if req.assigned_teacher_id:
            cursor.execute("""
                INSERT INTO assignment_history (student_id, old_teacher_id, new_teacher_id, changed_by, reason, changed_at)
                VALUES (?, NULL, ?, ?, 'Initial assignment', ?)
            """, (student_id, req.assigned_teacher_id, current_user["id"], now))

        write_audit_log(conn, current_user["id"], current_user.get("email", ""),
                        "ADMIN_CREATE_STUDENT", "STUDENT", student_id,
                        f"Admin created student '{req.name}' ({req.class_name}) – login: {req.username or 'None'}")
        cursor.execute("SELECT * FROM students WHERE id = ?", (student_id,))
        return dict(cursor.fetchone())

@app.put("/api/admin/students/{student_id}")
def admin_update_student(student_id: int, req: StudentUpdateRequest, current_user: dict = Depends(require_admin)):
    with get_db() as conn:
        cursor = conn.cursor()
        student = _get_student_or_404(cursor, student_id)
        now = _now()

        old_teacher = student.get("assigned_teacher_id")
        new_teacher = req.assigned_teacher_id

        cursor.execute("""
            UPDATE students
            SET name = ?, class_name = ?, roll_number = ?, guardian_name = ?, guardian_contact = ?,
                consent_given = ?, assigned_teacher_id = ?, updated_at = ?
            WHERE id = ?
        """, (req.name.strip(), req.class_name.strip(), req.roll_number.strip(),
              req.guardian_name.strip(), req.guardian_contact.strip(),
              1 if req.consent_given else 0, new_teacher, now, student_id))

        # Track reassignment
        if old_teacher != new_teacher:
            cursor.execute("""
                INSERT INTO assignment_history (student_id, old_teacher_id, new_teacher_id, changed_by, reason, changed_at)
                VALUES (?, ?, ?, ?, 'Admin reassignment', ?)
            """, (student_id, old_teacher, new_teacher, current_user["id"], now))

        # Update username on user account if provided
        if student["user_id"] and req.username:
            uname = req.username.strip().lower()
            cursor.execute("SELECT id FROM users WHERE LOWER(username) = ? AND id != ?",
                           (uname, student["user_id"]))
            if cursor.fetchone():
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                                    detail="Username already taken by another account.")
            cursor.execute("UPDATE users SET username = ?, full_name = ?, updated_at = ? WHERE id = ?",
                           (uname, req.name.strip(), now, student["user_id"]))

        write_audit_log(conn, current_user["id"], current_user.get("email", ""),
                        "ADMIN_UPDATE_STUDENT", "STUDENT", student_id,
                        f"Admin updated student '{req.name}'")
        cursor.execute("SELECT * FROM students WHERE id = ?", (student_id,))
        return dict(cursor.fetchone())

@app.post("/api/admin/students/{student_id}/reset-password")
def admin_reset_student_password(student_id: int, req: ResetPasswordRequest,
                                  current_user: dict = Depends(require_admin)):
    if len(req.new_password) < 6:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Password must be at least 6 characters.")
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT s.name, s.user_id, u.username FROM students s LEFT JOIN users u ON s.user_id = u.id WHERE s.id = ?",
                       (student_id,))
        record = cursor.fetchone()
        if not record or not record["user_id"]:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                                detail="Student has no linked login account.")
        now = _now()
        cursor.execute("UPDATE users SET password_hash = ?, must_change_password = 1, updated_at = ? WHERE id = ?",
                       (hash_password(req.new_password), now, record["user_id"]))
        write_audit_log(conn, current_user["id"], current_user.get("email", ""),
                        "RESET_STUDENT_PASSWORD", "USER", record["user_id"],
                        f"Admin reset login password for student '{record['name']}'")
        return {"success": True, "message": f"Password for {record['name']} reset. They must change it on next login."}

@app.post("/api/admin/students/{student_id}/toggle-status")
def admin_toggle_student_status(student_id: int, current_user: dict = Depends(require_admin)):
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT s.name, s.user_id, u.is_active FROM students s LEFT JOIN users u ON s.user_id = u.id WHERE s.id = ?",
                       (student_id,))
        record = cursor.fetchone()
        if not record or not record["user_id"]:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                                detail="Student has no linked login account.")
        new_status = 0 if record["is_active"] else 1
        cursor.execute("UPDATE users SET is_active = ?, updated_at = ? WHERE id = ?",
                       (new_status, _now(), record["user_id"]))
        return {"student_id": student_id, "user_active": new_status}

# ─────────────────────────────────────────────
#  PHASE 2 – Bulk Assignment
# ─────────────────────────────────────────────

@app.post("/api/admin/assignments/bulk")
def bulk_assign_students(req: BulkAssignRequest, current_user: dict = Depends(require_admin)):
    with get_db() as conn:
        cursor = conn.cursor()
        # Validate teacher
        cursor.execute("SELECT id, full_name FROM users WHERE id = ? AND role = 'teacher'", (req.teacher_id,))
        teacher = cursor.fetchone()
        if not teacher:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Teacher not found.")
        now = _now()
        updated = []
        for sid in req.student_ids:
            cursor.execute("SELECT id, assigned_teacher_id FROM students WHERE id = ?", (sid,))
            s = cursor.fetchone()
            if not s:
                continue
            old_tid = s["assigned_teacher_id"]
            cursor.execute("UPDATE students SET assigned_teacher_id = ?, updated_at = ? WHERE id = ?",
                           (req.teacher_id, now, sid))
            if old_tid != req.teacher_id:
                cursor.execute("""
                    INSERT INTO assignment_history (student_id, old_teacher_id, new_teacher_id, changed_by, reason, changed_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (sid, old_tid, req.teacher_id, current_user["id"], req.reason or "Bulk assignment", now))
            updated.append(sid)
        write_audit_log(conn, current_user["id"], current_user.get("email", ""),
                        "BULK_ASSIGN", "STUDENT", None,
                        f"Bulk-assigned {len(updated)} students to teacher '{teacher['full_name']}'")
        return {"assigned_count": len(updated), "student_ids": updated}

@app.get("/api/admin/assignment-history")
def get_assignment_history(student_id: Optional[int] = None, current_user: dict = Depends(require_admin)):
    with get_db() as conn:
        cursor = conn.cursor()
        sql = """
            SELECT ah.*, s.name AS student_name,
                   ot.full_name AS old_teacher_name, nt.full_name AS new_teacher_name,
                   cb.email AS changed_by_email
            FROM assignment_history ah
            JOIN students s ON ah.student_id = s.id
            LEFT JOIN users ot ON ah.old_teacher_id = ot.id
            LEFT JOIN users nt ON ah.new_teacher_id = nt.id
            LEFT JOIN users cb ON ah.changed_by = cb.id
            WHERE 1=1
        """
        params: List[Any] = []
        if student_id:
            sql += " AND ah.student_id = ?"
            params.append(student_id)
        sql += " ORDER BY ah.changed_at DESC LIMIT 200"
        cursor.execute(sql, params)
        return [dict(r) for r in cursor.fetchall()]

# ─────────────────────────────────────────────
#  PHASE 2 – Admin: Settings
# ─────────────────────────────────────────────

@app.get("/api/admin/settings")
def get_settings(current_user: dict = Depends(require_admin)):
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT key, value FROM settings")
        return {r["key"]: r["value"] for r in cursor.fetchall()}

@app.put("/api/admin/settings")
def update_settings(req: SettingsUpdateRequest, current_user: dict = Depends(require_admin)):
    updates = {
        "safeguarding_contact_name": req.safeguarding_contact_name,
        "safeguarding_contact_phone": req.safeguarding_contact_phone,
        "safeguarding_contact_email": req.safeguarding_contact_email,
        "reporting_window_days": str(req.reporting_window_days),
        "checkin_frequency_days": str(req.checkin_frequency_days),
    }
    with get_db() as conn:
        now = _now()
        for k, v in updates.items():
            conn.execute("INSERT OR REPLACE INTO settings (key, value, updated_at) VALUES (?, ?, ?)",
                         (k, v, now))
        write_audit_log(conn, current_user["id"], current_user.get("email", ""),
                        "UPDATE_SETTINGS", "SETTINGS", None, "Admin updated system settings")
        return {"success": True, "settings": updates}

# ─────────────────────────────────────────────
#  Dashboard
# ─────────────────────────────────────────────

@app.get("/api/dashboard")
def get_dashboard(current_user: dict = Depends(get_current_user)):
    with get_db() as conn:
        cursor = conn.cursor()

        # ─── ADMIN DASHBOARD ───
        if current_user["role"] == "admin":
            cursor.execute("SELECT COUNT(*) AS count FROM students WHERE is_archived = 0")
            total_students = cursor.fetchone()["count"]
            cursor.execute("SELECT COUNT(*) AS count FROM students WHERE is_archived = 1")
            total_archived = cursor.fetchone()["count"]
            cursor.execute("SELECT COUNT(*) AS count FROM users WHERE role = 'teacher' AND is_active = 1")
            total_teachers = cursor.fetchone()["count"]
            cursor.execute("SELECT COUNT(DISTINCT class_name) AS count FROM students WHERE is_archived = 0")
            total_classes = cursor.fetchone()["count"]
            cursor.execute("SELECT COUNT(*) AS count FROM students WHERE is_archived = 0 AND assigned_teacher_id IS NULL")
            unassigned_students = cursor.fetchone()["count"]
            cursor.execute("SELECT COUNT(*) AS count FROM assessments")
            total_assessments = cursor.fetchone()["count"]
            cursor.execute("SELECT COUNT(*) AS count FROM checkins")
            total_checkins = cursor.fetchone()["count"]
            cursor.execute("SELECT COUNT(*) AS count FROM alerts WHERE status IN ('open', 'acknowledged', 'snoozed')")
            open_alerts_count = cursor.fetchone()["count"]
            cursor.execute("SELECT COUNT(*) AS count FROM alerts WHERE severity = 'urgent' AND status != 'resolved'")
            urgent_alerts_count = cursor.fetchone()["count"]
            # Aggregated well-being distribution (admin sees totals only, not individual answers)
            reporting_days = int(_get_setting(conn, "reporting_window_days", "30"))
            cursor.execute("""
                SELECT s.id FROM students s WHERE s.is_archived = 0
            """)
            all_student_ids = [r["id"] for r in cursor.fetchall()]
            dist = {"Thriving": 0, "Doing okay": 0, "May benefit from support": 0, "No data": 0}
            for sid in all_student_ids:
                cursor.execute("SELECT score FROM checkins WHERE student_id = ? ORDER BY created_at ASC", (sid,))
                scores = [r["score"] for r in cursor.fetchall()]
                lvl = evaluate_support_level(scores)["level"]
                dist[lvl] = dist.get(lvl, 0) + 1

            return {
                "role": "admin",
                "total_students": total_students,
                "total_archived": total_archived,
                "total_teachers": total_teachers,
                "total_classes": total_classes,
                "unassigned_students": unassigned_students,
                "total_assessments": total_assessments,
                "total_checkins": total_checkins,
                "open_alerts_count": open_alerts_count,
                "urgent_alerts_count": urgent_alerts_count,
                "wellbeing_distribution": dist,
            }

        # ─── STUDENT DASHBOARD ───
        if current_user["role"] == "student":
            cursor.execute("SELECT * FROM students WHERE user_id = ?", (current_user["id"],))
            st = cursor.fetchone()
            if not st:
                return {"role": "student", "student": None,
                        "message": "Student profile not linked. Contact administrator."}
            st_dict = dict(st)
            cursor.execute("SELECT score FROM checkins WHERE student_id = ? ORDER BY created_at ASC",
                           (st_dict["id"],))
            scores = [r["score"] for r in cursor.fetchall()]
            support_info = evaluate_support_level(scores)
            cursor.execute("SELECT * FROM assessments WHERE student_id = ? ORDER BY date DESC",
                           (st_dict["id"],))
            assessments = [dict(r) for r in cursor.fetchall()]
            gaps = evaluate_learning_gaps(assessments)
            recommendations = generate_recommendations(support_info, gaps)
            # Mentor info (no personal well-being details)
            mentor_name = None
            if st_dict.get("assigned_teacher_id"):
                row = cursor.execute("SELECT full_name FROM users WHERE id = ?",
                                     (st_dict["assigned_teacher_id"],)).fetchone()
                if row:
                    mentor_name = row["full_name"]
            return {
                "role": "student",
                "student": st_dict,
                "mentor_name": mentor_name,
                "support_info": {
                    "level": support_info["level"],
                    "reason": support_info["reason"],
                    "badge_class": support_info["badge_class"],
                },
                "checkins_count": len(scores),
                "latest_score": scores[-1] if scores else None,
                "assessments": assessments[:5],
                "recommendations": recommendations,
                "disclaimer": DISCLAIMER_TEXT,
            }

        # ─── TEACHER DASHBOARD ───
        assigned_classes = [c.strip() for c in current_user.get("assigned_classes", "").split(",") if c.strip()]
        conditions: List[str] = []
        params: List[Any] = []
        if assigned_classes:
            ph = ",".join("?" for _ in assigned_classes)
            conditions.append(f"class_name IN ({ph})")
            params.extend(assigned_classes)
        conditions.append("assigned_teacher_id = ?")
        params.append(current_user["id"])
        where = " OR ".join(conditions)
        cursor.execute(f"SELECT * FROM students WHERE is_archived = 0 AND ({where})", params)
        students = [dict(r) for r in cursor.fetchall()]

        if not students:
            return {
                "role": "teacher",
                "total_students": 0,
                "class_average_mark": 0.0,
                "open_alerts_count": 0,
                "wellbeing_distribution": {"Thriving": 0, "Doing okay": 0,
                                           "May benefit from support": 0, "No data": 0},
                "students_need_attention": [],
                "disclaimer": DISCLAIMER_TEXT,
                "is_empty": True,
                "empty_message": "No students are currently assigned to this teacher.",
            }

        student_ids = [s["id"] for s in students]
        s_ph = ",".join("?" for _ in student_ids)

        cursor.execute(f"""
            SELECT AVG((score / max_score) * 100.0) AS avg_mark
            FROM assessments WHERE student_id IN ({s_ph})
        """, student_ids)
        row = cursor.fetchone()
        class_average_mark = round(row["avg_mark"], 1) if row and row["avg_mark"] is not None else 0.0

        cursor.execute(f"""
            SELECT COUNT(*) AS count FROM alerts
            WHERE student_id IN ({s_ph}) AND status IN ('open', 'acknowledged', 'snoozed')
        """, student_ids)
        open_alerts_count = cursor.fetchone()["count"]

        dist = {"Thriving": 0, "Doing okay": 0, "May benefit from support": 0, "No data": 0}
        students_need_attention = []

        reporting_days = int(_get_setting(conn, "reporting_window_days", "30"))

        for s in students:
            cursor.execute("SELECT score FROM checkins WHERE student_id = ? ORDER BY created_at ASC", (s["id"],))
            scores = [r["score"] for r in cursor.fetchall()]
            support_info = evaluate_support_level(scores)
            lvl = support_info["level"]
            dist[lvl if lvl in dist else "No data"] += 1

            cursor.execute("SELECT * FROM assessments WHERE student_id = ? ORDER BY date ASC, id ASC", (s["id"],))
            a_rows = [dict(r) for r in cursor.fetchall()]
            gaps = evaluate_learning_gaps(a_rows)

            cursor.execute("""
                SELECT * FROM alerts WHERE student_id = ? AND status IN ('open','acknowledged','snoozed')
                ORDER BY severity DESC, created_at DESC
            """, (s["id"],))
            st_alerts = [dict(r) for r in cursor.fetchall()]
            has_urgent = any(a["severity"] == "urgent" for a in st_alerts)

            reasons = []
            if has_urgent:
                reasons.append("🚨 Urgent safeguarding flag")
            if lvl == "May benefit from support":
                reasons.append(f"Well-being indicator: {support_info['reason']}")
            if gaps:
                reasons.append(f"Learning gap: {', '.join(g['subject'] for g in gaps)}")

            if reasons:
                students_need_attention.append({
                    "id": s["id"],
                    "name": s["name"],
                    "class_name": s["class_name"],
                    "support_level": lvl,
                    "support_reason": support_info["reason"],
                    "badge_class": support_info["badge_class"],
                    "learning_gaps": gaps,
                    "open_alerts": st_alerts,
                    "has_urgent": has_urgent,
                    "reasons": reasons,
                    "summary_reason": "; ".join(reasons),
                })

        students_need_attention.sort(
            key=lambda x: (not x["has_urgent"], x["support_level"] != "May benefit from support")
        )

        return {
            "role": "teacher",
            "total_students": len(students),
            "class_average_mark": class_average_mark,
            "open_alerts_count": open_alerts_count,
            "wellbeing_distribution": dist,
            "students_need_attention": students_need_attention,
            "disclaimer": DISCLAIMER_TEXT,
            "is_empty": False,
        }

# ─────────────────────────────────────────────
#  Students Routes
# ─────────────────────────────────────────────

@app.get("/api/students")
def list_students(
    query: Optional[str] = None,
    class_name: Optional[str] = None,
    include_archived: bool = False,
    current_user: dict = Depends(get_current_user)
):
    with get_db() as conn:
        cursor = conn.cursor()

        if current_user["role"] == "student":
            cursor.execute("SELECT * FROM students WHERE user_id = ?", (current_user["id"],))
            s = cursor.fetchone()
            return [dict(s)] if s else []

        sql = """
            SELECT s.*, u.email AS student_email, u.username AS student_username,
                   t.full_name AS teacher_name
            FROM students s
            LEFT JOIN users u ON s.user_id = u.id
            LEFT JOIN users t ON s.assigned_teacher_id = t.id
            WHERE 1=1
        """
        params: List[Any] = []

        if not include_archived:
            sql += " AND s.is_archived = 0"

        if current_user["role"] == "teacher":
            assigned_classes = [c.strip() for c in current_user.get("assigned_classes", "").split(",") if c.strip()]
            conditions = []
            if assigned_classes:
                ph = ",".join("?" for _ in assigned_classes)
                conditions.append(f"s.class_name IN ({ph})")
                params.extend(assigned_classes)
            conditions.append("s.assigned_teacher_id = ?")
            params.append(current_user["id"])
            sql += f" AND ({' OR '.join(conditions)})"

        if class_name:
            sql += " AND s.class_name = ?"
            params.append(class_name)

        if query:
            sql += " AND (s.name LIKE ? OR s.guardian_name LIKE ? OR s.roll_number LIKE ?)"
            params.extend([f"%{query.strip()}%"] * 3)

        sql += " ORDER BY s.class_name ASC, s.name ASC"
        cursor.execute(sql, params)
        rows = cursor.fetchall()

        result = []
        for r in rows:
            st = dict(r)
            if current_user["role"] in ["teacher", "admin"]:
                cursor.execute("SELECT score FROM checkins WHERE student_id = ? ORDER BY created_at ASC",
                               (st["id"],))
                scores = [row["score"] for row in cursor.fetchall()]
                sup = evaluate_support_level(scores)
                st["support_level"] = sup["level"]
                st["support_reason"] = sup["reason"]
                st["badge_class"] = sup["badge_class"]
            result.append(st)
        return result

@app.get("/api/students/{student_id}")
def get_student_profile(student_id: int, current_user: dict = Depends(get_current_user)):
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT s.*, u.email AS student_email, u.username AS student_username,
                   t.full_name AS teacher_name
            FROM students s
            LEFT JOIN users u ON s.user_id = u.id
            LEFT JOIN users t ON s.assigned_teacher_id = t.id
            WHERE s.id = ?
        """, (student_id,))
        student = cursor.fetchone()
        if not student:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Student not found.")
        student_dict = dict(student)

        check_student_record_access(current_user, student_dict)

        # Admin cannot view individual well-being data
        if current_user["role"] == "admin":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access restricted: Administrators cannot view individual student well-being data."
            )

        write_audit_log(conn, current_user["id"], current_user.get("email", ""),
                        "ACCESS_STUDENT_PROFILE", "STUDENT", student_id,
                        f"Accessed profile of student: {student_dict['name']}")

        cursor.execute("SELECT * FROM assessments WHERE student_id = ? ORDER BY date ASC, id ASC", (student_id,))
        assessments = [dict(r) for r in cursor.fetchall()]
        learning_gaps = evaluate_learning_gaps(assessments)

        cursor.execute("SELECT * FROM checkins WHERE student_id = ? ORDER BY created_at ASC", (student_id,))
        raw_checkins = [dict(r) for r in cursor.fetchall()]
        scores = []
        checkins_out = []
        for c in raw_checkins:
            scores.append(c["score"])
            checkins_out.append({
                "id": c["id"],
                "mood": c["mood"],
                "stress": c["stress"],
                "sleep": c["sleep"],
                "focus": c["focus"],
                "belonging": c["belonging"],
                "score": c["score"],
                "note": decrypt_note(c["encrypted_note"]),
                "created_at": c["created_at"],
            })

        support_info = evaluate_support_level(scores)
        recommendations = generate_recommendations(support_info, learning_gaps)

        cursor.execute("SELECT * FROM alerts WHERE student_id = ? ORDER BY created_at DESC", (student_id,))
        alerts = [dict(r) for r in cursor.fetchall()]

        cursor.execute("""
            SELECT o.*, u.full_name AS teacher_name
            FROM observations o JOIN users u ON o.teacher_id = u.id
            WHERE o.student_id = ? ORDER BY o.created_at DESC
        """, (student_id,))
        observations = [dict(r) for r in cursor.fetchall()]

        return {
            "student": student_dict,
            "assessments": assessments,
            "learning_gaps": learning_gaps,
            "checkins": checkins_out,
            "support_info": support_info,
            "recommendations": recommendations,
            "alerts": alerts,
            "observations": observations,
            "disclaimer": DISCLAIMER_TEXT,
        }

@app.post("/api/students", status_code=status.HTTP_201_CREATED)
def teacher_create_student(req: StudentCreateRequest, current_user: dict = Depends(require_teacher_or_admin)):
    check_teacher_class_access(current_user, req.class_name)
    with get_db() as conn:
        cursor = conn.cursor()
        now = _now()
        assigned_teacher_id = req.assigned_teacher_id or (current_user["id"] if current_user["role"] == "teacher" else None)
        user_id = None
        if req.username and req.username.strip():
            uname = req.username.strip().lower()
            cursor.execute("SELECT id FROM users WHERE LOWER(username) = ?", (uname,))
            if cursor.fetchone():
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                                    detail="A login with this username already exists.")
            pwd = req.password or "Student@123"
            cursor.execute("""
                INSERT INTO users (email, username, password_hash, full_name, role, is_active,
                                   assigned_classes, check_in_pin, must_change_password,
                                   failed_login_attempts, lockout_until, created_at, updated_at)
                VALUES (NULL, ?, ?, ?, 'student', 1, '', '0000', 0, 0, NULL, ?, ?)
            """, (uname, hash_password(pwd), req.name.strip(), now, now))
            user_id = cursor.lastrowid

        cursor.execute("""
            INSERT INTO students (user_id, assigned_teacher_id, name, roll_number, class_name,
                                  guardian_name, guardian_contact, consent_given, is_archived,
                                  created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, 0, ?, ?)
        """, (user_id, assigned_teacher_id, req.name.strip(), req.roll_number.strip(),
              req.class_name.strip(), req.guardian_name.strip(), req.guardian_contact.strip(),
              1 if req.consent_given else 0, now, now))
        student_id = cursor.lastrowid
        write_audit_log(conn, current_user["id"], current_user.get("email", ""),
                        "CREATE_STUDENT", "STUDENT", student_id,
                        f"Created student '{req.name}' in class '{req.class_name}'")
        cursor.execute("SELECT * FROM students WHERE id = ?", (student_id,))
        return dict(cursor.fetchone())

@app.put("/api/students/{student_id}")
def update_student(student_id: int, req: StudentUpdateRequest, current_user: dict = Depends(require_teacher_or_admin)):
    with get_db() as conn:
        cursor = conn.cursor()
        student = _get_student_or_404(cursor, student_id)
        check_student_record_access(current_user, student)
        check_teacher_class_access(current_user, req.class_name)
        now = _now()
        cursor.execute("""
            UPDATE students SET name = ?, class_name = ?, roll_number = ?, guardian_name = ?,
                               guardian_contact = ?, consent_given = ?, assigned_teacher_id = ?,
                               updated_at = ?
            WHERE id = ?
        """, (req.name.strip(), req.class_name.strip(), req.roll_number.strip(),
              req.guardian_name.strip(), req.guardian_contact.strip(),
              1 if req.consent_given else 0,
              req.assigned_teacher_id or student["assigned_teacher_id"],
              now, student_id))
        write_audit_log(conn, current_user["id"], current_user.get("email", ""),
                        "UPDATE_STUDENT", "STUDENT", student_id, f"Updated student '{req.name}'")
        cursor.execute("SELECT * FROM students WHERE id = ?", (student_id,))
        return dict(cursor.fetchone())

@app.post("/api/students/{student_id}/archive")
def toggle_archive_student(student_id: int, current_user: dict = Depends(require_teacher_or_admin)):
    with get_db() as conn:
        cursor = conn.cursor()
        student = _get_student_or_404(cursor, student_id)
        check_student_record_access(current_user, student)
        new_state = 0 if student["is_archived"] else 1
        now = _now()
        cursor.execute("UPDATE students SET is_archived = ?, updated_at = ? WHERE id = ?",
                       (new_state, now, student_id))
        action = "ARCHIVE_STUDENT" if new_state == 1 else "UNARCHIVE_STUDENT"
        write_audit_log(conn, current_user["id"], current_user.get("email", ""), action, "STUDENT",
                        student_id, f"{'Archived' if new_state else 'Unarchived'} student '{student['name']}'")
        return {"id": student_id, "is_archived": new_state}

# ─────────────────────────────────────────────
#  Assessments (Marks)
# ─────────────────────────────────────────────

@app.post("/api/assessments", status_code=status.HTTP_201_CREATED)
def add_assessment(req: AssessmentCreateRequest, current_user: dict = Depends(require_teacher_or_admin)):
    with get_db() as conn:
        cursor = conn.cursor()
        student = _get_student_or_404(cursor, req.student_id)
        check_student_record_access(current_user, student)
        now = _now()
        cursor.execute("""
            INSERT INTO assessments (student_id, subject, score, max_score, date, notes, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (req.student_id, req.subject.strip(), req.score, req.max_score,
              req.date.strip(), req.notes or "", now))
        assessment_id = cursor.lastrowid
        pct = round((req.score / req.max_score) * 100.0, 1)
        write_audit_log(conn, current_user["id"], current_user.get("email", ""),
                        "ADD_ASSESSMENT", "ASSESSMENT", assessment_id,
                        f"Added {req.subject} score {req.score}/{req.max_score} for {student['name']}")

        # Rule C & D
        cursor.execute("SELECT * FROM assessments WHERE student_id = ? ORDER BY date ASC, id ASC", (req.student_id,))
        all_a = [dict(r) for r in cursor.fetchall()]
        gaps = evaluate_learning_gaps(all_a)
        for gap in gaps:
            if gap["subject"] == req.subject:
                cursor.execute("""
                    SELECT id FROM alerts WHERE student_id = ? AND alert_type = 'learning_gap'
                    AND subject = ? AND status IN ('open','acknowledged','snoozed')
                """, (req.student_id, gap["subject"]))
                if not cursor.fetchone():
                    cursor.execute("""
                        INSERT INTO alerts (student_id, alert_type, title, message, severity, status,
                                           subject, created_at, updated_at)
                        VALUES (?, 'learning_gap', ?, ?, 'standard', 'open', ?, ?, ?)
                    """, (req.student_id,
                          f"Academic support recommended – {gap['subject']}: {student['name']}",
                          gap["reason"], gap["subject"], now, now))
        return {"id": assessment_id, "score": req.score, "percentage": pct, "learning_gaps": gaps}

# ─────────────────────────────────────────────
#  PHASE 3 – Mental Health Check-In (renamed from Kiosk)
# ─────────────────────────────────────────────

@app.post("/api/checkins/mental-health", status_code=status.HTTP_201_CREATED)
def submit_mental_health_checkin(req: CheckinRequest):
    """
    Teacher-initiated Mental Health Check-In.
    PIN is validated against the teacher's stored check_in_pin.
    Does NOT require a Bearer token so it works in unattended kiosk mode.
    """
    with get_db() as conn:
        cursor = conn.cursor()
        # Find teacher by PIN
        cursor.execute("""
            SELECT * FROM users WHERE check_in_pin = ? AND role = 'teacher' AND is_active = 1
        """, (req.teacher_pin.strip(),))
        teacher = cursor.fetchone()
        if not teacher:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid teacher PIN.")

        cursor.execute("SELECT * FROM students WHERE id = ? AND is_archived = 0", (req.student_id,))
        student = cursor.fetchone()
        if not student:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Student not found.")

        # Ensure student belongs to this teacher
        assigned = [c.strip() for c in teacher["assigned_classes"].split(",") if c.strip()]
        in_class = student["class_name"] in assigned if assigned else False
        is_mentor = student["assigned_teacher_id"] == teacher["id"]
        if not in_class and not is_mentor:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                                detail="Student is not assigned to your classes.")

        score = calculate_checkin_score(req.mood, req.stress, req.sleep, req.focus, req.belonging)
        encrypted_note = encrypt_note(req.note) if req.note else None
        now = _now()

        cursor.execute("""
            INSERT INTO checkins (student_id, mood, stress, sleep, focus, belonging,
                                  encrypted_note, score, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (req.student_id, req.mood, req.stress, req.sleep, req.focus,
              req.belonging, encrypted_note, score, now))
        checkin_id = cursor.lastrowid

        # Rule E: Safety keywords
        is_urgent, matched_kw = check_safety_keywords(req.note)
        sg_name = _get_setting(conn, "safeguarding_contact_name", "")
        sg_phone = _get_setting(conn, "safeguarding_contact_phone", "")
        full_sg_msg = SAFEGUARDING_MESSAGE
        if sg_name or sg_phone:
            full_sg_msg += f" Contact: {sg_name} {sg_phone}".strip()

        if is_urgent:
            cursor.execute("""
                INSERT INTO alerts (student_id, alert_type, title, message, severity, status,
                                   subject, created_at, updated_at)
                VALUES (?, 'safety', ?, ?, 'urgent', 'open', '', ?, ?)
            """, (req.student_id, f"🚨 Urgent Safeguarding Notice: {student['name']}",
                  full_sg_msg, now, now))

        # Rule B & D
        cursor.execute("SELECT score FROM checkins WHERE student_id = ? ORDER BY created_at ASC",
                       (req.student_id,))
        scores = [r["score"] for r in cursor.fetchall()]
        sup_info = evaluate_support_level(scores)
        if sup_info["level"] == "May benefit from support":
            cursor.execute("""
                SELECT id FROM alerts WHERE student_id = ? AND alert_type = 'support_level'
                AND status IN ('open','acknowledged','snoozed')
            """, (req.student_id,))
            if not cursor.fetchone():
                cursor.execute("""
                    INSERT INTO alerts (student_id, alert_type, title, message, severity, status,
                                       subject, created_at, updated_at)
                    VALUES (?, 'support_level', ?, ?, 'standard', 'open', '', ?, ?)
                """, (req.student_id,
                      f"Well-being follow-up needed: {student['name']}",
                      f"Well-being indicator: {sup_info['reason']}",
                      now, now))

        write_audit_log(conn, teacher["id"], teacher["email"] or "",
                        "MENTAL_HEALTH_CHECKIN", "CHECKIN", checkin_id,
                        f"Mental health check-in for '{student['name']}' (Score: {score}/5)")
        return {
            "success": True,
            "checkin_id": checkin_id,
            "score": score,
            "support_level": sup_info["level"],
            "support_reason": sup_info["reason"],
            "urgent_flag": is_urgent,
        }

# Keep old kiosk endpoint as alias for backwards compatibility
@app.post("/api/checkins/kiosk", status_code=status.HTTP_201_CREATED)
def submit_kiosk_checkin_compat(req: CheckinRequest):
    return submit_mental_health_checkin(req)

@app.post("/api/students/me/checkin", status_code=status.HTTP_201_CREATED)
def student_self_checkin(req: StudentSelfCheckinRequest, current_user: dict = Depends(require_student)):
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM students WHERE user_id = ? AND is_archived = 0", (current_user["id"],))
        student = cursor.fetchone()
        if not student:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                                detail="Student profile not linked to this account.")

        score = calculate_checkin_score(req.mood, req.stress, req.sleep, req.focus, req.belonging)
        encrypted_note = encrypt_note(req.note) if req.note else None
        now = _now()

        cursor.execute("""
            INSERT INTO checkins (student_id, mood, stress, sleep, focus, belonging,
                                  encrypted_note, score, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (student["id"], req.mood, req.stress, req.sleep, req.focus,
              req.belonging, encrypted_note, score, now))
        checkin_id = cursor.lastrowid

        is_urgent, _ = check_safety_keywords(req.note)
        sg_name = _get_setting(conn, "safeguarding_contact_name", "")
        sg_phone = _get_setting(conn, "safeguarding_contact_phone", "")
        full_sg_msg = SAFEGUARDING_MESSAGE
        if sg_name or sg_phone:
            full_sg_msg += f" Contact: {sg_name} {sg_phone}".strip()

        if is_urgent:
            cursor.execute("""
                INSERT INTO alerts (student_id, alert_type, title, message, severity, status,
                                   subject, created_at, updated_at)
                VALUES (?, 'safety', ?, ?, 'urgent', 'open', '', ?, ?)
            """, (student["id"], f"🚨 Urgent Safeguarding Notice: {student['name']}",
                  full_sg_msg, now, now))

        cursor.execute("SELECT score FROM checkins WHERE student_id = ? ORDER BY created_at ASC",
                       (student["id"],))
        scores = [r["score"] for r in cursor.fetchall()]
        sup_info = evaluate_support_level(scores)
        if sup_info["level"] == "May benefit from support":
            cursor.execute("""
                SELECT id FROM alerts WHERE student_id = ? AND alert_type = 'support_level'
                AND status IN ('open','acknowledged','snoozed')
            """, (student["id"],))
            if not cursor.fetchone():
                cursor.execute("""
                    INSERT INTO alerts (student_id, alert_type, title, message, severity, status,
                                       subject, created_at, updated_at)
                    VALUES (?, 'support_level', ?, ?, 'standard', 'open', '', ?, ?)
                """, (student["id"],
                      f"Well-being follow-up needed: {student['name']}",
                      f"Well-being indicator: {sup_info['reason']}",
                      now, now))

        write_audit_log(conn, current_user["id"], current_user.get("username") or current_user.get("email", ""),
                        "STUDENT_SELF_CHECKIN", "CHECKIN", checkin_id,
                        f"Student '{student['name']}' completed mental health check-in (Score: {score}/5)")
        return {
            "success": True,
            "checkin_id": checkin_id,
            "score": score,
            "support_level": sup_info["level"],
            "support_reason": sup_info["reason"],
            "urgent_flag": is_urgent,
            "safeguarding_message": full_sg_msg if is_urgent else None,
            "disclaimer": DISCLAIMER_TEXT,
        }

# ─────────────────────────────────────────────
#  Observations & Follow-ups
# ─────────────────────────────────────────────

VALID_OBS_STATUSES = ["new", "contacted", "in_progress", "resolved"]

@app.get("/api/students/{student_id}/observations")
def list_student_observations(student_id: int, current_user: dict = Depends(get_current_user)):
    with get_db() as conn:
        cursor = conn.cursor()
        student = _get_student_or_404(cursor, student_id)
        check_student_record_access(current_user, student)
        cursor.execute("""
            SELECT o.*, u.full_name AS teacher_name
            FROM observations o JOIN users u ON o.teacher_id = u.id
            WHERE o.student_id = ? ORDER BY o.created_at DESC
        """, (student_id,))
        return [dict(r) for r in cursor.fetchall()]

@app.post("/api/students/{student_id}/observations", status_code=status.HTTP_201_CREATED)
def create_student_observation(student_id: int, req: ObservationCreateRequest,
                                current_user: dict = Depends(require_teacher_or_admin)):
    with get_db() as conn:
        cursor = conn.cursor()
        student = _get_student_or_404(cursor, student_id)
        check_student_record_access(current_user, student)
        obs_status = req.status if req.status in VALID_OBS_STATUSES else "new"
        now = _now()
        cursor.execute("""
            INSERT INTO observations (student_id, teacher_id, observation_text,
                                      follow_up_action, status, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (student_id, current_user["id"], req.observation_text.strip(),
              (req.follow_up_action or "").strip(), obs_status, now, now))
        obs_id = cursor.lastrowid
        write_audit_log(conn, current_user["id"], current_user.get("email", ""),
                        "RECORD_OBSERVATION", "OBSERVATION", obs_id,
                        f"Observation recorded for student '{student['name']}'")
        cursor.execute("""
            SELECT o.*, u.full_name AS teacher_name
            FROM observations o JOIN users u ON o.teacher_id = u.id WHERE o.id = ?
        """, (obs_id,))
        return dict(cursor.fetchone())

@app.put("/api/observations/{obs_id}/status")
def update_observation_status(obs_id: int, req: ObservationStatusRequest,
                               current_user: dict = Depends(require_teacher_or_admin)):
    if req.status not in VALID_OBS_STATUSES:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                            detail=f"Invalid status. Choose from {VALID_OBS_STATUSES}")
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT o.*, s.class_name, s.assigned_teacher_id
            FROM observations o JOIN students s ON o.student_id = s.id WHERE o.id = ?
        """, (obs_id,))
        obs = cursor.fetchone()
        if not obs:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Observation not found.")
        check_student_record_access(current_user, dict(obs))
        cursor.execute("UPDATE observations SET status = ?, updated_at = ? WHERE id = ?",
                       (req.status, _now(), obs_id))
        return {"id": obs_id, "status": req.status}

# ─────────────────────────────────────────────
#  Alerts
# ─────────────────────────────────────────────

VALID_ALERT_STATUSES = ["open", "acknowledged", "snoozed", "resolved"]

@app.get("/api/alerts")
def list_alerts(status_filter: Optional[str] = None,
                current_user: dict = Depends(get_current_user)):
    with get_db() as conn:
        cursor = conn.cursor()
        if current_user["role"] == "admin":
            sql = "SELECT a.*, s.name AS student_name, s.class_name FROM alerts a JOIN students s ON a.student_id = s.id WHERE 1=1"
            params: List[Any] = []
        elif current_user["role"] == "teacher":
            assigned = [c.strip() for c in current_user.get("assigned_classes", "").split(",") if c.strip()]
            conds = []
            params = []
            if assigned:
                ph = ",".join("?" for _ in assigned)
                conds.append(f"s.class_name IN ({ph})")
                params.extend(assigned)
            conds.append("s.assigned_teacher_id = ?")
            params.append(current_user["id"])
            sql = f"SELECT a.*, s.name AS student_name, s.class_name FROM alerts a JOIN students s ON a.student_id = s.id WHERE ({' OR '.join(conds)})"
        else:
            return []

        if status_filter:
            sql += " AND a.status = ?"
            params.append(status_filter)
        sql += " ORDER BY CASE a.severity WHEN 'urgent' THEN 0 ELSE 1 END, a.created_at DESC"
        cursor.execute(sql, params)
        return [dict(r) for r in cursor.fetchall()]

@app.post("/api/alerts/{alert_id}/status")
def update_alert_status(alert_id: int, req: AlertStatusUpdateRequest,
                         current_user: dict = Depends(require_teacher_or_admin)):
    if req.status not in VALID_ALERT_STATUSES:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                            detail=f"Invalid status. Choose from {VALID_ALERT_STATUSES}")
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT a.*, s.class_name, s.assigned_teacher_id, s.name AS student_name
            FROM alerts a JOIN students s ON a.student_id = s.id WHERE a.id = ?
        """, (alert_id,))
        alert = cursor.fetchone()
        if not alert:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Alert not found.")
        check_student_record_access(current_user, dict(alert))
        now = _now()
        cursor.execute("UPDATE alerts SET status = ?, updated_at = ? WHERE id = ?",
                       (req.status, now, alert_id))
        write_audit_log(conn, current_user["id"], current_user.get("email", ""),
                        "UPDATE_ALERT_STATUS", "ALERT", alert_id,
                        f"Alert for '{alert['student_name']}' set to '{req.status}'")
        return {"id": alert_id, "status": req.status, "updated_at": now}

# ─────────────────────────────────────────────
#  Admin: Audit Logs & Classes & Unassigned
# ─────────────────────────────────────────────

@app.get("/api/admin/audit-logs")
def list_audit_logs(limit: int = 100, action: Optional[str] = None,
                    current_user: dict = Depends(require_admin)):
    with get_db() as conn:
        cursor = conn.cursor()
        sql = "SELECT * FROM audit_logs WHERE 1=1"
        params: List[Any] = []
        if action:
            sql += " AND action = ?"
            params.append(action)
        sql += " ORDER BY timestamp DESC LIMIT ?"
        params.append(limit)
        cursor.execute(sql, params)
        return [dict(r) for r in cursor.fetchall()]

@app.get("/api/admin/unassigned-students")
def list_unassigned_students(current_user: dict = Depends(require_admin)):
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT s.id, s.name, s.class_name, s.roll_number, s.created_at
            FROM students s
            WHERE s.assigned_teacher_id IS NULL AND s.is_archived = 0
            ORDER BY s.class_name ASC, s.name ASC
        """)
        return [dict(r) for r in cursor.fetchall()]

@app.get("/api/classes")
def get_classes(current_user: dict = Depends(get_current_user)):
    with get_db() as conn:
        cursor = conn.cursor()
        if current_user["role"] == "admin":
            cursor.execute("SELECT DISTINCT class_name FROM students WHERE is_archived = 0 ORDER BY class_name ASC")
            classes = [r["class_name"] for r in cursor.fetchall() if r["class_name"]]
        elif current_user["role"] == "teacher":
            assigned = [c.strip() for c in current_user.get("assigned_classes", "").split(",") if c.strip()]
            cursor.execute("SELECT DISTINCT class_name FROM students WHERE assigned_teacher_id = ? AND is_archived = 0",
                           (current_user["id"],))
            classes = list(set(assigned + [r["class_name"] for r in cursor.fetchall() if r["class_name"]]))
        else:
            classes = []
        return sorted(classes)

# ─────────────────────────────────────────────
#  Static Files & Frontend SPA
# ─────────────────────────────────────────────

app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

@app.get("/{full_path:path}")
def serve_spa(full_path: str):
    index_file = STATIC_DIR / "index.html"
    if index_file.exists():
        return FileResponse(index_file)
    return JSONResponse(status_code=404, content={"message": "Frontend not found."})
