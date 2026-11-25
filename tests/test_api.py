import pytest
import sys
from pathlib import Path
from fastapi import HTTPException

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from database import init_db, get_db
from auth import (
    hash_password,
    GENERIC_LOGIN_ERROR,
    INACTIVE_ERROR,
    UNASSIGNED_ERROR,
    MAX_LOGIN_ATTEMPTS
)
from crypto import decrypt_note
from main import (
    setup_initial_admin,
    login,
    change_password,
    force_change_password,
    create_teacher,
    update_teacher,
    reset_teacher_password,
    toggle_teacher_status,
    admin_create_student,
    bulk_assign_students,
    get_assignment_history,
    list_teachers,
    admin_list_students,
    list_students,
    get_student_profile,
    add_assessment,
    submit_mental_health_checkin,
    student_self_checkin,
    start_adaptive_checkin,
    answer_adaptive_checkin,
    get_active_checkin_session,
    create_student_observation,
    list_student_observations,
    update_observation_status,
    update_student_followup_status,
    update_alert_status,
    get_dashboard,
    SetupAdminRequest,
    LoginRequest,
    ChangePasswordRequest,
    ForceChangePasswordRequest,
    ResetPasswordRequest,
    TeacherCreateRequest,
    TeacherUpdateRequest,
    StudentCreateRequest,
    BulkAssignRequest,
    AssessmentCreateRequest,
    CheckinRequest,
    StudentSelfCheckinRequest,
    AdaptiveAnswerRequest,
    ObservationCreateRequest,
    ObservationStatusRequest,
    FollowUpStatusUpdateRequest,
    AlertStatusUpdateRequest
)

@pytest.fixture(scope="module", autouse=True)
def setup_clean_test_db():
    init_db()
    def _clean():
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM audit_logs")
            cursor.execute("DELETE FROM alerts")
            cursor.execute("DELETE FROM observations")
            cursor.execute("DELETE FROM recommendations")
            cursor.execute("DELETE FROM check_in_sessions")
            cursor.execute("DELETE FROM checkins")
            cursor.execute("DELETE FROM assessments")
            cursor.execute("DELETE FROM assignment_history")
            cursor.execute("DELETE FROM students")
            cursor.execute("DELETE FROM users")
            try:
                cursor.execute("DELETE FROM sqlite_sequence")
            except Exception:
                pass
    _clean()
    yield
    _clean()

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

    # 2. Login with real admin via admin portal
    login_res = login(LoginRequest(
        identifier="admin@school.edu",
        password="MasterAdmin@2026",
        portal="admin"
    ))
    assert "access_token" in login_res
    assert login_res["user"]["email"] == "admin@school.edu"

def test_portal_role_matching_and_exact_errors():
    # 1. Invalid credentials returns exact generic message
    with pytest.raises(HTTPException) as exc:
        login(LoginRequest(
            identifier="unknown@school.edu",
            password="WrongPassword123",
            portal="admin"
        ))
    assert exc.value.status_code == 401
    assert exc.value.detail == GENERIC_LOGIN_ERROR

    # 2. Admin trying to log into teacher portal -> 401 generic error (role mismatch doesn't leak role info)
    with pytest.raises(HTTPException) as exc:
        login(LoginRequest(
            identifier="admin@school.edu",
            password="MasterAdmin@2026",
            portal="teacher"
        ))
    assert exc.value.status_code == 401
    assert exc.value.detail == GENERIC_LOGIN_ERROR

    # 3. Create teacher with no assigned classes/students
    admin_user = {"id": 1, "email": "admin@school.edu", "full_name": "Dr. Eleanor Vance", "role": "admin"}
    unassigned_teacher = create_teacher(
        TeacherCreateRequest(
            email="unassigned.teacher@school.edu",
            password="TeacherPass@123",
            full_name="Unassigned Teacher",
            assigned_classes="",
            check_in_pin="1111"
        ),
        current_user=admin_user
    )

    # Logging in as unassigned teacher -> 403 exact message
    with pytest.raises(HTTPException) as exc:
        login(LoginRequest(
            identifier="unassigned.teacher@school.edu",
            password="TeacherPass@123",
            portal="teacher"
        ))
    assert exc.value.status_code == 403
    assert exc.value.detail == UNASSIGNED_ERROR

    # 4. Deactivated teacher -> 403 exact message
    toggle_teacher_status(unassigned_teacher["id"], current_user=admin_user)
    with pytest.raises(HTTPException) as exc:
        login(LoginRequest(
            identifier="unassigned.teacher@school.edu",
            password="TeacherPass@123",
            portal="teacher"
        ))
    assert exc.value.status_code == 403
    assert exc.value.detail == INACTIVE_ERROR

    # 5. Lockout after 5 failed attempts
    # Reactivate user for testing failed attempts
    toggle_teacher_status(unassigned_teacher["id"], current_user=admin_user)
    for _ in range(MAX_LOGIN_ATTEMPTS):
        with pytest.raises(HTTPException) as exc:
            login(LoginRequest(
                identifier="unassigned.teacher@school.edu",
                password="WrongPassword!",
                portal="teacher"
            ))
        assert exc.value.status_code == 401

    # Check database that user is locked out
    with get_db() as conn:
        row = conn.execute("SELECT failed_login_attempts, lockout_until FROM users WHERE id = ?",
                           (unassigned_teacher["id"],)).fetchone()
        assert row["failed_login_attempts"] >= MAX_LOGIN_ATTEMPTS
        assert row["lockout_until"] is not None

def test_admin_creates_teacher_and_student():
    admin_user = {"id": 1, "email": "admin@school.edu", "full_name": "Dr. Eleanor Vance", "role": "admin"}

    # 1. Admin creates active teacher Sarah Jenkins
    teacher = create_teacher(
        TeacherCreateRequest(
            email="sarah.jenkins@school.edu",
            password="TeacherPass@123",
            full_name="Sarah Jenkins",
            assigned_classes="Class 9A,Class 9B",
            check_in_pin="4321"
        ),
        current_user=admin_user
    )
    assert teacher["email"] == "sarah.jenkins@school.edu"
    assert teacher["assigned_classes"] == "Class 9A,Class 9B"

    # Teacher logs in successfully
    t_login = login(LoginRequest(
        identifier="sarah.jenkins@school.edu",
        password="TeacherPass@123",
        portal="teacher"
    ))
    assert "access_token" in t_login
    assert t_login["user"]["role"] == "teacher"

    # 2. Admin creates student Maya Patel with username (no email required) and roll number
    student = admin_create_student(
        StudentCreateRequest(
            name="Maya Patel",
            class_name="Class 9A",
            roll_number="01",
            guardian_name="Sunita Patel",
            guardian_contact="+1-555-0102",
            consent_given=True,
            assigned_teacher_id=teacher["id"],
            username="maya9a",
            password="StudentPass@123"
        ),
        current_user=admin_user
    )
    assert student["name"] == "Maya Patel"
    assert student["roll_number"] == "01"
    assert student["assigned_teacher_id"] == teacher["id"]

    # Student logs in with username
    s_login = login(LoginRequest(
        identifier="maya9a",
        password="StudentPass@123",
        portal="student"
    ))
    assert "access_token" in s_login
    assert s_login["user"]["role"] == "student"
    assert s_login["user"]["student_id"] == student["id"]

def test_force_password_change_flow():
    admin_user = {"id": 1, "email": "admin@school.edu", "full_name": "Dr. Eleanor Vance", "role": "admin"}

    with get_db() as conn:
        t_row = conn.execute("SELECT id FROM users WHERE email='sarah.jenkins@school.edu'").fetchone()
        t_id = t_row["id"]

    # Admin resets teacher password
    reset_teacher_password(t_id, ResetPasswordRequest(new_password="TempReset@123"), current_user=admin_user)

    # Teacher logs in with temp password
    t_login = login(LoginRequest(
        identifier="sarah.jenkins@school.edu",
        password="TempReset@123",
        portal="teacher"
    ))
    assert t_login["user"]["must_change_password"] == 1

    # Teacher forces password change
    teacher_user = {"id": t_id, "email": "sarah.jenkins@school.edu", "must_change_password": 1, "role": "teacher"}
    res = force_change_password(
        ForceChangePasswordRequest(new_password="PermanentPass@2026"),
        current_user=teacher_user
    )
    assert res["success"] is True

    # Now teacher can log in with permanent password and must_change_password is 0
    t_login2 = login(LoginRequest(
        identifier="sarah.jenkins@school.edu",
        password="PermanentPass@2026",
        portal="teacher"
    ))
    assert t_login2["user"]["must_change_password"] == 0

def test_authorization_and_isolation():
    admin_user = {"id": 1, "email": "admin@school.edu", "full_name": "Dr. Eleanor Vance", "role": "admin"}

    # Create Teacher 2 (Mr. Adams) with Class 10B
    t2 = create_teacher(
        TeacherCreateRequest(
            email="mr.adams@school.edu",
            password="Teacher@123",
            full_name="Mr. Adams",
            assigned_classes="Class 10B"
        ),
        current_user=admin_user
    )

    # Create Student in Class 10B assigned to Mr. Adams
    s_adams = admin_create_student(
        StudentCreateRequest(
            name="James Wilson",
            class_name="Class 10B",
            roll_number="01",
            guardian_name="Helen Wilson",
            guardian_contact="+1-555-0999",
            assigned_teacher_id=t2["id"],
            username="james10b",
            password="StudentPass@123"
        ),
        current_user=admin_user
    )

    with get_db() as conn:
        sarah_user = dict(conn.execute("SELECT * FROM users WHERE email='sarah.jenkins@school.edu'").fetchone())
        maya_user = dict(conn.execute("SELECT * FROM users WHERE username='maya9a'").fetchone())
        maya_student = dict(conn.execute("SELECT * FROM students WHERE user_id = ?", (maya_user["id"],)).fetchone())

    # 1. Sarah Jenkins tries to access James Wilson (Class 10B) -> 403 Forbidden
    with pytest.raises(HTTPException) as exc:
        get_student_profile(student_id=s_adams["id"], current_user=sarah_user)
    assert exc.value.status_code == 403

    # 2. Maya Patel tries to access James Wilson -> 403 Forbidden
    with pytest.raises(HTTPException) as exc:
        get_student_profile(student_id=s_adams["id"], current_user=maya_user)
    assert exc.value.status_code == 403
    assert "Students can only view their own record" in exc.value.detail

    # 3. Admin tries to access individual student well-being profile -> 403 Forbidden
    with pytest.raises(HTTPException) as exc:
        get_student_profile(student_id=maya_student["id"], current_user=admin_user)
    assert exc.value.status_code == 403
    assert "Administrators cannot view individual student well-being data" in exc.value.detail

    # 4. Maya Patel views her own record: internal triage labels and teacher notes MUST NOT be present
    maya_profile = get_student_profile(student_id=maya_student["id"], current_user=maya_user)
    assert maya_profile["student"]["name"] == "Maya Patel"
    # Ensure sensitive fields are excluded or empty for student role
    assert "support_level" not in maya_profile
    assert len(maya_profile["observations"]) == 0
    assert len(maya_profile["alerts"]) == 0

def test_bulk_assignment_and_history():
    admin_user = {"id": 1, "email": "admin@school.edu", "full_name": "Dr. Eleanor Vance", "role": "admin"}

    with get_db() as conn:
        maya_student = conn.execute("SELECT id FROM students WHERE name='Maya Patel'").fetchone()
        adams_teacher = conn.execute("SELECT id FROM users WHERE email='mr.adams@school.edu'").fetchone()

    # Reassign Maya Patel to Mr. Adams
    res = bulk_assign_students(
        BulkAssignRequest(
            student_ids=[maya_student["id"]],
            teacher_id=adams_teacher["id"],
            reason="Term transfer"
        ),
        current_user=admin_user
    )
    assert res["assigned_count"] == 1

    # Check assignment history
    history = get_assignment_history(student_id=maya_student["id"], current_user=admin_user)
    assert len(history) >= 1
    assert history[0]["new_teacher_name"] == "Mr. Adams"

    # Reassign back to Sarah Jenkins for remaining tests
    with get_db() as conn:
        sarah_teacher = conn.execute("SELECT id FROM users WHERE email='sarah.jenkins@school.edu'").fetchone()
    bulk_assign_students(
        BulkAssignRequest(
            student_ids=[maya_student["id"]],
            teacher_id=sarah_teacher["id"],
            reason="Reset to original teacher"
        ),
        current_user=admin_user
    )

def test_adaptive_checkin_engine():
    with get_db() as conn:
        maya_user = dict(conn.execute("SELECT * FROM users WHERE username='maya9a'").fetchone())
        maya_user["role"] = "student"

    # 1. Start adaptive check-in
    start_res = start_adaptive_checkin(current_user=maya_user)
    session_id = start_res["session_id"]
    assert session_id is not None
    assert start_res["question"] is not None
    assert start_res["status"] == "in_progress"

    # 2. Answer question with positive option
    current_q = start_res["question"]
    steps = 0
    res = start_res
    while res.get("status") == "in_progress" and steps < 25:
        steps += 1
        q_id = current_q["id"]
        opts = current_q.get("options", [])
        # Select first option (typically lowest concern score)
        selected_ans = opts[0]["id"] if opts else "fine"
        res = answer_adaptive_checkin(
            session_id=session_id,
            req=AdaptiveAnswerRequest(
                question_id=q_id,
                answer=selected_ans,
                preferred_not_to_answer=False,
                note=""
            ),
            current_user=maya_user
        )
        if res.get("status") == "completed":
            break
        current_q = res.get("question")

    assert res.get("status") == "completed"
    assert res.get("wellbeing_indicator") in ("Doing Well", "Moderate Concern")
    assert "caring conversation" in res.get("disclaimer", "").lower()
    assert 8 <= steps <= 25

def test_adaptive_checkin_with_safeguarding_trigger():
    with get_db() as conn:
        maya_user = dict(conn.execute("SELECT * FROM users WHERE username='maya9a'").fetchone())
        maya_user["role"] = "student"
        maya_student = dict(conn.execute("SELECT * FROM students WHERE user_id = ?", (maya_user["id"],)).fetchone())

    # Start new session
    start_res = start_adaptive_checkin(current_user=maya_user)
    session_id = start_res["session_id"]
    first_q = start_res["question"]
    opts = first_q.get("options", [])
    selected_ans = opts[-1]["id"] if opts else "low"

    # Answer with urgent keyword in note
    ans_res = answer_adaptive_checkin(
        session_id=session_id,
        req=AdaptiveAnswerRequest(
            question_id=first_q["id"],
            answer=selected_ans,
            preferred_not_to_answer=False,
            note="I feel completely hopeless and cannot go on."
        ),
        current_user=maya_user
    )
    # Check that alert was generated
    with get_db() as conn:
        alert = conn.execute("""
            SELECT * FROM alerts WHERE student_id = ? AND severity = 'urgent' AND status = 'open'
        """, (maya_student["id"],)).fetchone()
        assert alert is not None
        assert "urgent safeguarding" in alert["title"].lower()

def test_dashboard_statistics_and_empty_states():
    admin_user = {"id": 1, "email": "admin@school.edu", "full_name": "Dr. Eleanor Vance", "role": "admin"}
    with get_db() as conn:
        sarah_user = dict(conn.execute("SELECT * FROM users WHERE email='sarah.jenkins@school.edu'").fetchone())
        sarah_user["role"] = "teacher"

    # Admin dashboard
    admin_dash = get_dashboard(current_user=admin_user)
    assert admin_dash["total_teachers"] >= 1
    assert admin_dash["total_students"] >= 1

    # Teacher dashboard
    teacher_dash = get_dashboard(current_user=sarah_user)
    assert "wellbeing_distribution" in teacher_dash
    dist = teacher_dash["wellbeing_distribution"]
    assert "categories" in dist or "counts" in dist
    assert "summary_text" in dist
    assert "pending_text" in dist

def test_teacher_follow_up_workflow():
    with get_db() as conn:
        sarah_user = dict(conn.execute("SELECT * FROM users WHERE email='sarah.jenkins@school.edu'").fetchone())
        sarah_user["role"] = "teacher"
        maya_student = dict(conn.execute("SELECT * FROM students WHERE name='Maya Patel'").fetchone())

    # Update follow-up status: New -> Contacted -> In progress -> Resolved
    for new_status in ["Contacted", "In progress", "Resolved"]:
        res = update_student_followup_status(
            student_id=maya_student["id"],
            req=FollowUpStatusUpdateRequest(status=new_status, notes=f"Follow-up changed to {new_status}"),
            current_user=sarah_user
        )
        assert res["follow_up_status"] == new_status.lower().replace(" ", "_")
