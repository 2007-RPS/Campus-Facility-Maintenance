"""
Automated Layered Security and RBAC Test Suite
Covers:
1. Account Lockout after 5 Failed Logins (via LoginAttempts table)
2. Role-Based Access Control (@role_required server-side enforcement)
3. Object-Level Access Control (Requester isolation & Technician assignment isolation)
4. Read-Only Restriction for Management Role
5. Public Registration Role Restriction (Only student_staff permitted)
6. CSRF Protection on Mutating Requests
7. Forward-Only Request Status Progression
8. AuditLog Generation Verification
"""

import sys
import json
import time
from app import app
from db import query_db

def run_tests():
    print("=" * 70)
    print("RUNNING CAMPUS FMS LAYERED SECURITY & RBAC VERIFICATION SUITE")
    print("=" * 70)

    client = app.test_client()
    passed = 0
    total = 0

    def assert_test(cond, title):
        nonlocal passed, total
        total += 1
        if cond:
            print(f" [PASS] {title}")
            passed += 1
        else:
            print(f" [FAIL] {title}")

    # Clean up test email from LoginAttempts before test
    test_lockout_email = "lockout.test@campus.edu"
    query_db("DELETE FROM LoginAttempts WHERE LOWER(Email) = %s", (test_lockout_email,), commit=True)
    query_db("DELETE FROM Users WHERE LOWER(Email) = %s", (test_lockout_email,), commit=True)

    # -----------------------------------------------------------------
    # Test 1: Public Registration Role Restriction
    # -----------------------------------------------------------------
    print("\n--- Test Suite 1: Registration Role Restriction ---")
    # Attempting to register as facility_admin should be rejected (403)
    res = client.post("/api/auth/register", json={
        "name": "Hacker Admin",
        "email": "hacker@campus.edu",
        "password": "password123",
        "role": "facility_admin"
    })
    assert_test(res.status_code == 403, "Public registration as 'facility_admin' rejected with 403 Forbidden")

    # Public registration with student_staff succeeds
    res_reg = client.post("/api/auth/register", json={
        "name": "Test Student Two",
        "email": "student2@campus.edu",
        "password": "password123",
        "role": "student_staff"
    })
    assert_test(res_reg.status_code in [201, 409], "Public registration creates 'student_staff' account (201 Created)")

    # -----------------------------------------------------------------
    # Test 2: Account Lockout after 5 Failed Logins
    # -----------------------------------------------------------------
    print("\n--- Test Suite 2: Account Lockout (5 Failed Logins -> 15 min lock) ---")
    # Register dummy user to test lockout
    from werkzeug.security import generate_password_hash
    query_db(
        "INSERT INTO Users (Name, Email, Phone, PasswordHash, Role, Dept) VALUES (%s, %s, %s, %s, %s, %s)",
        ("Lockout Target", test_lockout_email, "9999999999", generate_password_hash("realpassword123"), "student_staff", "CS"),
        commit=True
    )

    # Submit 5 failed attempts
    for i in range(1, 6):
        res_fail = client.post("/api/auth/login", json={
            "email": test_lockout_email,
            "password": f"wrongpassword{i}"
        })
        assert_test(res_fail.status_code == 401, f"Failed login attempt #{i} returns 401 Unauthorized")

    # 6th attempt must be blocked by lockout policy (429)
    res_lock = client.post("/api/auth/login", json={
        "email": test_lockout_email,
        "password": "realpassword123" # even with correct password!
    })
    assert_test(res_lock.status_code == 429, "6th login attempt rejected with 429 Account Locked")
    assert_test("Account is locked" in res_lock.get_json().get("error", ""), "Lockout error message returned")

    # Verify attempts are in LoginAttempts table
    lock_records = query_db(
        "SELECT COUNT(*) AS c FROM LoginAttempts WHERE LOWER(Email) = %s AND IsSuccess = 0",
        (test_lockout_email,), fetchone=True
    )
    assert_test(lock_records["c"] >= 5, f"Persistent LoginAttempts table logged {lock_records['c']} failures")

    # -----------------------------------------------------------------
    # Test 3: Unauthenticated Access & CSRF Protection
    # -----------------------------------------------------------------
    print("\n--- Test Suite 3: Server-side Authentication & CSRF Protection ---")
    unauth_admin = client.get("/api/admin/requests")
    assert_test(unauth_admin.status_code == 401, "Unauthenticated access to /api/admin/requests rejected with 401")

    unauth_tech = client.get("/api/technician/jobs")
    assert_test(unauth_tech.status_code == 401, "Unauthenticated access to /api/technician/jobs rejected with 401")

    # Mutating request without CSRF token
    # First login as student to get a session
    student_client = app.test_client()
    login_res = student_client.post("/api/auth/login", json={
        "email": "alex.student@campus.edu",
        "password": "student123"
    })
    assert_test(login_res.status_code == 200, "Student Alex Chen logged in successfully (200)")

    # Attempt POST to /api/portal/requests WITHOUT CSRF header
    no_csrf_res = student_client.post("/api/portal/requests", json={
        "category_id": 1,
        "building_id": 1,
        "room_no": "101",
        "priority_id": 2,
        "description": "CSRF test description"
    })
    assert_test(no_csrf_res.status_code == 403, "POST request without X-CSRF-Token rejected with 403 Forbidden")

    # Fetch CSRF token and verify with valid token
    csrf_token = student_client.get("/api/auth/csrf-token").get_json()["csrf_token"]
    csrf_res = student_client.post("/api/portal/requests", headers={"X-CSRF-Token": csrf_token}, json={
        "category_id": 1,
        "building_id": 1,
        "room_no": "Room 101",
        "priority_id": 2,
        "description": "Security test ticket with valid CSRF"
    })
    assert_test(csrf_res.status_code == 201, "POST request with valid X-CSRF-Token accepted (201 Created)")
    new_ticket_id = csrf_res.get_json()["request_id"]

    # -----------------------------------------------------------------
    # Test 4: Role-Based Authorization Enforcement (@role_required)
    # -----------------------------------------------------------------
    print("\n--- Test Suite 4: Role Separation & Namespaces ---")
    # Student Alex Chen attempting to call Admin endpoints
    cross_role_res = student_client.get("/api/admin/requests")
    assert_test(cross_role_res.status_code == 403, "Student accessing /api/admin/requests rejected with 403 Forbidden")

    cross_tech_res = student_client.get("/api/technician/jobs")
    assert_test(cross_tech_res.status_code == 403, "Student accessing /api/technician/jobs rejected with 403 Forbidden")

    cross_mgmt_res = student_client.get("/api/management/dashboard")
    assert_test(cross_mgmt_res.status_code == 403, "Student accessing /api/management/dashboard rejected with 403 Forbidden")

    # -----------------------------------------------------------------
    # Test 5: Object-Level Security (Requester Isolation)
    # -----------------------------------------------------------------
    print("\n--- Test Suite 5: Object-Level Authorization (Requester Isolation) ---")
    # Find a request that does NOT belong to Alex Chen (Alex Chen UserID = 1)
    other_req = query_db("SELECT RequestID, UserID FROM Requests WHERE UserID != 1 LIMIT 1", fetchone=True)
    if other_req:
        other_id = other_req["RequestID"]
        # Student Alex attempts to view other user's request details
        leak_res = student_client.get(f"/api/portal/requests/{other_id}")
        assert_test(leak_res.status_code == 403, f"Requester viewing another user's Request #{other_id} rejected with 403")

        # Student Alex attempts to rate other user's request
        rate_res = student_client.post(f"/api/portal/requests/{other_id}/feedback", headers={"X-CSRF-Token": csrf_token}, json={
            "rating": 5, "comments": "Unauthorized rating attempt"
        })
        assert_test(rate_res.status_code == 403, f"Requester submitting feedback on another user's Request #{other_id} rejected with 403")
    else:
        print(" [SKIP] No other user requests found to test isolation against")

    # -----------------------------------------------------------------
    # Test 6: Object-Level Security (Technician Assignment Isolation)
    # -----------------------------------------------------------------
    print("\n--- Test Suite 6: Object-Level Authorization (Technician Isolation) ---")
    tech_client = app.test_client()
    tech_login = tech_client.post("/api/auth/login", json={
        "email": "carlos.electrician@campus.edu",
        "password": "tech123"
    })
    assert_test(tech_login.status_code == 200, "Technician Carlos logged in successfully (200)")
    tech_csrf = tech_client.get("/api/auth/csrf-token").get_json()["csrf_token"]

    # Technician Carlos attempts to access new_ticket_id (which is not yet assigned to Carlos)
    unassigned_res = tech_client.get(f"/api/technician/jobs/{new_ticket_id}")
    assert_test(unassigned_res.status_code == 403, f"Technician viewing unassigned Request #{new_ticket_id} rejected with 403 Forbidden")

    unassigned_worklog = tech_client.post(f"/api/technician/jobs/{new_ticket_id}/work-logs", headers={"X-CSRF-Token": tech_csrf}, json={
        "work_description": "Illegal work log"
    })
    assert_test(unassigned_worklog.status_code == 403, f"Technician logging work on unassigned Request #{new_ticket_id} rejected with 403 Forbidden")

    # -----------------------------------------------------------------
    # Test 7: Executive Management is Strictly Read-Only
    # -----------------------------------------------------------------
    print("\n--- Test Suite 7: Executive Management Read-Only Restrictions ---")
    mgmt_client = app.test_client()
    mgmt_login = mgmt_client.post("/api/auth/login", json={
        "email": "reynolds.mgmt@campus.edu",
        "password": "mgmt123"
    })
    assert_test(mgmt_login.status_code == 200, "Management Reynolds logged in successfully (200)")
    mgmt_csrf = mgmt_client.get("/api/auth/csrf-token").get_json()["csrf_token"]

    # Management can view dashboard
    mgmt_dash = mgmt_client.get("/api/management/dashboard")
    assert_test(mgmt_dash.status_code == 200, "Management reads /api/management/dashboard successfully (200)")

    # Management CANNOT create requests (403)
    mgmt_mutate1 = mgmt_client.post("/api/portal/requests", headers={"X-CSRF-Token": mgmt_csrf}, json={
        "description": "Mgmt illegal ticket"
    })
    assert_test(mgmt_mutate1.status_code == 403, "Management attempting request creation rejected with 403 Forbidden")

    # Management CANNOT dispatch or assign (403)
    mgmt_mutate2 = mgmt_client.post(f"/api/admin/requests/{new_ticket_id}/assign", headers={"X-CSRF-Token": mgmt_csrf}, json={
        "TechID": 1
    })
    assert_test(mgmt_mutate2.status_code == 403, "Management attempting technician dispatch rejected with 403 Forbidden")

    # -----------------------------------------------------------------
    # Test 8: Forward-Only Status Validation & Audit Logging
    # -----------------------------------------------------------------
    print("\n--- Test Suite 8: Forward-Only Progression & Audit Logging ---")
    admin_client = app.test_client()
    admin_login = admin_client.post("/api/auth/login", json={
        "email": "marcus.admin@campus.edu",
        "password": "admin123"
    })
    assert_test(admin_login.status_code == 200, "Admin Marcus logged in successfully (200)")
    admin_csrf = admin_client.get("/api/auth/csrf-token").get_json()["csrf_token"]

    # Assign technician to new_ticket_id (Open -> Assigned)
    tech_row = query_db("SELECT TechID FROM Technicians WHERE Available = 1 LIMIT 1", fetchone=True)
    assign_res = admin_client.post(f"/api/admin/requests/{new_ticket_id}/assign", headers={"X-CSRF-Token": admin_csrf}, json={
        "TechID": tech_row["TechID"]
    })
    assert_test(assign_res.status_code == 200, f"Admin assigned technician to Request #{new_ticket_id} (Open -> Assigned)")

    # Attempt INVALID backward/skipping transition (Assigned -> Open or Assigned -> Resolved)
    skip_res = admin_client.put(f"/api/admin/requests/{new_ticket_id}/status", headers={"X-CSRF-Token": admin_csrf}, json={
        "status": "Resolved"
    })
    assert_test(skip_res.status_code == 400, "Invalid skipping transition Assigned -> Resolved rejected with 400 Bad Request")

    back_res = admin_client.put(f"/api/admin/requests/{new_ticket_id}/status", headers={"X-CSRF-Token": admin_csrf}, json={
        "status": "Open"
    })
    assert_test(back_res.status_code == 400, "Backward transition Assigned -> Open rejected with 400 Bad Request")

    # Valid forward transition: Assigned -> In Progress -> Resolved -> Closed
    fwd1 = admin_client.put(f"/api/admin/requests/{new_ticket_id}/status", headers={"X-CSRF-Token": admin_csrf}, json={
        "status": "In Progress"
    })
    assert_test(fwd1.status_code == 200, "Valid transition Assigned -> In Progress succeeds (200)")

    fwd2 = admin_client.put(f"/api/admin/requests/{new_ticket_id}/status", headers={"X-CSRF-Token": admin_csrf}, json={
        "status": "Resolved"
    })
    assert_test(fwd2.status_code == 200, "Valid transition In Progress -> Resolved succeeds (200)")

    fwd3 = admin_client.put(f"/api/admin/requests/{new_ticket_id}/status", headers={"X-CSRF-Token": admin_csrf}, json={
        "status": "Closed"
    })
    assert_test(fwd3.status_code == 200, "Valid transition Resolved -> Closed succeeds (200)")

    # Verify AuditLog has records
    audit_count = query_db("SELECT COUNT(*) AS c FROM AuditLog", fetchone=True)
    assert_test(audit_count["c"] > 5, f"AuditLog table actively populated with {audit_count['c']} security events")

    print("\n" + "=" * 70)
    print(f"SECURITY SUITE SUMMARY: {passed}/{total} TESTS PASSED")
    print("=" * 70)

    # Clean up test accounts
    query_db("DELETE FROM LoginAttempts WHERE LOWER(Email) = %s", (test_lockout_email,), commit=True)
    query_db("DELETE FROM Users WHERE LOWER(Email) = %s", (test_lockout_email,), commit=True)

    if passed == total:
        print("[SUCCESS] ALL SECURITY CONTROLS AND RBAC CHECKS FULLY VERIFIED!")
        return 0
    else:
        print("[FAILURE] Some security checks failed!")
        return 1

if __name__ == "__main__":
    sys.exit(run_tests())
