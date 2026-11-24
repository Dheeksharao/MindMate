import os
import time
import bcrypt
import jwt
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, Any
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from database import get_db

JWT_SECRET = os.environ.get("MINDMATE_JWT_SECRET", "mindmate-super-secret-jwt-key-2026-change-in-production")
JWT_ALGORITHM = "HS256"
JWT_EXPIRATION_SECONDS = 86400 * 7  # 7 days

MAX_LOGIN_ATTEMPTS = 5
LOCKOUT_MINUTES = 15

security = HTTPBearer(auto_error=False)

GENERIC_LOGIN_ERROR = "Incorrect email/username or password."
INACTIVE_ERROR = "Your account is inactive. Please contact the administrator."
UNASSIGNED_ERROR = "Your account has not been assigned to a class/mentor yet. Please contact the administrator."

def hash_password(password: str) -> str:
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(password.encode("utf-8"), salt).decode("utf-8")

def verify_password(plain_password: str, hashed_password: str) -> bool:
    try:
        return bcrypt.checkpw(plain_password.encode("utf-8"), hashed_password.encode("utf-8"))
    except Exception:
        return False

def create_access_token(user_data: dict) -> str:
    payload = {
        "sub": str(user_data["id"]),
        "email": user_data.get("email") or "",
        "username": user_data.get("username") or "",
        "role": user_data["role"],
        "full_name": user_data["full_name"],
        "assigned_classes": user_data.get("assigned_classes", ""),
        "must_change_password": user_data.get("must_change_password", 0),
        "exp": int(time.time()) + JWT_EXPIRATION_SECONDS
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)

def decode_access_token(token: str) -> Optional[dict]:
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        return payload
    except Exception:
        return None

def get_current_user(credentials: Optional[HTTPAuthorizationCredentials] = Depends(security)) -> Dict[str, Any]:
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
            headers={"WWW-Authenticate": "Bearer"},
        )
    token = credentials.credentials
    payload = decode_access_token(token)
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired session token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    user_id = payload.get("sub")
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, email, username, full_name, role, is_active, assigned_classes,
                   check_in_pin, must_change_password, failed_login_attempts, lockout_until
            FROM users WHERE id = ?
        """, (user_id,))
        row = cursor.fetchone()
        if not row:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User account no longer exists",
            )
        user_dict = dict(row)
        if not user_dict.get("is_active", 1):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=INACTIVE_ERROR
            )
        return user_dict

def authenticate_user(identifier: str, password: str, portal: str) -> dict:
    """
    Authenticate a user for a specific portal ('admin', 'teacher', 'student').
    Returns user dict on success.
    Raises HTTPException with appropriate message on failure.
    Portal/role mismatch returns the GENERIC error (never reveals account existence).
    """
    with get_db() as conn:
        cursor = conn.cursor()

        # Find by email or username
        identifier_clean = identifier.strip().lower()
        cursor.execute("""
            SELECT * FROM users
            WHERE (LOWER(email) = ? OR LOWER(username) = ?)
        """, (identifier_clean, identifier_clean))
        user = cursor.fetchone()

        # Check lockout first (if user found)
        if user:
            user_dict = dict(user)
            lockout_until = user_dict.get("lockout_until")
            if lockout_until:
                lock_dt = datetime.fromisoformat(lockout_until)
                if datetime.now(timezone.utc) < lock_dt:
                    # Still locked – don't reveal why, give generic error
                    raise HTTPException(
                        status_code=status.HTTP_401_UNAUTHORIZED,
                        detail=GENERIC_LOGIN_ERROR
                    )
                else:
                    # Lockout expired, clear it
                    cursor.execute(
                        "UPDATE users SET lockout_until = NULL, failed_login_attempts = 0, updated_at = ? WHERE id = ?",
                        (datetime.now(timezone.utc).isoformat(), user_dict["id"])
                    )
                    conn.commit()

        # Verify password
        if not user or not verify_password(password, user["password_hash"]):
            if user:
                new_attempts = (user["failed_login_attempts"] or 0) + 1
                if new_attempts >= MAX_LOGIN_ATTEMPTS:
                    lockout_time = (datetime.now(timezone.utc) + timedelta(minutes=LOCKOUT_MINUTES)).isoformat()
                    cursor.execute(
                        "UPDATE users SET failed_login_attempts = ?, lockout_until = ?, updated_at = ? WHERE id = ?",
                        (new_attempts, lockout_time, datetime.now(timezone.utc).isoformat(), user["id"])
                    )
                else:
                    cursor.execute(
                        "UPDATE users SET failed_login_attempts = ?, updated_at = ? WHERE id = ?",
                        (new_attempts, datetime.now(timezone.utc).isoformat(), user["id"])
                    )
                conn.commit()
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=GENERIC_LOGIN_ERROR
            )

        user_dict = dict(user)

        # Role must match portal (use GENERIC error so we don't reveal account existence)
        if user_dict["role"] != portal:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=GENERIC_LOGIN_ERROR
            )

        # Check active status (after password verified = safe to reveal this)
        if not user_dict.get("is_active", 1):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=INACTIVE_ERROR
            )

        # For students: check assignment
        if portal == "student":
            cursor.execute(
                "SELECT assigned_teacher_id, class_name FROM students WHERE user_id = ? AND is_archived = 0",
                (user_dict["id"],)
            )
            student_row = cursor.fetchone()
            if not student_row:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=INACTIVE_ERROR
                )
            if not student_row["assigned_teacher_id"] and not student_row["class_name"]:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=UNASSIGNED_ERROR
                )

        # For teachers: check at least one class or student assigned
        if portal == "teacher":
            has_classes = bool(user_dict.get("assigned_classes", "").strip())
            cursor.execute(
                "SELECT COUNT(*) AS cnt FROM students WHERE assigned_teacher_id = ? AND is_archived = 0",
                (user_dict["id"],)
            )
            has_students = cursor.fetchone()["cnt"] > 0
            if not has_classes and not has_students:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=UNASSIGNED_ERROR
                )

        # Clear failed attempts on successful login
        cursor.execute(
            "UPDATE users SET failed_login_attempts = 0, lockout_until = NULL, updated_at = ? WHERE id = ?",
            (datetime.now(timezone.utc).isoformat(), user_dict["id"])
        )
        conn.commit()

        return user_dict

def check_teacher_class_access(user: dict, class_name: str, student: Optional[dict] = None) -> None:
    if user["role"] == "admin":
        return
    if user["role"] == "teacher":
        if student and student.get("assigned_teacher_id") == user["id"]:
            return
        assigned = [c.strip() for c in user.get("assigned_classes", "").split(",") if c.strip()]
        if "*" not in assigned and class_name not in assigned:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access denied: You are not authorised for class '{class_name}'."
            )
        return
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Access denied: Teacher permissions required."
    )

def check_student_record_access(user: dict, student: dict) -> None:
    if user["role"] == "admin":
        return
    if user["role"] == "student":
        if student.get("user_id") != user["id"]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied: Students can only view their own record."
            )
        return
    if user["role"] == "teacher":
        if student.get("assigned_teacher_id") == user["id"]:
            return
        assigned = [c.strip() for c in user.get("assigned_classes", "").split(",") if c.strip()]
        if "*" not in assigned and student.get("class_name") not in assigned:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access denied: Student is not in your assigned classes."
            )
        return
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Access denied: Unauthorised role."
    )

def require_admin(user: dict = Depends(get_current_user)) -> dict:
    if user["role"] != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden: Administrator role required.")
    return user

def require_teacher(user: dict = Depends(get_current_user)) -> dict:
    if user["role"] != "teacher":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden: Teacher role required.")
    return user

def require_student(user: dict = Depends(get_current_user)) -> dict:
    if user["role"] != "student":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden: Student role required.")
    return user

def require_teacher_or_admin(user: dict = Depends(get_current_user)) -> dict:
    if user["role"] not in ["teacher", "admin"]:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden: Teacher or Administrator role required.")
    return user
