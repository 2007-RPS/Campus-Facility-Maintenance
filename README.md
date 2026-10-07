# Campus Facility Maintenance Request Management System (Campus FMS)

A full-stack, enterprise-grade prototype for managing campus facility maintenance requests, work order dispatches, technician logging, SLA compliance tracking, and management analytics.

Built with **Python Flask**, local **MySQL 8.0** (`campus_fms` database), and a clean **Plain HTML5 / Vanilla CSS / Modern Vanilla JS** frontend styled with a dark-green and white theme (`#16a34a`, `#064e3b`), rounded cards, and left sidebar.

---

## Architecture & Security Overview

### 1. Four Role-Based Consoles with URL Isolation
The application provides four independent consoles. Each console renders strictly its own UI, and each API endpoint is server-side authorized with `@role_required`:

| Console Role | Console URL | Login URL | Description & Access Rights |
| :--- | :--- | :--- | :--- |
| **Student / Staff** | `/portal` | `/portal/login`<br>`/portal/register` | Submit facility breakdown tickets, track real-time status in "My Requests", view SLA countdowns, and submit 5-star ratings once resolved. **Object-level check:** Requesters can only access and rate their own requests. |
| **Technician** | `/technician` | `/technician/login` | View assigned work orders, record work logs and spare materials in Indian Rupees (**₹**), and mark jobs resolved. **Object-level check:** Technicians can only access requests explicitly assigned to them in `Assignments`. |
| **Facility Admin** | `/admin` | `/admin/login` | All-campus ticket dispatch table, assign skill-matched available technicians, manage status progressions, provision new user accounts via "Manage Users", and inspect security audit logs. |
| **Executive Management** | `/management` | `/management/login` | **Strictly Read-Only**. High-level facility KPIs, SLA compliance %, total material spend in **₹**, Chart.js volume distributions, real-time status progression timeline, and system audit logs. All mutation attempts rejected with 403. |
| **Gateway / Landing** | `/` | `/login` | Public gateway directing users to their respective role login pages or active session console. |

---

### 2. Layered Security & Authentication Controls

- **Server-Side Authorization (`@role_required`)**:
  - Enforced on all web and namespaced API endpoints (`/api/portal/*`, `/api/technician/*`, `/api/admin/*`, `/api/management/*`).
  - Unauthorized calls return `401 Unauthorized` (if unauthenticated) or `403 Forbidden` (if role disallowed).
- **Object-Level Access Control**:
  - Requesters can access ONLY their own requests (`r.UserID == session['user_id']`). Any attempt to access another requester's ticket returns `403 Forbidden`.
  - Technicians can access ONLY requests assigned to them in `Assignments`. Accessing unassigned tickets returns `403 Forbidden`.
  - Management is strictly read-only.
- **Account Lockout (Persistent `LoginAttempts` Table)**:
  - Tracks every login attempt (email, IP, timestamp, success/failure) in the database (not in memory).
  - Automatically locks an account for **15 minutes** after **5 consecutive failed login attempts**.
- **Session Security & Idle Timeout**:
  - `HttpOnly=True`, `SameSite=Lax`, and `Secure` support.
  - **30-minute idle session timeout**: If no requests are made for 30 minutes, the session is invalidated, prompting the user to log in again.
  - Dedicated logout buttons on all consoles.
- **CSRF Protection**:
  - Cryptographically secure 32-byte hex token stored in session and injected into page headers.
  - Required (`X-CSRF-Token`) on all state-changing requests (`POST`, `PUT`, `DELETE`). Calls without valid token are rejected with `403 Forbidden`.
- **System Audit Trail (`AuditLog` Table)**:
  - Logs user logins, failed attempts, technician assignments, status changes, and user creations with UserID, Action, Details, IP, and Timestamp in IST.
  - Directly inspectable on Admin and Management consoles.
- **Forward-Only Status Progression**:
  - Request lifecycle strictly advances forward: `Open` ➔ `Assigned` ➔ `In Progress` ➔ `Resolved` ➔ `Closed`.
  - Skipping or backward transitions are rejected by both the API and database triggers.
- **Security Headers**:
  - Hardened with `X-Frame-Options: DENY`, `X-Content-Type-Options: nosniff`, `Referrer-Policy: strict-origin-when-cross-origin`, and `Content-Security-Policy`.
- **Output Escaping & Indian Currency**:
  - Input sanitized; output escaped in DOM.
  - All currency displayed strictly in Indian Rupees (**₹**) with `toLocaleString('en-IN')` (e.g. ₹1,25,000.00).

---

### 3. Least-Privilege MySQL User (`campus_app`)

The application connects to MySQL using a dedicated **least-privilege user** (`campus_app`) rather than `root`. This user is restricted to data manipulation only and **cannot drop or alter database structures**:

- **Granted Privileges**: `SELECT`, `INSERT`, `UPDATE`, `DELETE`, `EXECUTE` on `campus_fms.*`
- **Denied Privileges**: `DROP`, `CREATE`, `ALTER`, `GRANT OPTION`

To create this user in MySQL:

```sql
CREATE USER IF NOT EXISTS 'campus_app'@'localhost' IDENTIFIED BY 'CampusApp@2026';
GRANT SELECT, INSERT, UPDATE, DELETE, EXECUTE ON campus_fms.* TO 'campus_app'@'localhost';
FLUSH PRIVILEGES;
```

Verify that `campus_app` is blocked from dropping tables:
```sql
-- This query will fail with MySQL Error 1142 (DROP command denied to user 'campus_app'@'localhost')
DROP TABLE campus_fms.Users;
```

---

## Pre-seeded Demo Credentials

Public registration creates only Student/Staff accounts. To explore all 4 consoles, use the following pre-seeded credentials:

| Role | Name | Email | Password | Console URL |
| :--- | :--- | :--- | :--- | :--- |
| **Student / Staff** | Alex Chen | `alex.student@campus.edu` | `student123` | [`/portal`](http://127.0.0.1:5000/portal) |
| **Student / Staff** | Prof. Sarah Jenkins | `sarah.faculty@campus.edu` | `staff123` | [`/portal`](http://127.0.0.1:5000/portal) |
| **Facility Admin** | Marcus Vance | `marcus.admin@campus.edu` | `admin123` | [`/admin`](http://127.0.0.1:5000/admin) |
| **Technician (Electrical)** | Carlos Mendez | `carlos.electrician@campus.edu` | `tech123` | [`/technician`](http://127.0.0.1:5000/technician) |
| **Technician (Plumbing)** | Elena Rostova | `elena.plumber@campus.edu` | `tech123` | [`/technician`](http://127.0.0.1:5000/technician) |
| **Executive Management** | Dr. Arthur Reynolds | `reynolds.mgmt@campus.edu` | `mgmt123` | [`/management`](http://127.0.0.1:5000/management) |

*(Note: The demo switcher is disabled by default. If desired for development, set `DEMO_MODE=true` in `.env`)*

---

## 15-Table Normalized Database Schema

1. `Users` (`UserID` PK, Name, Email, Phone, PasswordHash, Role, Dept)
2. `Buildings` (`BuildingID` PK, BuildingName, Address)
3. `Facilities` (`FacilityID` PK, BuildingID FK, RoomNo, Floor, Type)
4. `Categories` (`CategoryID` PK, CategoryName, Description)
5. `Priorities` (`PriorityID` PK, Label, SLAHours)
6. `Assets` (`AssetID` PK, AssetName, CategoryID FK, FacilityID FK, Status)
7. `Technicians` (`TechID` PK, UserID FK, Skill, Available)
8. `Requests` (`RequestID` PK, UserID FK, FacilityID FK, CategoryID FK, PriorityID FK, Description, Status, RequestDate)
9. `Assignments` (`AssignID` PK, RequestID FK, TechID FK, AssignedOn)
10. `WorkLogs` (`LogID` PK, AssignID FK, WorkDate, WorkDescription)
11. `Materials` (`MatID` PK, LogID FK, MaterialName, Qty, Cost)
12. `StatusHistory` (`HistID` PK, RequestID FK, OldStatus, NewStatus, ChangedOn)
13. `Feedback` (`FeedbackID` PK, RequestID FK UNIQUE, UserID FK, Rating, Comments, FeedbackDate)
14. `LoginAttempts` (`AttemptID` PK, Email, IPAddress, AttemptTime, IsSuccess)
15. `AuditLog` (`LogID` PK, UserID FK, Action, Details, IP, Timestamp)

---

## Running Automated Security Tests

A comprehensive security test script (`test_security.py`) validates all security controls:

```bash
python test_security.py
```

This verifies:
1. Public registration restriction (cannot register as admin/tech/mgmt)
2. Account lockout after 5 failed logins via `LoginAttempts` table
3. Server-side role authorization (`@role_required`)
4. CSRF protection on state-changing requests
5. Object-level isolation (requester ticket isolation & technician assignment isolation)
6. Read-only enforcement on Executive Management
7. Forward-only status progression (`Open` ➔ `Assigned` ➔ `In Progress` ➔ `Resolved` ➔ `Closed`)
8. Tamper-evident entries in `AuditLog` table

---

## Launching the Application

1. Verify `.env`:
   ```ini
   DB_HOST=localhost
   DB_PORT=3306
   DB_USER=campus_app
   DB_PASSWORD=CampusApp@2026
   DB_NAME=campus_fms
   SECRET_KEY=campus_fms_super_secret_key_2026_development
   PORT=5000
   FLASK_DEBUG=1
   DEMO_MODE=false
   ```

2. Run the application:
   ```bash
   python app.py
   ```

3. Navigate to **http://127.0.0.1:5000** to access the gateway and login portals.
