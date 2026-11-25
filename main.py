import os
import json
import uuid
from datetime import datetime, timezone, timedelta
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
)
from scoring_config import (
    evaluate_adaptive_checkin_scoring,
    check_text_for_safeguarding,
    SAFEGUARDING_TEACHER_ALERT_MESSAGE,
    DEFAULT_STUDENT_CALM_MESSAGE,
    DISCLAIMER_TEXT,
    GUIDANCE_TEMPLATES,
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

def write_audit_log(conn, user_id: Optional[int], user_email: Optional[str], action: str,
                    resource_type: str, resource_id: Optional[int], details: str):
    ident = user_email or "system"
    conn.execute(
        """
        INSERT INTO audit_logs (user_id, user_email, action, resource_type, resource_id, details, timestamp)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (user_id, ident, action, resource_type, resource_id, details, _now())
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
    identifier: Optional[str] = None
    email: Optional[str] = None
    username: Optional[str] = None
    password: str
    portal: str = "teacher"   # 'admin', 'teacher', 'student'

class ForgotPasswordRequest(BaseModel):
    identifier: str

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

CheckinKioskRequest = CheckinRequest

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

class AdaptiveAnswerRequest(BaseModel):
    question_id: str
    answer: Any
    preferred_not_to_answer: bool = False
    note: Optional[str] = None

class FollowUpStatusUpdateRequest(BaseModel):
    status: str # 'new', 'contacted', 'in_progress', 'resolved'
    notes: Optional[str] = ""

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

def setup_initial_admin(req: SetupAdminRequest):
    email = req.email.strip().lower()
    full_name = req.full_name.strip()
    if not email or not full_name:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Email and full name are required.")
    if len(req.password) < 8:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Password must be at least 8 characters.")

    with get_db() as conn:
        existing_admin = conn.execute(
            "SELECT id FROM users WHERE role = 'admin' LIMIT 1"
        ).fetchone()
        if existing_admin:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Initial setup has already been completed.")

        existing_user = conn.execute(
            "SELECT id FROM users WHERE email = ?",
            (email,),
        ).fetchone()
        now = _now()
        if existing_user:
            conn.execute(
                """
                UPDATE users
                SET password_hash = ?, full_name = ?, role = 'admin', is_active = 1, updated_at = ?
                WHERE id = ?
                """,
                (hash_password(req.password), full_name, now, existing_user["id"]),
            )
            user_id = existing_user["id"]
        else:
            cursor = conn.execute(
                """
                INSERT INTO users
                    (email, username, password_hash, full_name, role, is_active, assigned_classes,
                     check_in_pin, created_at, updated_at)
                VALUES (?, NULL, ?, ?, 'admin', 1, '', '9999', ?, ?)
                """,
                (email, hash_password(req.password), full_name, now, now),
            )
            user_id = cursor.lastrowid

        user_row = conn.execute(
            "SELECT * FROM users WHERE id = ?",
            (user_id,),
        ).fetchone()
        write_audit_log(
            conn,
            user_id,
            email,
            "INITIAL_ADMIN_SETUP",
            "USER",
            user_id,
            "Initial administrator account was created.",
        )

    pub = _build_public_user(dict(user_row))
    token = create_access_token(dict(user_row))
    return {"access_token": token, "token_type": "bearer", "user": pub}

@app.post("/api/auth/setup")
def setup_initial_admin_endpoint(req: SetupAdminRequest):
    return setup_initial_admin(req)

@app.post("/api/auth/login")
def login(req: LoginRequest):
    portal = req.portal.strip().lower()
    if portal not in ("admin", "teacher", "student"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid portal.")

    identifier = req.identifier or req.email or req.username
    if not identifier:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=GENERIC_LOGIN_ERROR)
    user_dict = authenticate_user(identifier, req.password, portal)
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

@app.post("/api/auth/forgot-password")
def request_password_reset(req: ForgotPasswordRequest):
    identifier = req.identifier.strip().lower()
    if not identifier:
        return {"success": True, "message": "If the account exists, a password reset request has been sent to the administrator."}

    with get_db() as conn:
        conn.execute(
            "INSERT INTO password_reset_requests (identifier, status, requested_at) VALUES (?, 'pending', ?)",
            (identifier, _now()),
        )
        write_audit_log(
            conn,
            None,
            identifier,
            "PASSWORD_RESET_REQUEST",
            "USER",
            None,
            "A password reset request was submitted.",
        )
    return {
        "success": True,
        "message": "If the account exists, a password reset request has been sent to the administrator.",
    }

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
                "wellbeing_distribution": {
                    "has_data": False,
                    "empty_message": "No students are currently assigned to this teacher.",
                    "total_assigned": 0,
                    "included_count": 0,
                    "pending_count": 0,
                    "summary_text": "Based on 0 assigned students",
                    "pending_text": "0 students pending check-in",
                    "categories": {}
                },
                "teaching_insights": {
                    "average_lesson_understanding_pct": None,
                    "classroom_participation_pct": None,
                    "teaching_pace_feedback": {"just_right": 0.0, "fast": 0.0, "slow": 0.0},
                    "preferred_learning_methods": [],
                    "academic_support_required_count": 0,
                    "difficult_subjects": []
                },
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

        # Reporting Window Cutoff
        reporting_days = int(_get_setting(conn, "reporting_window_days", "30"))
        cutoff_dt = datetime.now(timezone.utc) - timedelta(days=reporting_days)
        cutoff_iso = cutoff_dt.isoformat()

        included_students_count = 0
        distribution_counts = {"Doing Well": 0, "Moderate Concern": 0, "Needs Attention": 0}

        # Insights accumulators
        understanding_scores = []
        question_comfort_counts = {"comfortable": 0, "hesitant": 0}
        pace_counts = {"just_right": 0, "fast": 0, "slow": 0}
        preferred_methods_counts = {}
        academic_support_students = set()
        difficult_subject_counts = {}

        students_need_attention = []

        for s in students:
            # Query latest check-in in reporting window
            cursor.execute("""
                SELECT * FROM checkins
                WHERE student_id = ? AND created_at >= ?
                ORDER BY created_at DESC LIMIT 1
            """, (s["id"], cutoff_iso))
            latest_c = cursor.fetchone()

            # Follow-up status check
            cursor.execute("""
                SELECT * FROM observations WHERE student_id = ? ORDER BY created_at DESC LIMIT 1
            """, (s["id"],))
            latest_obs = cursor.fetchone()
            follow_up_status = latest_obs["status"] if latest_obs else (latest_c["follow_up_status"] if latest_c and "follow_up_status" in latest_c.keys() else "none")

            if latest_c:
                included_students_count += 1
                indicator = latest_c["wellbeing_indicator"] if latest_c["wellbeing_indicator"] else None
                if not indicator:
                    sup_temp = evaluate_support_level([latest_c["score"]])
                    lvl_temp = sup_temp["level"]
                    if lvl_temp == "Thriving":
                        indicator = "Doing Well"
                    elif lvl_temp == "Doing okay":
                        indicator = "Moderate Concern"
                    else:
                        indicator = "Needs Attention"

                if indicator not in distribution_counts:
                    distribution_counts[indicator] = 0
                distribution_counts[indicator] += 1

                # Parse snapshot for insights
                snapshot_raw = latest_c["answers_snapshot_json"] if "answers_snapshot_json" in latest_c.keys() and latest_c["answers_snapshot_json"] else "{}"
                try:
                    snapshot = json.loads(snapshot_raw) if snapshot_raw else {}
                except Exception:
                    snapshot = {}

                for qk, qval in snapshot.items():
                    ans = qval.get("answer") if isinstance(qval, dict) else qval
                    # Lesson understanding
                    if "understanding" in qk:
                        if ans in ["und_all", "und_most"]:
                            understanding_scores.append(100.0 if ans == "und_all" else 80.0)
                        elif ans == "und_half":
                            understanding_scores.append(60.0)
                        elif ans in ["und_struggling", "und_lost"]:
                            understanding_scores.append(40.0 if ans == "und_struggling" else 20.0)
                    # Question comfort
                    if "question_comfort" in qk:
                        if ans in ["qc_very", "qc_sometimes"]:
                            question_comfort_counts["comfortable"] += 1
                        else:
                            question_comfort_counts["hesitant"] += 1
                    # Pace
                    if "pace" in qk:
                        if ans == "tp_just_right":
                            pace_counts["just_right"] += 1
                        elif ans in ["tp_fast", "tp_racing"]:
                            pace_counts["fast"] += 1
                        elif ans == "tp_slow":
                            pace_counts["slow"] += 1
                    # Preferred method
                    if "preferred_method" in qk and isinstance(ans, str):
                        m_label = {"pm_visual": "Visual", "pm_hands_on": "Hands-on", "pm_listening": "Listening", "pm_reading": "Reading"}.get(ans, "Other")
                        preferred_methods_counts[m_label] = preferred_methods_counts.get(m_label, 0) + 1
                    # Difficult subjects
                    if "subject" in qk and isinstance(ans, str) and ans.startswith("subj_"):
                        s_name = {"subj_math": "Mathematics", "subj_science": "Science", "subj_lang": "Languages", "subj_social": "Social Studies", "subj_all": "All Subjects"}.get(ans, ans)
                        difficult_subject_counts[s_name] = difficult_subject_counts.get(s_name, 0) + 1
                    # Support asked
                    if "support_ask" in qk and ans in ["asa_practice", "asa_teacher", "asa_buddy"]:
                        academic_support_students.add(s["id"])

            cursor.execute("SELECT score FROM checkins WHERE student_id = ? ORDER BY created_at ASC", (s["id"],))
            scores = [r["score"] for r in cursor.fetchall()]
            support_info = evaluate_support_level(scores)
            lvl = support_info["level"]

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

            if reasons or follow_up_status in ["new", "contacted", "in_progress"]:
                students_need_attention.append({
                    "id": s["id"],
                    "name": s["name"],
                    "class_name": s["class_name"],
                    "roll_number": s.get("roll_number", ""),
                    "support_level": lvl,
                    "support_reason": support_info["reason"],
                    "badge_class": support_info["badge_class"],
                    "learning_gaps": gaps,
                    "open_alerts": st_alerts,
                    "has_urgent": has_urgent,
                    "reasons": reasons,
                    "summary_reason": "; ".join(reasons) if reasons else "Follow-up in progress",
                    "follow_up_status": follow_up_status or "new"
                })

        students_need_attention.sort(
            key=lambda x: (not x["has_urgent"], x["support_level"] != "May benefit from support")
        )

        total_assigned = len(students)
        pending_checkins_count = total_assigned - included_students_count

        if included_students_count == 0:
            distribution_data = {
                "has_data": False,
                "empty_message": "No assessments completed yet.",
                "total_assigned": total_assigned,
                "included_count": 0,
                "pending_count": pending_checkins_count,
                "summary_text": f"Based on 0 of {total_assigned} assigned students",
                "pending_text": f"{pending_checkins_count} students pending check-in",
                "categories": {}
            }
        else:
            categories = {}
            for cat in ["Doing Well", "Moderate Concern", "Needs Attention"]:
                c_cnt = distribution_counts.get(cat, 0)
                c_pct = round((c_cnt / included_students_count) * 100.0, 1)
                categories[cat] = {
                    "count": c_cnt,
                    "percentage": c_pct,
                    "display": f"{cat}: {c_cnt} students ({c_pct}%)"
                }
            distribution_data = {
                "has_data": True,
                "total_assigned": total_assigned,
                "included_count": included_students_count,
                "pending_count": pending_checkins_count,
                "summary_text": f"Based on {included_students_count} of {total_assigned} assigned students",
                "pending_text": f"{pending_checkins_count} students pending check-in",
                "categories": categories,
                "counts": distribution_counts
            }

        avg_und = round(sum(understanding_scores) / max(len(understanding_scores), 1), 1) if understanding_scores else None
        tot_qc = question_comfort_counts["comfortable"] + question_comfort_counts["hesitant"]
        qc_pct = round((question_comfort_counts["comfortable"] / tot_qc) * 100.0, 1) if tot_qc > 0 else None
        tot_pace = sum(pace_counts.values())
        pace_breakdown = {
            "just_right": round((pace_counts["just_right"] / tot_pace) * 100.0, 1) if tot_pace > 0 else 0.0,
            "fast": round((pace_counts["fast"] / tot_pace) * 100.0, 1) if tot_pace > 0 else 0.0,
            "slow": round((pace_counts["slow"] / tot_pace) * 100.0, 1) if tot_pace > 0 else 0.0
        }
        teaching_insights = {
            "average_lesson_understanding_pct": avg_und,
            "classroom_participation_pct": qc_pct,
            "teaching_pace_feedback": pace_breakdown,
            "preferred_learning_methods": [
                {"method": k, "count": v} for k, v in sorted(preferred_methods_counts.items(), key=lambda x: x[1], reverse=True)
            ],
            "academic_support_required_count": len(academic_support_students),
            "difficult_subjects": [
                {"subject": k, "count": v} for k, v in sorted(difficult_subject_counts.items(), key=lambda x: x[1], reverse=True)
            ]
        }

        return {
            "role": "teacher",
            "total_students": len(students),
            "class_average_mark": class_average_mark,
            "open_alerts_count": open_alerts_count,
            "wellbeing_distribution": distribution_data,
            "teaching_insights": teaching_insights,
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

        # Privacy filtering for student role:
        # Students must NOT see internal labels such as "Needs Attention", teacher notes, or follow-up flags.
        if current_user["role"] == "student":
            return {
                "student": {
                    "id": student_dict["id"],
                    "name": student_dict["name"],
                    "roll_number": student_dict.get("roll_number", ""),
                    "class_name": student_dict["class_name"],
                    "teacher_name": student_dict.get("teacher_name", "")
                },
                "assessments": assessments,
                "learning_gaps": learning_gaps,
                "checkins": [{
                    "id": c["id"],
                    "created_at": c["created_at"],
                    "note": c["note"]
                } for c in checkins_out],
                "recommendations": recommendations,
                "alerts": [],
                "observations": [],
                "disclaimer": DISCLAIMER_TEXT,
            }

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
#  PHASE 4 – Adaptive Mental Health Check-In Engine
# ─────────────────────────────────────────────

@app.get("/api/checkins/active")
def get_active_checkin_session(current_user: dict = Depends(require_student)):
    """Checks if the logged-in student has an in_progress adaptive check-in session."""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM students WHERE user_id = ? AND is_archived = 0", (current_user["id"],))
        st = cursor.fetchone()
        if not st:
            return {"active": False}
        cursor.execute("""
            SELECT s.*, q.domain, q.question_text, q.answer_type, q.options_json, q.prefer_not_to_answer
            FROM check_in_sessions s
            LEFT JOIN check_in_questions q ON s.current_question_id = q.id
            WHERE s.student_id = ? AND s.status = 'in_progress'
            ORDER BY s.started_at DESC LIMIT 1
        """, (st["id"],))
        row = cursor.fetchone()
        if not row:
            return {"active": False}
        opts = json.loads(row["options_json"]) if row["options_json"] else []
        public_opts = [{"id": o["id"], "label": o["label"]} for o in opts]
        history = json.loads(row["question_history_json"]) if row["question_history_json"] else []
        return {
            "active": True,
            "session_id": row["id"],
            "question": {
                "id": row["current_question_id"],
                "domain": row["domain"],
                "question_text": row["question_text"],
                "answer_type": row["answer_type"],
                "options": public_opts,
                "prefer_not_to_answer": bool(row["prefer_not_to_answer"])
            },
            "total_answered": len(history),
            "progress_pct": min(round((len(history) / 12) * 100), 95),
            "disclaimer": DISCLAIMER_TEXT
        }

@app.post("/api/checkins/start")
def start_adaptive_checkin(current_user: dict = Depends(require_student)):
    """Initializes a new adaptive check-in session with questions dynamically selected by the backend."""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM students WHERE user_id = ? AND is_archived = 0", (current_user["id"],))
        student = cursor.fetchone()
        if not student:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Student profile not linked to this account.")

        session_id = str(uuid.uuid4())
        now = _now()

        # Fetch first root question
        cursor.execute("SELECT * FROM check_in_questions WHERE is_root = 1 ORDER BY root_order ASC LIMIT 1")
        first_q = cursor.fetchone()
        if not first_q:
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Question bank not initialized.")

        cursor.execute("""
            INSERT INTO check_in_sessions (id, student_id, status, current_question_id,
                                          question_history_json, answers_json, domain_scores_json,
                                          concern_tags_json, started_at)
            VALUES (?, ?, 'in_progress', ?, '[]', '{}', '{}', '[]', ?)
        """, (session_id, student["id"], first_q["id"], now))

        write_audit_log(conn, current_user["id"], current_user.get("username") or "",
                        "START_ADAPTIVE_CHECKIN", "CHECKIN_SESSION", None,
                        f"Student '{student['name']}' started adaptive check-in")

        opts = json.loads(first_q["options_json"])
        public_opts = [{"id": o["id"], "label": o["label"]} for o in opts]

        return {
            "status": "in_progress",
            "session_id": session_id,
            "question": {
                "id": first_q["id"],
                "domain": first_q["domain"],
                "question_text": first_q["question_text"],
                "answer_type": first_q["answer_type"],
                "options": public_opts,
                "prefer_not_to_answer": bool(first_q["prefer_not_to_answer"])
            },
            "total_answered": 0,
            "progress_pct": 0,
            "disclaimer": DISCLAIMER_TEXT
        }

@app.post("/api/checkins/{session_id}/answer")
def answer_adaptive_checkin(session_id: str, req: AdaptiveAnswerRequest, current_user: dict = Depends(require_student)):
    """Receives student's answer, updates concern levels, and dynamically returns the next question or completion result."""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM students WHERE user_id = ? AND is_archived = 0", (current_user["id"],))
        student = cursor.fetchone()
        if not student:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Student profile not linked to this account.")

        cursor.execute("SELECT * FROM check_in_sessions WHERE id = ? AND student_id = ? AND status = 'in_progress'",
                       (session_id, student["id"]))
        session = cursor.fetchone()
        if not session:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Active check-in session not found or already completed.")

        cursor.execute("SELECT * FROM check_in_questions WHERE id = ?", (req.question_id,))
        q_row = cursor.fetchone()
        if not q_row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Question not found in database.")

        q_domain = q_row["domain"]
        q_opts = json.loads(q_row["options_json"])
        q_rules = json.loads(q_row["branching_rules_json"]) if q_row["branching_rules_json"] else {}
        history = json.loads(session["question_history_json"])
        answers = json.loads(session["answers_json"])
        domain_scores = json.loads(session["domain_scores_json"])
        tags_accum = set(json.loads(session["concern_tags_json"]))

        ans_score = 0.0
        ans_tags = []
        is_urgent = False

        if req.preferred_not_to_answer:
            ans_score = 0.0
            ans_tags.append("preferred_not_to_answer")
        elif q_row["answer_type"] == "optional_free_text":
            text_val = str(req.answer or req.note or "")
            is_u, matched_kw = check_text_for_safeguarding(text_val)
            if is_u:
                is_urgent = True
                ans_score = 1.0
                ans_tags.append("urgent_safeguarding")
        elif q_row["answer_type"] == "multi_choice":
            chosen = req.answer if isinstance(req.answer, list) else [req.answer]
            matched_opts = [o for o in q_opts if o["id"] in chosen]
            if matched_opts:
                ans_score = max(o.get("concern_score", 0.0) for o in matched_opts)
                for o in matched_opts:
                    ans_tags.extend(o.get("tags", []))
                    if "urgent_safeguarding" in o.get("tags", []):
                        is_urgent = True
        else: # single_choice, scale
            chosen = str(req.answer)
            matched_opt = next((o for o in q_opts if o["id"] == chosen), None)
            if matched_opt:
                ans_score = matched_opt.get("concern_score", 0.0)
                ans_tags.extend(matched_opt.get("tags", []))
                if "urgent_safeguarding" in matched_opt.get("tags", []):
                    is_urgent = True

        if req.note:
            is_u_note, _ = check_text_for_safeguarding(req.note)
            if is_u_note:
                is_urgent = True
                ans_tags.append("urgent_safeguarding")

        if is_urgent:
            cursor.execute("""
                SELECT id FROM alerts WHERE student_id = ? AND alert_type = 'safety' AND status = 'open'
            """, (student["id"],))
            if not cursor.fetchone():
                now_u = _now()
                cursor.execute("""
                    INSERT INTO alerts (student_id, alert_type, title, message, severity, status, subject, created_at, updated_at)
                    VALUES (?, 'safety', ?, ?, 'urgent', 'open', '', ?, ?)
                """, (student["id"], f"🚨 Urgent Safeguarding Notice: {student['name']}",
                      SAFEGUARDING_TEACHER_ALERT_MESSAGE, now_u, now_u))

        tags_accum.update(ans_tags)

        answers[req.question_id] = {
            "answer": req.answer,
            "preferred_not_to_answer": req.preferred_not_to_answer,
            "score": ans_score,
            "tags": ans_tags,
            "question_text": q_row["question_text"],
            "domain": q_domain,
            "note": req.note
        }

        domain_q_scores = [a["score"] for a in answers.values() if a.get("domain") == q_domain and not a.get("preferred_not_to_answer")]
        if domain_q_scores:
            domain_scores[q_domain] = round(sum(domain_q_scores) / len(domain_q_scores), 2)

        if req.question_id not in history:
            history.append(req.question_id)

        next_q_row = None

        # 1. Branching rule follow-ups
        follow_ups = q_rules.get("follow_ups", {})
        if isinstance(req.answer, list):
            for opt_id in req.answer:
                target_qid = follow_ups.get(opt_id)
                if target_qid and target_qid not in history:
                    cursor.execute("SELECT * FROM check_in_questions WHERE id = ?", (target_qid,))
                    next_q_row = cursor.fetchone()
                    if next_q_row:
                        break
        elif isinstance(req.answer, str):
            target_qid = follow_ups.get(req.answer)
            if target_qid and target_qid not in history:
                cursor.execute("SELECT * FROM check_in_questions WHERE id = ?", (target_qid,))
                next_q_row = cursor.fetchone()

        # 2. Check next root question
        if not next_q_row:
            ph = ",".join("?" for _ in history) if history else "''"
            cursor.execute(f"""
                SELECT * FROM check_in_questions
                WHERE is_root = 1 AND id NOT IN ({ph})
                ORDER BY root_order ASC LIMIT 1
            """, history)
            next_q_row = cursor.fetchone()

        # 3. Check for early completion
        max_concern = max(domain_scores.values()) if domain_scores else 0.0
        hard_max_reached = len(history) >= 25
        natural_end = (next_q_row is None) or (len(history) >= 8 and next_q_row is None and max_concern < 0.35)

        if hard_max_reached or natural_end:
            now = _now()
            scoring_res = evaluate_adaptive_checkin_scoring(domain_scores, answers, is_urgent or ("urgent_safeguarding" in tags_accum))

            overall_concern = scoring_res["overall_score"]
            scaled_score = round(max(1.0, min(5.0, 5.0 - overall_concern * 4.0)), 2)

            mood_val = 5 - int(domain_scores.get("Mood & Emotions", 0.0) * 4)
            stress_val = 1 + int(domain_scores.get("Stress & Pressure", 0.0) * 4)
            sleep_val = 5 - int(domain_scores.get("Daily Routine & Habits", 0.0) * 4)
            focus_val = 5 - int(domain_scores.get("Concentration & Focus", 0.0) * 4)
            belonging_val = 5 - int(domain_scores.get("Social & School Experience", 0.0) * 4)

            note_pieces = [a["note"] for a in answers.values() if a.get("note")]
            combined_notes = " | ".join(note_pieces) if note_pieces else None
            encrypted_note = encrypt_note(combined_notes) if combined_notes else None

            cursor.execute("""
                INSERT INTO checkins (
                    student_id, mood, stress, sleep, focus, belonging,
                    encrypted_note, score, created_at, session_id,
                    wellbeing_indicator, indicator_reasons, domain_scores_json,
                    academic_concerns_json, teaching_concerns_json, recommendations_json,
                    urgent_flag, follow_up_status, answers_snapshot_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                student["id"], mood_val, stress_val, sleep_val, focus_val, belonging_val,
                encrypted_note, scaled_score, now, session_id,
                scoring_res["wellbeing_indicator"],
                json.dumps(scoring_res["indicator_reasons"]),
                json.dumps(domain_scores),
                json.dumps([k for k, v in answers.items() if "academic" in k]),
                json.dumps([k for k, v in answers.items() if "teaching" in k]),
                json.dumps(scoring_res["recommendations"]),
                1 if scoring_res["urgent_flag"] else 0,
                "pending" if scoring_res["wellbeing_indicator"] != "Doing Well" else "none",
                json.dumps(answers)
            ))
            checkin_id = cursor.lastrowid

            cursor.execute("""
                UPDATE check_in_sessions
                SET status = 'completed', question_history_json = ?, answers_json = ?,
                    domain_scores_json = ?, concern_tags_json = ?, completed_at = ?
                WHERE id = ?
            """, (json.dumps(history), json.dumps(answers), json.dumps(domain_scores),
                  json.dumps(list(tags_accum)), now, session_id))

            sg_name = _get_setting(conn, "safeguarding_contact_name", "")
            sg_phone = _get_setting(conn, "safeguarding_contact_phone", "")
            sg_email = _get_setting(conn, "safeguarding_contact_email", "")

            student_calm_msg = DEFAULT_STUDENT_CALM_MESSAGE
            if sg_name:
                contact_details = f"{sg_name} ({sg_phone or sg_email or 'Safeguarding Lead'})"
                student_calm_msg = (
                    f"Thank you for sharing with us. Your well-being matters to us deeply. "
                    f"If you need to talk right now, please reach out to {contact_details} or your class teacher."
                )

            if scoring_res["urgent_flag"]:
                cursor.execute("""
                    INSERT INTO alerts (student_id, alert_type, title, message, severity, status, subject, created_at, updated_at)
                    VALUES (?, 'safety', ?, ?, 'urgent', 'open', '', ?, ?)
                """, (student["id"], f"🚨 Urgent Safeguarding Notice: {student['name']}",
                      SAFEGUARDING_TEACHER_ALERT_MESSAGE, now, now))
            elif scoring_res["wellbeing_indicator"] == "Needs Attention":
                cursor.execute("""
                    INSERT INTO alerts (student_id, alert_type, title, message, severity, status, subject, created_at, updated_at)
                    VALUES (?, 'support_level', ?, ?, 'standard', 'open', '', ?, ?)
                """, (student["id"], f"Well-being follow-up needed: {student['name']}",
                      f"Well-being indicator: {'; '.join(scoring_res['indicator_reasons'])}", now, now))

            write_audit_log(conn, current_user["id"], current_user.get("username") or "",
                            "COMPLETE_ADAPTIVE_CHECKIN", "CHECKIN", checkin_id,
                            f"Student '{student['name']}' completed adaptive check-in. Indicator: {scoring_res['wellbeing_indicator']}")

            return {
                "status": "completed",
                "wellbeing_indicator": scoring_res["wellbeing_indicator"],
                "recommendations": scoring_res["recommendations"],
                "total_answered": len(history),
                "urgent_flag": scoring_res["urgent_flag"],
                "safeguarding_message": student_calm_msg if scoring_res["urgent_flag"] else None,
                "disclaimer": DISCLAIMER_TEXT
            }

        cursor.execute("""
            UPDATE check_in_sessions
            SET current_question_id = ?, question_history_json = ?, answers_json = ?,
                domain_scores_json = ?, concern_tags_json = ?
            WHERE id = ?
        """, (next_q_row["id"], json.dumps(history), json.dumps(answers),
              json.dumps(domain_scores), json.dumps(list(tags_accum)), session_id))

        next_opts = json.loads(next_q_row["options_json"])
        public_next_opts = [{"id": o["id"], "label": o["label"]} for o in next_opts]

        return {
            "status": "in_progress",
            "session_id": session_id,
            "question": {
                "id": next_q_row["id"],
                "domain": next_q_row["domain"],
                "question_text": next_q_row["question_text"],
                "answer_type": next_q_row["answer_type"],
                "options": public_next_opts,
                "prefer_not_to_answer": bool(next_q_row["prefer_not_to_answer"])
            },
            "total_answered": len(history),
            "progress_pct": min(round((len(history) / 12) * 100), 95),
            "disclaimer": DISCLAIMER_TEXT
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

@app.put("/api/students/{student_id}/follow-up")
def update_student_followup_status(student_id: int, req: FollowUpStatusUpdateRequest, current_user: dict = Depends(require_teacher_or_admin)):
    status_val = req.status.strip().lower().replace(" ", "_")
    valid_statuses = ["new", "contacted", "in_progress", "resolved"]
    if status_val not in valid_statuses:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Invalid status. Choose from {valid_statuses}")
    with get_db() as conn:
        cursor = conn.cursor()
        student = _get_student_or_404(cursor, student_id)
        check_student_record_access(current_user, student)
        now = _now()
        cursor.execute("UPDATE checkins SET follow_up_status = ? WHERE student_id = ?", (status_val, student_id))
        cursor.execute("""
            INSERT INTO observations (student_id, teacher_id, observation_text, follow_up_action, status, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (student_id, current_user["id"], req.notes or f"Follow-up status set to {status_val}", f"Workflow status: {status_val}", status_val, now, now))
        write_audit_log(conn, current_user["id"], current_user.get("email", ""),
                        "UPDATE_FOLLOWUP_STATUS", "STUDENT", student_id,
                        f"Updated follow-up status for '{student['name']}' to '{status_val}'")
        return {"student_id": student_id, "follow_up_status": status_val, "updated_at": now}

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
