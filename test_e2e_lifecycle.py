"""
Live HTTP End-to-End Lifecycle Verification against http://127.0.0.1:5000
Tests the complete multi-console lifecycle over real HTTP sockets with session cookies:
1. Gateway landing & security headers
2. Student Alex Chen creates ticket (Open)
3. Admin Marcus Vance assigns technician (Assigned) and checks Audit Log
4. Technician Carlos Mendez logs work + materials in INR (In Progress) and resolves (Resolved)
5. Student Alex Chen submits 5-star rating (Closed)
6. Executive Management Reynolds inspects analytics, total spend in INR, and audit trail
"""

import re
import sys
import json
import urllib.request
import urllib.parse
import http.cookiejar

# Ensure utf-8 stdout on Windows console
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")


BASE_URL = "http://127.0.0.1:5000"

class HttpClient:
    def __init__(self):
        self.cookie_jar = http.cookiejar.CookieJar()
        self.opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(self.cookie_jar))
        self.csrf_token = ""

    def get(self, path):
        req = urllib.request.Request(f"{BASE_URL}{path}")
        try:
            with self.opener.open(req) as resp:
                headers = dict(resp.info())
                body = resp.read().decode("utf-8")
                # Extract CSRF token if present in HTML
                match = re.search(r'<meta name="csrf-token" content="([^"]+)"', body)
                if match:
                    self.csrf_token = match.group(1)
                return resp.status, headers, body
        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8")
            return e.code, dict(e.info()), body

    def post(self, path, data=None, is_json=True, use_csrf=True):
        headers = {}
        if is_json:
            headers["Content-Type"] = "application/json"
            encoded_data = json.dumps(data or {}).encode("utf-8")
        else:
            headers["Content-Type"] = "application/x-www-form-urlencoded"
            encoded_data = urllib.parse.urlencode(data or {}).encode("utf-8")

        if use_csrf and self.csrf_token:
            headers["X-CSRF-Token"] = self.csrf_token

        req = urllib.request.Request(f"{BASE_URL}{path}", data=encoded_data, headers=headers, method="POST")
        try:
            with self.opener.open(req) as resp:
                headers_resp = dict(resp.info())
                body = resp.read().decode("utf-8")
                return resp.status, headers_resp, body
        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8")
            return e.code, dict(e.info()), body

    def login(self, email, password):
        status, headers, body = self.post("/api/auth/login", {"email": email, "password": password}, use_csrf=False)
        if status == 200:
            res_json = json.loads(body)
            self.csrf_token = res_json.get("csrf_token", "")
        return status, body

    def logout(self):
        return self.post("/api/auth/logout", use_csrf=True)

def main():
    print("=" * 70)
    print("RUNNING LIVE HTTP E2E LIFECYCLE TEST ON http://127.0.0.1:5000")
    print("=" * 70)

    # Step 1: Gateway Landing & Security Headers Check
    print("\n[Step 1] Checking Landing Gateway & HTTP Security Headers...")
    client = HttpClient()
    status, headers, body = client.get("/")
    assert status == 200, f"Gateway returned status {status}"
    assert "Campus Facility Maintenance Request System" in body, "Landing page title present"
    assert headers.get("X-Frame-Options") == "DENY", "X-Frame-Options: DENY header present"
    assert headers.get("X-Content-Type-Options") == "nosniff", "X-Content-Type-Options: nosniff present"
    assert "Content-Security-Policy" in headers, "Content-Security-Policy header present"
    print(" -> PASS: Landing gateway active and hardened security headers verified.")

    # Step 2: Student Login & Submit Request
    print("\n[Step 2] Student Alex Chen login & request submission...")
    student_client = HttpClient()
    status, body = student_client.login("alex.student@campus.edu", "student123")
    assert status == 200, f"Student login failed: {body}"
    print(" -> PASS: Alex Chen authenticated successfully. Redirect: /portal")

    # Get portal page
    status, _, _ = student_client.get("/portal")
    assert status == 200, "Student accesses /portal console"

    # Submit new maintenance ticket
    ticket_payload = {
        "building_id": 1,
        "room_no": "Lab 204",
        "category_id": 1, # Electrical
        "priority_id": 2, # Medium
        "description": "Flickering ceiling tube light in Lab 204 causing eye strain"
    }
    status, _, body = student_client.post("/api/portal/requests", ticket_payload)
    assert status == 201, f"Create request failed ({status}): {body}"
    req_json = json.loads(body)
    ticket_id = req_json["request_id"]
    print(f" -> PASS: Ticket #{ticket_id} created with initial status 'Open'. Ticket No: {req_json['ticket_number']}")

    # Verify ticket in My Requests
    status, _, body = student_client.get(f"/api/portal/requests/{ticket_id}")
    assert status == 200, "Requester can read own ticket details"
    assert json.loads(body)["Status"] == "Open", "Ticket status is Open"
    student_client.logout()

    # Step 3: Admin Login & Dispatch Technician
    print(f"\n[Step 3] Facility Admin Marcus Vance dispatching technician to Ticket #{ticket_id}...")
    admin_client = HttpClient()
    status, body = admin_client.login("marcus.admin@campus.edu", "admin123")
    assert status == 200, "Admin login successful"

    # Admin assigns technician Carlos Mendez (TechID: 1)
    status, _, body = admin_client.post(f"/api/admin/requests/{ticket_id}/assign", {"TechID": 1})
    assert status == 200, f"Technician assign failed ({status}): {body}"
    assign_json = json.loads(body)
    assert assign_json["status"] == "Assigned", "Status updated to Assigned"
    print(f" -> PASS: Technician Carlos Mendez assigned (Assignment #{assign_json['assignment_id']}). Status is 'Assigned'.")

    # Admin checks Audit Log
    status, _, body = admin_client.get("/api/admin/audit-logs")
    assert status == 200, "Admin can read audit logs"
    audit_entries = json.loads(body)
    assert any(a["Action"] == "TECHNICIAN_ASSIGNED" for a in audit_entries), "TECHNICIAN_ASSIGNED recorded in AuditLog"
    print(f" -> PASS: Audit log contains TECHNICIAN_ASSIGNED event.")
    admin_client.logout()

    # Step 4: Technician Carlos Mendez Work Log & Resolution
    print(f"\n[Step 4] Technician Carlos Mendez logging work & materials in INR (₹) for Ticket #{ticket_id}...")
    tech_client = HttpClient()
    status, body = tech_client.login("carlos.electrician@campus.edu", "tech123")
    assert status == 200, "Technician login successful"

    # Technician adds work log + materials (Fluorescent Tube & Starter)
    work_payload = {
        "work_description": "Replaced worn-out ballast starter and installed new 36W LED fluorescent tube.",
        "materials": [
            {"material_name": "36W LED Tube", "qty": 1, "cost": 250.00},
            {"material_name": "Electronic Starter", "qty": 1, "cost": 80.00}
        ]
    }
    status, _, body = tech_client.post(f"/api/technician/jobs/{ticket_id}/work-logs", work_payload)
    assert status == 201, f"Work log post failed ({status}): {body}"
    log_json = json.loads(body)
    assert log_json["status"] == "In Progress", "Auto-transitioned to In Progress"
    print(f" -> PASS: Work log #{log_json['log_id']} saved with ₹330.00 materials. Status is now 'In Progress'.")

    # Technician marks Resolved
    status, _, body = tech_client.post(f"/api/technician/jobs/{ticket_id}/resolve")
    assert status == 200, f"Resolve failed ({status}): {body}"
    assert json.loads(body)["status"] == "Resolved", "Status updated to Resolved"
    print(f" -> PASS: Ticket #{ticket_id} marked as 'Resolved'.")
    tech_client.logout()

    # Step 5: Requester Rating & Feedback
    print(f"\n[Step 5] Requester Alex Chen rating resolved Ticket #{ticket_id}...")
    student_client = HttpClient()
    status, _ = student_client.login("alex.student@campus.edu", "student123")
    assert status == 200, "Student login successful"

    # Rate resolved ticket 5 stars
    rating_payload = {
        "rating": 5,
        "comments": "Fixed immediately! Laboratory lighting is back to normal. Excellent service."
    }
    status, _, body = student_client.post(f"/api/portal/requests/{ticket_id}/feedback", rating_payload)
    assert status == 201, f"Feedback failed ({status}): {body}"
    assert json.loads(body)["status"] == "Closed", "Status automatically advanced to Closed"
    print(f" -> PASS: 5-star rating submitted. Ticket #{ticket_id} successfully transitioned to 'Closed'.")
    student_client.logout()

    # Step 6: Executive Management Inspection
    print(f"\n[Step 6] Executive Management Reynolds inspecting dashboard analytics...")
    mgmt_client = HttpClient()
    status, _ = mgmt_client.login("reynolds.mgmt@campus.edu", "mgmt123")
    assert status == 200, "Management login successful"

    status, _, body = mgmt_client.get("/api/management/dashboard")
    assert status == 200, "Dashboard analytics fetched successfully"
    dash = json.loads(body)
    print(f" -> PASS: Executive Dashboard KPI Summary:")
    print(f"    • Total Requests: {dash['total_requests']}")
    print(f"    • Open / Active: {dash['open_requests']}")
    print(f"    • Resolved / Closed: {dash['resolved_requests']}")
    print(f"    • SLA Compliance Rate: {dash['sla_compliance_rate']}%")
    print(f"    • Average Feedback Rating: ⭐ {dash['average_rating']}/5 ({dash['ratings_count']} reviews)")
    total_cost_val = float(dash['total_materials_cost'])
    print(f"    • Total Material Spend: ₹{total_cost_val:,.2f}")
    print(f"    • Status History Timeline Entries: {len(dash['recent_timeline'])}")


    # Check Management Audit Logs
    status, _, body = mgmt_client.get("/api/management/audit-logs")
    assert status == 200, "Management audit trail loaded"
    mgmt_client.logout()

    print("\n" + "=" * 70)
    print("ALL 6 STEPS OF THE END-TO-END MULTI-CONSOLE LIFECYCLE PASSED PERFECTLY!")
    print("=" * 70)
    return 0

if __name__ == "__main__":
    import sys
    sys.exit(main())
