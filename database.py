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

        # 9. check_in_questions: Question bank in the database (100+ questions across 8+ domains)
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS check_in_questions (
            id TEXT PRIMARY KEY,
            domain TEXT NOT NULL,
            question_text TEXT NOT NULL,
            answer_type TEXT NOT NULL, -- 'single_choice', 'multi_choice', 'scale', 'optional_free_text'
            options_json TEXT NOT NULL, -- JSON array of options: [{"id": "...", "label": "...", "concern_score": 0.0, "tags": [...]}]
            prefer_not_to_answer INTEGER NOT NULL DEFAULT 1,
            version INTEGER NOT NULL DEFAULT 1,
            branching_rules_json TEXT NOT NULL DEFAULT '{}', -- JSON object specifying follow-up conditions
            is_root INTEGER NOT NULL DEFAULT 0, -- 1 if this is part of the core screening flow
            root_order INTEGER NOT NULL DEFAULT 0
        );
        """)

        # 10. check_in_sessions: Active and completed adaptive check-in sessions
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS check_in_sessions (
            id TEXT PRIMARY KEY,
            student_id INTEGER NOT NULL REFERENCES students(id) ON DELETE CASCADE,
            status TEXT NOT NULL DEFAULT 'in_progress', -- 'in_progress', 'completed', 'abandoned'
            current_question_id TEXT REFERENCES check_in_questions(id),
            question_history_json TEXT NOT NULL DEFAULT '[]',
            answers_json TEXT NOT NULL DEFAULT '{}',
            domain_scores_json TEXT NOT NULL DEFAULT '{}',
            concern_tags_json TEXT NOT NULL DEFAULT '[]',
            started_at TEXT NOT NULL,
            completed_at TEXT
        );
        """)

        # 11. settings: admin-configurable app settings
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );
        """)

        # 12. audit_logs
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

        cursor.execute("""
        CREATE TABLE IF NOT EXISTS password_reset_requests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            identifier TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'pending',
            requested_at TEXT NOT NULL,
            resolved_at TEXT,
            resolved_by INTEGER REFERENCES users(id) ON DELETE SET NULL
        );
        """)

        # ---- Migrations for existing tables ----
        cursor.execute("PRAGMA table_info(users)")
        raw_user_info = cursor.fetchall()
        user_info = {r["name"]: r for r in raw_user_info}
        user_cols = list(user_info.keys())

        # If email was created with NOT NULL constraint, recreate users table so student logins without email are supported
        if user_info.get("email") and user_info["email"]["notnull"] == 1:
            cursor.execute("PRAGMA foreign_keys=OFF")
            cursor.execute("""
            CREATE TABLE users_migrated (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                email TEXT UNIQUE,
                username TEXT UNIQUE,
                password_hash TEXT NOT NULL,
                full_name TEXT NOT NULL,
                role TEXT NOT NULL,
                is_active INTEGER NOT NULL DEFAULT 1,
                assigned_classes TEXT NOT NULL DEFAULT '',
                check_in_pin TEXT NOT NULL DEFAULT '1234',
                must_change_password INTEGER NOT NULL DEFAULT 0,
                failed_login_attempts INTEGER NOT NULL DEFAULT 0,
                lockout_until TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            """)
            cursor.execute("""
            INSERT INTO users_migrated (id, email, username, password_hash, full_name, role, is_active, assigned_classes, check_in_pin, must_change_password, failed_login_attempts, lockout_until, created_at, updated_at)
            SELECT id, email, username, password_hash, full_name, role,
                   COALESCE(is_active, 1), COALESCE(assigned_classes, ''),
                   COALESCE(check_in_pin, '1234'), COALESCE(must_change_password, 0),
                   COALESCE(failed_login_attempts, 0), lockout_until,
                   created_at, updated_at
            FROM users;
            """)
            cursor.execute("DROP TABLE users;")
            cursor.execute("ALTER TABLE users_migrated RENAME TO users;")
            cursor.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_users_username_unique ON users(username);")
            cursor.execute("PRAGMA foreign_keys=ON")
            # Refresh user_cols
            cursor.execute("PRAGMA table_info(users)")
            user_cols = [r["name"] for r in cursor.fetchall()]
        if "is_active" not in user_cols:
            cursor.execute("ALTER TABLE users ADD COLUMN is_active INTEGER NOT NULL DEFAULT 1")
        if "username" not in user_cols:
            cursor.execute("ALTER TABLE users ADD COLUMN username TEXT")
            cursor.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_users_username_unique ON users(username)")
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

        cursor.execute("PRAGMA table_info(checkins)")
        checkin_cols = [r["name"] for r in cursor.fetchall()]
        checkin_new_cols = {
            "session_id": "TEXT",
            "wellbeing_indicator": "TEXT DEFAULT ''",
            "indicator_reasons": "TEXT DEFAULT ''",
            "domain_scores_json": "TEXT DEFAULT '{}'",
            "academic_concerns_json": "TEXT DEFAULT '[]'",
            "teaching_concerns_json": "TEXT DEFAULT '[]'",
            "recommendations_json": "TEXT DEFAULT '[]'",
            "urgent_flag": "INTEGER DEFAULT 0",
            "follow_up_status": "TEXT DEFAULT 'none'",
            "answers_snapshot_json": "TEXT DEFAULT '{}'"
        }
        for col, col_def in checkin_new_cols.items():
            if col not in checkin_cols:
                cursor.execute(f"ALTER TABLE checkins ADD COLUMN {col} {col_def}")

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
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_questions_domain ON check_in_questions(domain);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_questions_root ON check_in_questions(is_root, root_order);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_sessions_student ON check_in_sessions(student_id);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_sessions_status ON check_in_sessions(status);")

if __name__ == "__main__":
    init_db()
    print("Database initialized successfully at:", DB_PATH)
