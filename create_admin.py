import argparse
import sys
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
                SET password_hash = ?, full_name = ?, role = 'admin', is_active = 1
                WHERE id = ?
            """, (hash_password(password), full_name.strip(), existing["id"]))
            print(f"Updated existing user '{email}' to active Administrator.")
        else:
            cursor.execute("""
                INSERT INTO users (email, password_hash, full_name, role, is_active, assigned_classes, kiosk_pin, created_at)
                VALUES (?, ?, ?, 'admin', 1, '', '9999', ?)
            """, (email.strip().lower(), hash_password(password), full_name.strip(), now_iso))
            print(f"Created new Administrator account: '{email}'.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Create or update an Administrator account for MindMate.")
    parser.add_argument("--email", default="admin@mindmate.edu", help="Admin email address")
    parser.add_argument("--password", default="Admin@123", help="Admin password")
    parser.add_argument("--name", default="System Administrator", help="Admin full name")
    
    args = parser.parse_args()
    create_admin(args.email, args.password, args.name)
