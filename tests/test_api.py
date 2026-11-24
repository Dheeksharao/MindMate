import pytest
import sys
from pathlib import Path
from fastapi import HTTPException

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from database import init_db, get_db
from auth import hash_password
from crypto import decrypt_note
from main import (
    setup_initial_admin,
    login,
    change_password,
    create_teacher,
    toggle_teacher_status,
    admin_create_student,
    list_students,
    get_student_profile,
    add_assessment,
    submit_kiosk_checkin,
    student_self_checkin,
    create_student_observation,
    list_student_observations,
    update_observation_status,
    update_alert_status,
    SetupAdminRequest,
    LoginRequest,
    ChangePasswordRequest,
    TeacherCreateRequest,
    StudentCreateRequest,
    AssessmentCreateRequest,
    CheckinKioskRequest,
    StudentSelfCheckinRequest,
    ObservationCreateRequest,
    ObservationStatusRequest,
    AlertStatusUpdateRequest
)

@pytest.fixture(scope="module", autouse=True)
def setup_clean_test_db():
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
        except Exception:
            pass

def test_initial_admin_setup_and_login():
    # 1. Setup initial real admin
    setup_res = setup_initial_admin(SetupAdminRequest(
        email="admin@school.edu",
        password="MasterAdmin@2026",
        full_name="Dr. Eleanor Vance"
    ))
    assert "access_token" in setup_res
    assert setup_res["user"]["role"] == "admin"

    # Cannot run initial setup a second time
    with pytest.raises(HTTPException) as excinfo:
        setup_initial_admin(SetupAdminRequest(
            email="hacker@school.edu",
            password="Hacker@123",
            full_name="Attacker"
        ))
    assert excinfo.value.status_code == 400

    # 2. Login with real admin
    login_res = login(LoginRequest(email="admin@school.edu", password="MasterAdmin@2026"))
    assert "access_token" in login_res
    assert login_res["user"]["email"] == "admin@school.edu"

def test_admin_creates_teacher_and_teacher_login():
    admin_user = {"id": 1, "email": "admin@school.edu", "full_name": "Dr. Eleanor Vance", "role": "admin"}
    
    # Admin creates real teacher
    teacher_data = create_teacher(
        TeacherCreateRequest(
            email="sarah.jenkins@school.edu",
            password="TeacherPass@123",
            full_name="Sarah Jenkins",
            assigned_classes="Class 9A,Class 9B",
            kiosk_pin="4321"
        ),
        current_user=admin_user
    )
    assert teacher_data["email"] == "sarah.jenkins@school.edu"
    assert teacher_data["assigned_classes"] == "Class 9A,Class 9B"

    # Teacher logs in with their own credentials
    t_login = login(LoginRequest(email="sarah.jenkins@school.edu", password="TeacherPass@123"))
    assert "access_token" in t_login
    assert t_login["user"]["role"] == "teacher"
    assert t_login["user"]["assigned_classes"] == "Class 9A,Class 9B"

def test_deactivated_user_cannot_login():
    admin_user = {"id": 1, "email": "admin@school.edu", "full_name": "Dr. Eleanor Vance", "role": "admin"}
    
    # Create substitute teacher
    sub = create_teacher(
        TeacherCreateRequest(
            email="sub@school.edu",
            password="TempPass@123",
            full_name="Temp Substitute",
            assigned_classes="Class 9A"
        ),
        current_user=admin_user
    )
    
    # Deactivate teacher
    toggle_teacher_status(sub["id"], current_user=admin_user)
    
    # Attempting to log in while deactivated -> 403
    with pytest.raises(HTTPException) as excinfo:
        login(LoginRequest(email="sub@school.edu", password="TempPass@123"))
    assert excinfo.value.status_code == 403
    assert "deactivated" in excinfo.value.detail.lower()

def test_admin_creates_student_with_login():
    admin_user = {"id": 1, "email": "admin@school.edu", "full_name": "Dr. Eleanor Vance", "role": "admin"}
    
    # Find teacher ID
    with get_db() as conn:
        t_row = conn.cursor().execute("SELECT id FROM users WHERE email='sarah.jenkins@school.edu'").fetchone()
        t_id = t_row["id"]
        
    student = admin_create_student(
        StudentCreateRequest(
            name="Maya Patel",
            class_name="Class 9A",
            guardian_name="Sunita Patel",
            guardian_contact="+1-555-0102",
            consent_given=True,
            assigned_teacher_id=t_id,
            email="maya.patel@student.edu",
            password="StudentPass@123"
        ),
        current_user=admin_user
    )
    assert student["name"] == "Maya Patel"
    assert student["user_id"] is not None

    # Student logs in with their own student credentials
    s_login = login(LoginRequest(email="maya.patel@student.edu", password="StudentPass@123"))
    assert "access_token" in s_login
    assert s_login["user"]["role"] == "student"
    assert s_login["user"]["student_id"] == student["id"]

def test_password_change():
    # Student changes password
    with get_db() as conn:
        s_user = conn.cursor().execute("SELECT * FROM users WHERE email='maya.patel@student.edu'").fetchone()
        user_dict = dict(s_user)

    change_res = change_password(
        ChangePasswordRequest(
            current_password="StudentPass@123",
            new_password="NewSecurePass@2026"
        ),
        current_user=user_dict
    )
    assert change_res["success"] is True

    # Old password no longer works
    with pytest.raises(HTTPException) as exc:
        login(LoginRequest(email="maya.patel@student.edu", password="StudentPass@123"))
    assert exc.value.status_code == 401

    # New password works
    assert "access_token" in login(LoginRequest(email="maya.patel@student.edu", password="NewSecurePass@2026"))

def test_403_teacher_scoping_other_classes():
    admin_user = {"id": 1, "email": "admin@school.edu", "full_name": "Dr. Eleanor Vance", "role": "admin"}
    
    # Teacher 1 teaches only Class 9A
    t1 = create_teacher(
        TeacherCreateRequest(
            email="mr.adams@school.edu",
            password="Teacher@123",
            full_name="Mr. Adams",
            assigned_classes="Class 9A"
        ),
        current_user=admin_user
    )
    
    # Student in Class 10B
    s_other = admin_create_student(
        StudentCreateRequest(
            name="James Wilson",
            class_name="Class 10B",
            guardian_name="Helen Wilson",
            guardian_contact="+1-555-0999"
        ),
        current_user=admin_user
    )
    
    # Mr. Adams tries to access James Wilson in 10B -> 403 Forbidden
    with pytest.raises(HTTPException) as excinfo:
        get_student_profile(student_id=s_other["id"], current_user=t1)
    assert excinfo.value.status_code == 403
    assert "Access denied" in excinfo.value.detail

def test_403_student_access_other_student():
    admin_user = {"id": 1, "email": "admin@school.edu", "full_name": "Dr. Eleanor Vance", "role": "admin"}
    
    # Create student 2
    s2 = admin_create_student(
        StudentCreateRequest(
            name="Chloe Nguyen",
            class_name="Class 9A",
            guardian_name="Huy Nguyen",
            guardian_contact="+1-555-0104",
            email="chloe@student.edu",
            password="ChloePass@123"
        ),
        current_user=admin_user
    )
    
    # Get Maya Patel's user dict
    with get_db() as conn:
        maya_user = dict(conn.cursor().execute("SELECT * FROM users WHERE email='maya.patel@student.edu'").fetchone())
        
    # Maya tries to access Chloe's confidential profile -> 403 Forbidden!
    with pytest.raises(HTTPException) as excinfo:
        get_student_profile(student_id=s2["id"], current_user=maya_user)
    assert excinfo.value.status_code == 403
    assert "Students can only view their own individual record" in excinfo.value.detail

def test_403_admin_cannot_view_individual_wellbeing():
    admin_user = {"id": 1, "email": "admin@school.edu", "full_name": "Dr. Eleanor Vance", "role": "admin"}
    
    # Admin cannot view confidential student well-being details
    with pytest.raises(HTTPException) as excinfo:
        get_student_profile(student_id=1, current_user=admin_user)
    assert excinfo.value.status_code == 403
    assert "Administrators cannot view individual student well-being data" in excinfo.value.detail

def test_assessment_learning_gap_and_deduplication():
    # Teacher Sarah Jenkins
    with get_db() as conn:
        t_row = dict(conn.cursor().execute("SELECT * FROM users WHERE email='sarah.jenkins@school.edu'").fetchone())
        s_row = dict(conn.cursor().execute("SELECT * FROM students WHERE name='Maya Patel'").fetchone())

    # Add a mark below 40% (Rule C)
    res = add_assessment(
        AssessmentCreateRequest(
            student_id=s_row["id"],
            subject="Mathematics",
            score=35.0,
            max_score=100.0,
            date="2026-11-20",
            notes="Quarterly Math Exam"
        ),
        current_user=t_row
    )
    assert res["percentage"] == 35.0
    assert any(g["subject"] == "Mathematics" for g in res["learning_gaps"])

    # Verify alert created in DB
    with get_db() as conn:
        count = conn.cursor().execute("""
            SELECT COUNT(*) AS c FROM alerts
            WHERE student_id = ? AND alert_type = 'learning_gap' AND subject = 'Mathematics' AND status = 'open'
        """, (s_row["id"],)).fetchone()["c"]
        assert count == 1

    # Add second low score -> Rule D deduplication preserves single open alert
    add_assessment(
        AssessmentCreateRequest(
            student_id=s_row["id"],
            subject="Mathematics",
            score=32.0,
            max_score=100.0,
            date="2026-11-22",
            notes="Retest"
        ),
        current_user=t_row
    )
    with get_db() as conn:
        count2 = conn.cursor().execute("""
            SELECT COUNT(*) AS c FROM alerts
            WHERE student_id = ? AND alert_type = 'learning_gap' AND subject = 'Mathematics' AND status = 'open'
        """, (s_row["id"],)).fetchone()["c"]
        assert count2 == 1

def test_student_self_checkin_and_encryption():
    with get_db() as conn:
        maya_user = dict(conn.cursor().execute("SELECT * FROM users WHERE email='maya.patel@student.edu'").fetchone())
        maya_student = dict(conn.cursor().execute("SELECT * FROM students WHERE user_id = ?", (maya_user["id"],)).fetchone())

    # Student performs self check-in
    res = student_self_checkin(
        StudentSelfCheckinRequest(
            mood=4,
            stress=2, # calm (6-2=4)
            sleep=4,
            focus=4,
            belonging=5,
            note="Enjoying our science project this week!"
        ),
        current_user=maya_user
    )
    assert res["success"] is True
    # Rule A: (4 + 4 + 4 + 4 + 5) / 5 = 21 / 5 = 4.2
    assert res["score"] == 4.2

    # Verify Fernet encryption in database
    with get_db() as conn:
        c_row = conn.cursor().execute("SELECT encrypted_note FROM checkins WHERE id = ?", (res["checkin_id"],)).fetchone()
        assert c_row["encrypted_note"] is not None
        assert "science project" not in c_row["encrypted_note"]
        decrypted = decrypt_note(c_row["encrypted_note"])
        assert "Enjoying our science project" in decrypted

def test_kiosk_checkin_and_safety_alert():
    with get_db() as conn:
        s_row = dict(conn.cursor().execute("SELECT * FROM students WHERE name='Maya Patel'").fetchone())

    # Kiosk checkin with safety keyword "hopeless"
    res = submit_kiosk_checkin(
        CheckinKioskRequest(
            student_id=s_row["id"],
            mood=1,
            stress=5, # overwhelmed (6-5=1)
            sleep=1,
            focus=1,
            belonging=1,
            note="I feel completely hopeless about keeping up.",
            teacher_pin="4321"
        )
    )
    assert res["success"] is True
    assert res["urgent_flag"] is True

    # Verify urgent alert in database
    with get_db() as conn:
        alert = conn.cursor().execute("SELECT * FROM alerts WHERE student_id = ? AND severity = 'urgent' AND status = 'open'", (s_row["id"],)).fetchone()
        assert alert is not None
        assert "Speak with the student privately today" in alert["message"]

def test_teacher_observations_and_followups():
    with get_db() as conn:
        t_row = dict(conn.cursor().execute("SELECT * FROM users WHERE email='sarah.jenkins@school.edu'").fetchone())
        s_row = dict(conn.cursor().execute("SELECT * FROM students WHERE name='Maya Patel'").fetchone())

    # Teacher adds observation & follow-up plan
    obs = create_student_observation(
        student_id=s_row["id"],
        req=ObservationCreateRequest(
            observation_text="Student appeared overwhelmed during math test prep.",
            follow_up_action="Scheduled gentle 1-on-1 check-in; paired with buddy study partner.",
            status="pending"
        ),
        current_user=t_row
    )
    assert obs["id"] is not None
    assert obs["status"] == "pending"

    # Fetch observations
    obs_list = list_student_observations(student_id=s_row["id"], current_user=t_row)
    assert len(obs_list) >= 1
    assert obs_list[0]["observation_text"] == "Student appeared overwhelmed during math test prep."

    # Update observation status
    status_res = update_observation_status(
        obs_id=obs["id"],
        req=ObservationStatusRequest(status="completed"),
        current_user=t_row
    )
    assert status_res["status"] == "completed"

def test_alert_status_lifecycle():
    with get_db() as conn:
        t_row = dict(conn.cursor().execute("SELECT * FROM users WHERE email='sarah.jenkins@school.edu'").fetchone())
        alert = conn.cursor().execute("SELECT id FROM alerts WHERE status = 'open' LIMIT 1").fetchone()
        alert_id = alert["id"]

    # Acknowledge
    ack = update_alert_status(alert_id, AlertStatusUpdateRequest(status="acknowledged"), current_user=t_row)
    assert ack["status"] == "acknowledged"

    # Snooze
    snz = update_alert_status(alert_id, AlertStatusUpdateRequest(status="snoozed"), current_user=t_row)
    assert snz["status"] == "snoozed"

    # Resolve
    res = update_alert_status(alert_id, AlertStatusUpdateRequest(status="resolved"), current_user=t_row)
    assert res["status"] == "resolved"
