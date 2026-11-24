# MindMate – Student Well-being & Academic Support (v2.0)

**MindMate** is a realistic, secure, database-driven web application for school well-being monitoring and academic support. It features role-based access for **Administrators**, **Teachers**, and **Students**, strictly driven by real database records without dummy or mock data.

---

## 🚀 Key Improvements & Architecture

- **100% Database-Driven**:
  - No dummy users, no mock students, no fake credentials, and no hardcoded dashboard metrics.
  - If the database is empty, the application presents intuitive empty states (e.g. *"No teachers added yet"*, *"No students enrolled yet"*).
- **First-Time Master Setup**:
  - On the very first run, MindMate detects that no administrator account exists and automatically displays an initial Master Administrator setup screen (or you can run `python create_admin.py`).
- **Full Role-Based Access Control**:
  - **Administrator**:
    - Creates and manages real teacher accounts (assigning classes, setting kiosk PINs, activating/deactivating accounts, resetting passwords).
    - Enrolls real students, assigns classroom teachers, manages parental consent, and creates/resets student login accounts.
    - Views real-time school database statistics.
    - Reviews tamper-evident safeguarding and access audit logs.
  - **Teacher**:
    - Sees **only** the students enrolled in their assigned classes or directly assigned to them (`403 Forbidden` for any other student).
    - Views student academic and well-being profiles.
    - Conducts classroom MindMate assessments and student kiosk check-ins.
    - Logs **behavioral observations and tracks follow-up action plans** directly in the database.
    - Records academic marks (automatically detecting learning gaps and alerts).
  - **Student**:
    - Logs into the student portal using their own credentials.
    - Views **only** their own profile, learning tips, and assessment history.
    - Can submit **daily self check-ins** directly from their personal dashboard.
    - Strict backend authorization ensures students can never view any other student's information (`403 Forbidden`).
- **Security & Privacy**:
  - Passwords hashed using `bcrypt`.
  - Authenticated session tokens with `JWT`.
  - Self-service password change (`/api/auth/change-password`) and administrator credential reset.
  - Account deactivation enforcement (`is_active` check).
  - Confidential student check-in notes encrypted at rest with **Fernet symmetric encryption** ([`crypto.py`](file:///C:/Users/vinay/.gemini/antigravity/scratch/mindmate/crypto.py)).
  - Non-diagnostic safeguarding policy displayed across well-being interfaces.

---

## 🏃 Quick Start Guide

### 1. Requirements
Python 3.10+ installed.

### 2. Install Dependencies
```powershell
cd C:\Users\vinay\.gemini\antigravity\scratch\mindmate
pip install -r requirements.txt
```

### 3. Start the Web Server
```powershell
uvicorn main:app --reload
```
Open **`http://127.0.0.1:8000`** in your browser.

### 4. Initial Administrator Setup
- When opening `http://127.0.0.1:8000` for the first time, you will be prompted to create the initial **Master Administrator** account.
- Alternatively, you can create an administrator from the command line:
  ```powershell
  python create_admin.py --email admin@school.edu --password AdminPass@123 --name "School Administrator"
  ```

---

## 📐 Business Logic & Safeguarding Rules

- **Rule A (Check-in Score)**:
  $$\text{Score} = \frac{\text{Mood} + (6 - \text{Stress}) + \text{Sleep} + \text{Focus} + \text{Belonging}}{5}$$
  *Stress is inverted so higher scores consistently represent higher well-being.*

- **Rule B (Support Level & Mathematical Trend)**:
  Evaluated from the average of the last 3 check-ins:
  - If average $< 3.0$, or ($< 3.5$ and falling by $> 0.4$ versus previous 3): $\rightarrow$ **"May benefit from support"**
  - If $< 3.7$: $\rightarrow$ **"Doing okay"**
  - Otherwise: $\rightarrow$ **"Thriving"**
  *Always shows exact reason on screen, e.g.: "Average 2.8/5 over last 3 check-ins, trend -0.5".*

- **Rule C (Learning Gap)**:
  A subject is flagged if the latest score is below **40%**, or dropped by more than **15 points** versus the previous assessment.

- **Rule D (Alerts & Deduplication)**:
  Alerts auto-created for learning gaps or support indicators. Deduplication ensures no duplicate open alert is ever created for the same student/subject.

- **Rule E (Safeguarding Keywords)**:
  Check-in notes containing keywords such as `"hopeless"`, `"hurt myself"`, or `"unsafe"` trigger an **URGENT** alert:
  > *"Speak with the student privately today, follow your school's safeguarding policy and involve the counsellor."*

- **Rule F (Strength-Based Recommendations)**:
  Bite-sized practice sets for academic gaps; gentle 1-on-1 check-ins and peer buddy study sessions for well-being support.

---

## 🧪 Automated Pytest Test Suite

MindMate includes 23 automated tests covering initial setup, authentication, password changing, role-based 403 authorization, observations, student self check-ins, Fernet encryption, and Rules A through F:

```powershell
python -m pytest -p no:cacheprovider
```

---

## 🛡️ Privacy Notice
*"This tool does not diagnose. It helps teachers notice when a student might need a caring conversation."*
All personal well-being notes are Fernet-encrypted and restricted to classroom educators.
