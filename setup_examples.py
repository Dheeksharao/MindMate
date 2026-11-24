import sys
from datetime import datetime, timezone
from pathlib import Path

from database import init_db, get_db
from auth import hash_password

def create_examples():
    init_db()
    with get_db() as conn:
        cursor = conn.cursor()
        now_iso = datetime.now(timezone.utc).isoformat()

        # 1. Administrator Example
        admin_email = "admin@oakridge.edu"
        cursor.execute("SELECT id FROM users WHERE email = ?", (admin_email,))
        if not cursor.fetchone():
            cursor.execute("""
                INSERT INTO users (email, password_hash, full_name, role, is_active, assigned_classes, kiosk_pin, created_at)
                VALUES (?, ?, 'Dr. Eleanor Vance', 'admin', 1, '', '9999', ?)
            """, (admin_email, hash_password("Admin@2026"), now_iso))
            admin_id = cursor.lastrowid
            print(f"✓ Created Administrator: {admin_email} / Admin@2026")
        else:
            print(f"• Administrator {admin_email} already exists.")

        # 2. Teacher Example
        teacher_email = "mrs.jenkins@oakridge.edu"
        cursor.execute("SELECT id FROM users WHERE email = ?", (teacher_email,))
        t_row = cursor.fetchone()
        if not t_row:
            cursor.execute("""
                INSERT INTO users (email, password_hash, full_name, role, is_active, assigned_classes, kiosk_pin, created_at)
                VALUES (?, ?, 'Sarah Jenkins', 'teacher', 1, 'Grade 9A', '1234', ?)
            """, (teacher_email, hash_password("Teacher@2026"), now_iso))
            teacher_id = cursor.lastrowid
            print(f"✓ Created Teacher: {teacher_email} / Teacher@2026 (PIN: 1234, Class: Grade 9A)")
        else:
            teacher_id = t_row["id"]
            print(f"• Teacher {teacher_email} already exists.")

        # 3. Student Example (User account + Student record)
        student_email = "maya.patel@oakridge.edu"
        cursor.execute("SELECT id FROM users WHERE email = ?", (student_email,))
        s_user_row = cursor.fetchone()
        if not s_user_row:
            cursor.execute("""
                INSERT INTO users (email, password_hash, full_name, role, is_active, assigned_classes, kiosk_pin, created_at)
                VALUES (?, ?, 'Maya Patel', 'student', 1, '', '0000', ?)
            """, (student_email, hash_password("Student@2026"), now_iso))
            student_user_id = cursor.lastrowid
            print(f"✓ Created Student Login: {student_email} / Student@2026")
        else:
            student_user_id = s_user_row["id"]

        cursor.execute("SELECT id FROM students WHERE user_id = ?", (student_user_id,))
        if not cursor.fetchone():
            cursor.execute("""
                INSERT INTO students (user_id, assigned_teacher_id, name, class_name, guardian_name, guardian_contact, consent_given, is_archived, created_at, updated_at)
                VALUES (?, ?, 'Maya Patel', 'Grade 9A', 'Sunita Patel', '+1-555-0102', 1, 0, ?, ?)
            """, (student_user_id, teacher_id, now_iso, now_iso))
            print("✓ Enrolled Maya Patel into Grade 9A (Assigned Teacher: Sarah Jenkins)")
        else:
            print("• Student record for Maya Patel already enrolled.")

        print("\nAll 3 example accounts are ready to use in your database!")

if __name__ == "__main__":
    create_examples()
