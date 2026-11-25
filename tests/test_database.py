import sqlite3

import database


def test_init_db_migrates_legacy_users_table(monkeypatch, tmp_path):
    db_path = tmp_path / "legacy.db"
    with sqlite3.connect(db_path) as conn:
        conn.executescript("""
            CREATE TABLE users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                email TEXT NOT NULL UNIQUE,
                password_hash TEXT NOT NULL,
                full_name TEXT NOT NULL,
                role TEXT NOT NULL,
                assigned_classes TEXT NOT NULL DEFAULT '',
                kiosk_pin TEXT NOT NULL DEFAULT '1234',
                created_at TEXT NOT NULL
            );
            CREATE TABLE users_migrated (id INTEGER);
            INSERT INTO users (
                email, password_hash, full_name, role, assigned_classes, kiosk_pin, created_at
            ) VALUES (
                'legacy@example.test', 'hashed-password', 'Legacy User', 'teacher',
                'Class A', '5678', '2024-01-02T03:04:05+00:00'
            );
        """)

    monkeypatch.setattr(database, "DB_PATH", db_path)
    database.init_db()

    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        user = conn.execute("SELECT * FROM users WHERE email = ?", ("legacy@example.test",)).fetchone()

    assert user["username"] is None
    assert user["check_in_pin"] == "5678"
    assert user["is_active"] == 1
    assert user["assigned_classes"] == "Class A"
    assert user["must_change_password"] == 0
    assert user["failed_login_attempts"] == 0
    assert user["created_at"] == "2024-01-02T03:04:05+00:00"
    assert user["updated_at"] == "2024-01-02T03:04:05+00:00"
