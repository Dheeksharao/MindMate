import sys
import getpass
from datetime import datetime, timezone
from pathlib import Path

from database import init_db, get_db
from auth import hash_password

def create_admin(email: str, password: str, full_name: str):
    init_db()
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM users WHERE email = ?", (email.strip().lower(),))
        existing = cursor.fetchone()
        now_iso = datetime.now(timezone.utc).isoformat()
        
        if existing:
            cursor.execute("""
                UPDATE users
                SET password_hash = ?, full_name = ?, role = 'admin', is_active = 1, updated_at = ?
                WHERE id = ?
            """, (hash_password(password), full_name.strip(), now_iso, existing["id"]))
            print(f"Updated existing user '{email}' to active Administrator.")
        else:
            cursor.execute("""
                INSERT INTO users (email, username, password_hash, full_name, role, is_active, assigned_classes, check_in_pin, created_at, updated_at)
                VALUES (?, NULL, ?, ?, 'admin', 1, '', '9999', ?, ?)
            """, (email.strip().lower(), hash_password(password), full_name.strip(), now_iso, now_iso))
            print(f"Created new Administrator account: '{email}'.")

if __name__ == "__main__":
    init_db()
    with get_db() as conn:
        if conn.execute("SELECT 1 FROM users WHERE role = 'admin' LIMIT 1").fetchone():
            raise SystemExit("An administrator already exists. Use the admin portal to manage accounts.")

    email = input("Administrator email: ").strip().lower()
    full_name = input("Administrator full name: ").strip()
    password = getpass.getpass("Administrator password: ")
    confirmation = getpass.getpass("Confirm password: ")
    if not email or not full_name:
        raise SystemExit("Email and full name are required.")
    if len(password) < 8:
        raise SystemExit("Password must be at least 8 characters.")
    if password != confirmation:
        raise SystemExit("Passwords do not match.")
    create_admin(email, password, full_name)
