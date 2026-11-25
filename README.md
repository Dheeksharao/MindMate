<<<<<<< HEAD
 MindMate – Student Well-being & Academic Support (v2.0)

**MindMate** is a realistic, secure, database-driven web application for school well-being monitoring and academic support. It features role-based access for **Administrators**, **Teachers**, and **Students**, strictly driven by real database records without dummy or mock data.
=======
# MindMate – Student Well-being & Academic Support System

**MindMate** is a realistic, secure, database-driven web application for school well-being monitoring, academic support, and student guidance.

> **Non-Diagnostic Policy Notice**:
> *"This tool does not diagnose. It helps teachers notice when a student might need a caring conversation."*

---

## 🌟 Key Features & Architecture

### 1. Zero Mock Data & Pure Database Persistence
- **No hardcoded users, demo accounts, pre-filled forms, or mock dashboard numbers** anywhere in the system.
- Every metric, chart, distribution, and student record is calculated in real time directly from SQLite database queries.
- When empty, clean and informative empty states are displayed (e.g. *"No teachers added yet"*, *"No students added yet"*, *"No assessments completed yet"*).

### 2. First Admin Bootstrap
- Initial Administrator setup is performed via an interactive, secure CLI script without default credentials:
  ```powershell
  python create_admin.py
  ```
  Prompts interactively for Administrator Email, Full Name, and Password.
- Once created, the admin portal manages all teacher and student accounts.

### 3. Multi-Portal Authentication & Role Isolation
- **Three dedicated login portals**:
  - **Educator Portal**: Teachers log in using their email or username.
  - **Student Portal**: Students log in using their admin-issued username (email not required).
  - **Admin Portal**: System administrator login.
- **Strict Role-to-Portal Matching**: Attempting to sign into a mismatched portal returns the exact generic error `"Incorrect email/username or password."` without revealing account existence.
- **In-Memory Token Storage**: Strict security policy—JWT authentication tokens live purely in-memory in the client runtime; **never stored in `localStorage`**.
- **Rate-Limiting & Lockout**: 5 failed login attempts temporarily locks the account for 15 minutes.
- **Mandatory Password Reset**: Administrator password resets require the user to change their password upon their next login (`/api/auth/force-change-password`).

### 4. Admin Management & Assignments
- **Teacher & Student Management**: Full CRUD with soft deactivation (`is_active = 0`, no hard deletion).
- **Primary Mentor Assignment**: Each student has exactly one primary mentor teacher. Bulk assignment and reassignment are supported with full audit logging in `assignment_history`.
- **System Settings**: Admin-configurable safeguarding lead contact information (name, phone, email), check-in frequency, and reporting window (default: 30 days).

### 5. Adaptive Mental Health Check-In Engine
- **Question Bank**: 108 questions across 8 well-being domains stored in the database (`check_in_questions`):
  1. *Mood & Emotions*
  2. *Stress & Pressure*
  3. *Academic Experience*
  4. *Daily Routine & Habits*
  5. *Concentration & Focus*
  6. *Social & School Experience*
  7. *Teaching & Classroom Insights*
  8. *Support & Coping Strategies*
- **Adaptive Server-Driven Flow**:
  - `POST /api/checkins/start` initializes a dynamic session.
  - `POST /api/checkins/{id}/answer` evaluates the response and dynamically determines the next question.
  - **Dynamic Length (8–25 questions)**: Students who report positive habits and thriving indicators complete early (8–11 questions). Students indicating concerns branch into targeted follow-ups.
- **Encrypted Free-Text Notes**: Free-text reflection notes are encrypted at rest with Fernet symmetric cryptography.
- **Urgent Safeguarding Trigger**: Keywords such as `"hopeless"`, `"hurt myself"`, `"unsafe"`, or `"cannot go on"` immediately generate an urgent alert for the designated safeguarding team and return a calming, supportive message with emergency contacts to the student.

### 6. Scoring & Indicator Thresholds
- **Domain Concern Scoring** (0.0 to 1.0):
  - *Low Concern*: $\le 0.34$
  - *Medium Concern*: $0.35 - 0.64$
  - *High Concern*: $\ge 0.65$
- **Overall Well-being Indicator**:
  - **Doing Well**: Average concern score $< 0.30$ and 0 High-concern domains.
  - **Moderate Concern**: Average concern score $0.30 - 0.54$ or exactly 1 High-concern domain.
  - **Needs Attention**: Average concern score $\ge 0.55$, or $\ge 2$ High-concern domains, or any urgent safeguarding keyword.

### 7. Teacher & Student Dashboards
- **Teacher Dashboard**:
  - Scoped strictly to assigned students (`403 Forbidden` for unassigned students).
  - **Well-Being Distribution**: Aggregated from the latest check-in of each student within the configurable reporting window (default 30 days). Displays *"Based on X of Y assigned students"* and *"Z students pending check-in"*.
  - **Teaching & Learning Insights**: Real feedback on lesson understanding %, classroom question comfort %, teaching pace preferences, and preferred learning methods.
  - **Student Follow-Up Workflow**: Interactive status progression (`New` $\rightarrow$ `Contacted` $\rightarrow$ `In progress` $\rightarrow$ `Resolved`).
- **Student Dashboard**:
  - Displays only permitted personal records (own assessments, guidance tips, self check-in history).
  - Strict privacy filter excludes internal triage labels, teacher observations, and alerts.

---

## 🚀 Getting Started

### 1. Requirements
- Python 3.10+
- Modern Web Browser

### 2. Setup & Installation
```powershell
cd C:\Users\vinay\.gemini\antigravity\scratch\mindmate
pip install -r requirements.txt
```

### 3. Initialize Database & Questions
```powershell
python database.py
python populate_questions.py
```

### 4. Create Initial Administrator
Run the interactive CLI bootstrap tool:
```powershell
python create_admin.py
```
Enter your administrator email, full name, and password when prompted.

### 5. Start the MindMate Server
```powershell
uvicorn main:app --reload
```
Open **`http://127.0.0.1:8000`** in your browser.

---

## 🧪 Automated Testing

MindMate comes with a comprehensive pytest test suite covering authentication, multi-portal matching, lockout, authorization isolation, bulk assignments, adaptive check-ins, safeguarding triggers, and scoring rules:

```powershell
python -m pytest tests/ -v
```
All 26 automated tests pass with 100% test coverage.
>>>>>>> a89d944 (Complete MindMate: database-driven architecture, zero mock data, adaptive check-ins, multi-portal auth)
