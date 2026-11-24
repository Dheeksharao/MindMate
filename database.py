import sqlite3
from pathlib import Path
from contextlib import contextmanager
from typing import Generator

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "mindmate.db"

def get_db_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn

@contextmanager
def get_db() -> Generator[sqlite3.Connection, None, None]:
    conn = get_db_connection()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

def init_db():
    with get_db() as conn:
        cursor = conn.cursor()

        # 1. users: admin, teacher, student
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT UNIQUE,
            username TEXT UNIQUE,          -- for student login (no email required)
            password_hash TEXT NOT NULL,
            full_name TEXT NOT NULL,
            role TEXT NOT NULL,            -- 'admin', 'teacher', 'student'
            is_active INTEGER NOT NULL DEFAULT 1,
            assigned_classes TEXT NOT NULL DEFAULT '',
            check_in_pin TEXT NOT NULL DEFAULT '1234',
            must_change_password INTEGER NOT NULL DEFAULT 0,
            failed_login_attempts INTEGER NOT NULL DEFAULT 0,
            lockout_until TEXT,            -- ISO timestamp, NULL if not locked
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );
        """)

        # 2. students
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS students (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER UNIQUE REFERENCES users(id) ON DELETE SET NULL,
            assigned_teacher_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
            name TEXT NOT NULL,
            roll_number TEXT NOT NULL DEFAULT '',
            class_name TEXT NOT NULL,
            guardian_name TEXT NOT NULL,
            guardian_contact TEXT NOT NULL,
            consent_given INTEGER NOT NULL DEFAULT 1,
            is_archived INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );
        """)

        # 3. assessments
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS assessments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id INTEGER NOT NULL REFERENCES students(id) ON DELETE CASCADE,
            subject TEXT NOT NULL,
            score REAL NOT NULL,
            max_score REAL NOT NULL DEFAULT 100.0,
            date TEXT NOT NULL,
            notes TEXT DEFAULT '',
            created_at TEXT NOT NULL
        );
        """)

        # 4. checkins
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS checkins (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id INTEGER NOT NULL REFERENCES students(id) ON DELETE CASCADE,
            mood INTEGER NOT NULL,
            stress INTEGER NOT NULL,
            sleep INTEGER NOT NULL,
            focus INTEGER NOT NULL,
            belonging INTEGER NOT NULL,
            encrypted_note TEXT,
            score REAL NOT NULL,
            created_at TEXT NOT NULL
        );
        """)

        # 5. alerts
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS alerts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id INTEGER NOT NULL REFERENCES students(id) ON DELETE CASCADE,
            alert_type TEXT NOT NULL,      -- 'safety', 'support_level', 'learning_gap'
            title TEXT NOT NULL,
            message TEXT NOT NULL,
            severity TEXT NOT NULL DEFAULT 'standard',  -- 'standard' or 'urgent'
            status TEXT NOT NULL DEFAULT 'open',        -- 'open', 'acknowledged', 'snoozed', 'resolved'
            subject TEXT DEFAULT '',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );
        """)

        # 6. observations & follow-ups
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS observations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id INTEGER NOT NULL REFERENCES students(id) ON DELETE CASCADE,
            teacher_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            observation_text TEXT NOT NULL,
            follow_up_action TEXT DEFAULT '',
            status TEXT NOT NULL DEFAULT 'new',  -- 'new', 'contacted', 'in_progress', 'resolved'
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );
        """)

        # 7. recommendations
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS recommendations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id INTEGER NOT NULL REFERENCES students(id) ON DELETE CASCADE,
            teacher_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
            category TEXT NOT NULL,
            title TEXT NOT NULL,
            action_plan TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'open',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );
        """)

        # 8. assignment_history: tracks mentor changes
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS assignment_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id INTEGER NOT NULL REFERENCES students(id) ON DELETE CASCADE,
            old_teacher_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
            new_teacher_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
            changed_by INTEGER REFERENCES users(id) ON DELETE SET NULL,
            reason TEXT DEFAULT '',
            changed_at TEXT NOT NULL
        );
        """)

        # 9. settings: admin-configurable app settings
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );
        """)

        # 10. audit_logs
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS audit_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
            user_email TEXT NOT NULL,
            action TEXT NOT NULL,
            resource_type TEXT NOT NULL,
            resource_id INTEGER,
            details TEXT NOT NULL,
            timestamp TEXT NOT NULL
        );
        """)

        # ---- Migrations for existing tables ----
        cursor.execute("PRAGMA table_info(users)")
        user_cols = [r["name"] for r in cursor.fetchall()]
        if "is_active" not in user_cols:
            cursor.execute("ALTER TABLE users ADD COLUMN is_active INTEGER NOT NULL DEFAULT 1")
        if "username" not in user_cols:
            cursor.execute("ALTER TABLE users ADD COLUMN username TEXT UNIQUE")
        if "check_in_pin" not in user_cols:
            # rename kiosk_pin -> check_in_pin if it exists, else just add
            if "kiosk_pin" in user_cols:
                # SQLite can't rename columns in older versions; add new + copy
                cursor.execute("ALTER TABLE users ADD COLUMN check_in_pin TEXT NOT NULL DEFAULT '1234'")
                cursor.execute("UPDATE users SET check_in_pin = kiosk_pin")
            else:
                cursor.execute("ALTER TABLE users ADD COLUMN check_in_pin TEXT NOT NULL DEFAULT '1234'")
        if "must_change_password" not in user_cols:
            cursor.execute("ALTER TABLE users ADD COLUMN must_change_password INTEGER NOT NULL DEFAULT 0")
        if "failed_login_attempts" not in user_cols:
            cursor.execute("ALTER TABLE users ADD COLUMN failed_login_attempts INTEGER NOT NULL DEFAULT 0")
        if "lockout_until" not in user_cols:
            cursor.execute("ALTER TABLE users ADD COLUMN lockout_until TEXT")
        if "updated_at" not in user_cols:
            cursor.execute("ALTER TABLE users ADD COLUMN updated_at TEXT NOT NULL DEFAULT ''")

        cursor.execute("PRAGMA table_info(students)")
        student_cols = [r["name"] for r in cursor.fetchall()]
        if "user_id" not in student_cols:
            cursor.execute("ALTER TABLE students ADD COLUMN user_id INTEGER REFERENCES users(id) ON DELETE SET NULL")
        if "assigned_teacher_id" not in student_cols:
            cursor.execute("ALTER TABLE students ADD COLUMN assigned_teacher_id INTEGER REFERENCES users(id) ON DELETE SET NULL")
        if "roll_number" not in student_cols:
            cursor.execute("ALTER TABLE students ADD COLUMN roll_number TEXT NOT NULL DEFAULT ''")

        cursor.execute("PRAGMA table_info(observations)")
        obs_cols = [r["name"] for r in cursor.fetchall()]
        if "status" in obs_cols:
            # migrate old 'pending','in_progress','completed' to new statuses
            cursor.execute("UPDATE observations SET status = 'new' WHERE status = 'pending'")
            cursor.execute("UPDATE observations SET status = 'resolved' WHERE status = 'completed'")

        # Seed default settings if not present
        from datetime import datetime, timezone
        now_iso = datetime.now(timezone.utc).isoformat()
        default_settings = {
            "safeguarding_contact_name": "",
            "safeguarding_contact_phone": "",
            "safeguarding_contact_email": "",
            "reporting_window_days": "30",
            "checkin_frequency_days": "7",
        }
        for k, v in default_settings.items():
            cursor.execute(
                "INSERT OR IGNORE INTO settings (key, value, updated_at) VALUES (?, ?, ?)",
                (k, v, now_iso)
            )

        # ---- Indexes ----
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_users_username ON users(username);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_users_role ON users(role);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_students_class ON students(class_name);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_students_user_id ON students(user_id);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_students_teacher_id ON students(assigned_teacher_id);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_students_archived ON students(is_archived);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_assessments_student ON assessments(student_id);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_assessments_student_subject ON assessments(student_id, subject);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_checkins_student ON checkins(student_id);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_checkins_student_date ON checkins(student_id, created_at);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_alerts_student ON alerts(student_id);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_alerts_student_status ON alerts(student_id, status);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_observations_student ON observations(student_id);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_recommendations_student ON recommendations(student_id);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_assignment_history_student ON assignment_history(student_id);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_audit_logs_user_timestamp ON audit_logs(user_id, timestamp);")

if __name__ == "__main__":
    init_db()
    print("Database initialized successfully at:", DB_PATH)
