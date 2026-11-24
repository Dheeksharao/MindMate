import sys
import sqlite3
from pathlib import Path
from database import init_db, get_db

def clear_all_data():
    """
    Cleans all records from MindMate so it contains only real data entered through the application.
    """
    print("Initializing clean MindMate schema...")
    init_db()
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM audit_logs")
        cursor.execute("DELETE FROM alerts")
        cursor.execute("DELETE FROM observations")
        cursor.execute("DELETE FROM recommendations")
        cursor.execute("DELETE FROM checkins")
        cursor.execute("DELETE FROM assessments")
        cursor.execute("DELETE FROM students")
        cursor.execute("DELETE FROM users")
        try:
            cursor.execute("DELETE FROM sqlite_sequence")
        except sqlite3.OperationalError:
            pass
        print("Database cleared: 0 mock users, 0 mock students, 0 mock records.")
        print("MindMate is now ready for real database-driven accounts and data.")

if __name__ == "__main__":
    clear_all_data()
