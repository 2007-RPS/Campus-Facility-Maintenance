import os
import re
import json
import time
import secrets
import datetime
from functools import wraps
from flask import Flask, request, jsonify, render_template, session, redirect, url_for, make_response
from werkzeug.security import check_password_hash, generate_password_hash
from dotenv import load_dotenv
from db import query_db, get_engine_status, get_db_connection

load_dotenv()

app = Flask(__name__, static_folder="static", template_folder="templates")
app.secret_key = os.getenv("SECRET_KEY", "campus_fms_super_secret_key_2026_development")

class VercelPathFixMiddleware:
    """Restores the true requested path when Vercel rewrites forward to an entrypoint."""
    def __init__(self, wsgi_app):
        self.wsgi_app = wsgi_app

    def __call__(self, environ, start_response):
        original_uri = environ.get("HTTP_X_FORWARDED_URI") or environ.get("HTTP_X_MATCHED_PATH")
        path_info = environ.get("PATH_INFO", "")
        if original_uri:
            path_only = original_uri.split("?")[0]
            if path_only and path_only not in ("/api/index", "/api/index.py"):
                environ["PATH_INFO"] = path_only
        elif path_info in ("/api/index", "/api/index.py", "/app.py"):
            environ["PATH_INFO"] = "/"
        return self.wsgi_app(environ, start_response)

app.wsgi_app = VercelPathFixMiddleware(app.wsgi_app)

# Session & Cookie Security
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
app.config["SESSION_COOKIE_SECURE"] = os.getenv("COOKIE_SECURE", "false").lower() == "true"

DEMO_MODE = os.getenv("DEMO_MODE", "false").lower() == "true"

# Forward-only status transitions
VALID_TRANSITIONS = {
    "Open": ["Assigned"],
    "Assigned": ["In Progress"],
    "In Progress": ["Resolved"],
    "Resolved": ["Closed"],
    "Closed": []
}

# Role console home routes
ROLE_DASHBOARDS = {
    "student_staff": "/portal",
    "technician": "/technician",
    "facility_admin": "/admin",
    "management": "/management"
}

ROLE_LOGIN_PAGES = {
    "student_staff": "/portal/login",
    "technician": "/technician/login",
    "facility_admin": "/admin/login",
    "management": "/management/login"
}

# =====================================================================
# Security Helpers & Middleware
# =====================================================================

def get_client_ip():
    """Extracts client IP safely considering proxies."""
    ip = request.headers.get("X-Forwarded-For", request.remote_addr) or "127.0.0.1"
    if "," in ip:
        ip = ip.split(",")[0].strip()
    return ip[:45]

def log_audit(action, details=None, user_id=None):
    """
    Records an entry in the AuditLog table:
    LogID, UserID, Action, Details, IP, Timestamp
    """
    uid = user_id if user_id is not None else session.get("user_id")
    det_str = json.dumps(details) if isinstance(details, (dict, list)) else (str(details) if details is not None else "")
    ip = get_client_ip()
    try:
        query_db(
            "INSERT INTO AuditLog (UserID, Action, Details, IP) VALUES (%s, %s, %s, %s)",
            (uid, action, det_str, ip),
            commit=True
        )
    except Exception as e:
        print(f"[!] Audit log write failure ({action}): {e}")

def check_account_lockout(email):
    """
    Checks LoginAttempts table for lockout:
    Lock account for 15 minutes after 5 consecutive failed logins.
    Returns: (is_locked: bool, remaining_minutes: int, failed_count: int)
    """
    email_clean = (email or "").strip().lower()
    if not email_clean:
        return False, 0, 0

    # Count failed attempts in the last 15 minutes since the last success
    query = """
        SELECT COUNT(*) AS failed_count, MAX(AttemptTime) AS last_attempt
        FROM LoginAttempts
        WHERE LOWER(Email) = %s AND IsSuccess = 0
          AND AttemptTime >= NOW() - INTERVAL 15 MINUTE
          AND AttemptTime > COALESCE((
              SELECT MAX(AttemptTime) FROM LoginAttempts 
              WHERE LOWER(Email) = %s AND IsSuccess = 1
          ), '1970-01-01 00:00:00')
    """
    row = query_db(query, (email_clean, email_clean), fetchone=True)
    failed_count = row["failed_count"] if row and row["failed_count"] else 0

    if failed_count >= 5:
        last_attempt = row["last_attempt"]
        remaining = 15
        if isinstance(last_attempt, datetime.datetime):
            elapsed = (datetime.datetime.now() - last_attempt).total_seconds()
            remaining = max(1, int((900 - elapsed) / 60))
        return True, remaining, failed_count
    return False, 0, failed_count

def record_login_attempt(email, is_success):
    """Logs an attempt into the persistent LoginAttempts table."""
    email_clean = (email or "").strip().lower()
    ip = get_client_ip()
    try:
        query_db(
            "INSERT INTO LoginAttempts (Email, IPAddress, IsSuccess) VALUES (%s, %s, %s)",
            (email_clean, ip, 1 if is_success else 0),
            commit=True
        )
    except Exception as e:
        print(f"[!] LoginAttempts write error: {e}")

def get_current_user_obj():
    """Returns the authenticated user dict from session or None."""
    user_id = session.get("user_id")
    if not user_id:
        return None
    user = query_db(
        "SELECT UserID, Name, Email, Phone, Role, Dept FROM Users WHERE UserID = %s",
        (user_id,), fetchone=True
    )
    return normalize_row(user) if user else None

def normalize_row(row):
    """Standardizes row dict with both Review 1 PascalCase and friendly aliases."""
    if not isinstance(row, dict):
        return row
    d = dict(row)
    if "RequestID" in d:
        d["id"] = d["RequestID"]
        d["request_id"] = d["RequestID"]
        d["ticket_number"] = f"REQ-2026-{d['RequestID']:03d}"
    if "UserID" in d:
        d["user_id"] = d["UserID"]
    if "CategoryID" in d:
        d["category_id"] = d["CategoryID"]
    if "CategoryName" in d:
        d["category_name"] = d["CategoryName"]
    if "BuildingID" in d:
        d["building_id"] = d["BuildingID"]
    if "BuildingName" in d:
        d["building_name"] = d["BuildingName"]
    if "RoomNo" in d:
        d["room"] = d["RoomNo"]
        d["room_no"] = d["RoomNo"]
    if "PriorityID" in d:
        d["priority_id"] = d["PriorityID"]
    if "PriorityLabel" in d:
        d["priority"] = d["PriorityLabel"]
        d["label"] = d["PriorityLabel"]
    if "SLAHours" in d:
        d["sla_hours"] = d["SLAHours"]
    if "Status" in d:
        d["status"] = d["Status"]
    if "RequestDate" in d:
        d["request_date"] = str(d["RequestDate"])
    if "Rating" in d:
        d["rating"] = d["Rating"]
    if "Comments" in d:
        d["comments"] = d["Comments"]
    if "FeedbackComments" in d:
        d["comments"] = d["FeedbackComments"]
    if "TechID" in d:
        d["tech_id"] = d["TechID"]
    if "Skill" in d:
        d["skill"] = d["Skill"]
    return d

# =====================================================================
# Application Request Hooks
# =====================================================================

@app.before_request
def handle_security_and_session():
    # 1. Ensure CSRF token exists in session
    if "csrf_token" not in session:
        session["csrf_token"] = secrets.token_hex(32)

    # 2. Check 30-minute idle session timeout
    if "user_id" in session:
        now = time.time()
        last_active = session.get("last_active")
        if last_active and (now - last_active > 1800):  # 30 minutes
            user_id = session.get("user_id")
            session.clear()
            log_audit("SESSION_EXPIRED", "Session timed out after 30 minutes of inactivity", user_id=user_id)
            if request.path.startswith("/api/"):
                return jsonify({"error": "Session expired due to 30 minutes of inactivity. Please log in again.", "expired": True}), 401
            return redirect("/?expired=1")
        session["last_active"] = now

    # 3. CSRF Protection for state-changing HTTP methods
    if request.method in ["POST", "PUT", "DELETE", "PATCH"]:
        # Exempt authentication entrypoints that establish a new session
        if request.path in ["/api/auth/login", "/api/auth/register"]:
            return None

        submitted_token = request.headers.get("X-CSRF-Token") or request.form.get("csrf_token")
        session_token = session.get("csrf_token")
        if not submitted_token or not session_token or not secrets.compare_digest(str(submitted_token), str(session_token)):
            if request.path.startswith("/api/"):
                return jsonify({"error": "CSRF verification failed. Missing or invalid X-CSRF-Token header."}), 403
            return render_template("403.html", error_message="CSRF token validation failed."), 403

@app.after_request
def apply_security_headers(response):
    """Sets hardened HTTP security headers."""
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; "
        "script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
        "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
        "font-src 'self' https://fonts.gstatic.com data:; "
        "img-src 'self' data:; "
        "connect-src 'self';"
    )
    return response

@app.context_processor
def inject_globals():
    return {
        "csrf_token": session.get("csrf_token", ""),
        "current_user": get_current_user_obj(),
        "demo_mode": DEMO_MODE,
        "now_year": datetime.datetime.now().year
    }

# =====================================================================
# Authorization Decorator (@role_required)
# =====================================================================

def role_required(*allowed_roles):
    """
    Enforces authentication and server-side role check.
    Rejects unauthorized access with 401 (if unauthenticated) or 403 (if role disallowed).
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            user_id = session.get("user_id")
            if not user_id:
                if request.path.startswith("/api/"):
                    return jsonify({"error": "Authentication required. Please log in."}), 401
                # Redirect to appropriate login page
                for role, prefix in [("student_staff", "/portal"), ("technician", "/technician"), ("facility_admin", "/admin"), ("management", "/management")]:
                    if request.path.startswith(prefix):
                        return redirect(f"{prefix}/login")
                return redirect("/login")

            user_role = session.get("user_role")
            if user_role not in allowed_roles:
                if request.path.startswith("/api/"):
                    return jsonify({
                        "error": f"Access denied. Required role in {list(allowed_roles)}, but current role is '{user_role}'."
                    }), 403
                return render_template("403.html", user_role=user_role, allowed_roles=allowed_roles), 403

            return f(*args, **kwargs)
        return decorated_function
    return decorator

# =====================================================================
# Public Web Routes & Role Login Views
# =====================================================================

@app.route("/favicon.ico")
def favicon():
    return "", 204

@app.route("/")
@app.route("/api/index")
@app.route("/api/index.py")
def index():
    """Landing gateway directing users to their respective consoles."""
    user = get_current_user_obj()
    return render_template("landing.html", user=user)

@app.route("/login")
def login_gateway():
    user = get_current_user_obj()
    if user and user["Role"] in ROLE_DASHBOARDS:
        return redirect(ROLE_DASHBOARDS[user["Role"]])
    return redirect("/portal/login")

@app.route("/logout")
def logout_view():
    if "user_id" in session:
        log_audit("USER_LOGOUT", "User logged out via web view")
    session.clear()
    return redirect("/")

# 1. Student / Staff Console & Auth
@app.route("/portal")
@role_required("student_staff")
def portal_console():
    return render_template("portal.html")

@app.route("/portal/login")
def portal_login():
    if session.get("user_role") == "student_staff":
        return redirect("/portal")
    return render_template("portal_login.html")

@app.route("/portal/register")
def portal_register():
    if session.get("user_role") == "student_staff":
        return redirect("/portal")
    return render_template("portal_register.html")

# 2. Technician Console & Auth
@app.route("/technician")
@role_required("technician")
def technician_console():
    return render_template("technician.html")

@app.route("/technician/login")
def technician_login():
    if session.get("user_role") == "technician":
        return redirect("/technician")
    return render_template("tech_login.html")

# 3. Facility Admin Console & Auth
@app.route("/admin")
@role_required("facility_admin")
def admin_console():
    return render_template("admin.html")

@app.route("/admin/login")
def admin_login():
    if session.get("user_role") == "facility_admin":
        return redirect("/admin")
    return render_template("admin_login.html")

# 4. Management Console & Auth
@app.route("/management")
@role_required("management")
def management_console():
    return render_template("management.html")

@app.route("/management/login")
def management_login():
    if session.get("user_role") == "management":
        return redirect("/management")
    return render_template("mgmt_login.html")

# =====================================================================
# Authentication API (/api/auth/...)
# =====================================================================

@app.route("/api/auth/csrf-token", methods=["GET"])
def api_auth_csrf():
    return jsonify({"csrf_token": session.get("csrf_token")})

@app.route("/api/auth/me", methods=["GET"])
def api_auth_me():
    user = get_current_user_obj()
    if not user:
        return jsonify({"authenticated": False}), 401
    return jsonify({
        "authenticated": True,
        "user": user,
        "csrf_token": session.get("csrf_token")
    })

@app.route("/api/auth/login", methods=["POST"])
def api_auth_login():
    """
    Real authentication:
    - Checks 15-minute lockout for 5 failed logins via LoginAttempts table
    - Validates hashed password
    - Starts secure session with last_active timestamp
    - Writes to AuditLog
    """
    data = request.get_json() or {}
    email = (data.get("email") or "").strip().lower()
    password = data.get("password") or ""
    expected_role = data.get("role")  # Optional role hint from role login forms

    if not email or not password:
        return jsonify({"error": "Email and password are required"}), 400

    # 1. Lockout verification from LoginAttempts table
    is_locked, remaining_mins, failed_count = check_account_lockout(email)
    if is_locked:
        log_audit("LOGIN_LOCKED_ATTEMPT", f"Login attempted while account locked ({failed_count} failed attempts)", user_id=None)
        return jsonify({
            "error": f"Account is locked due to 5 consecutive failed login attempts. Please try again in {remaining_mins} minute(s)."
        }), 429

    # 2. User lookup
    user = query_db(
        "SELECT UserID, Name, Email, Phone, PasswordHash, Role, Dept FROM Users WHERE LOWER(Email) = %s",
        (email,), fetchone=True
    )

    if not user or not check_password_hash(user["PasswordHash"], password):
        record_login_attempt(email, is_success=False)
        log_audit("LOGIN_FAILED", f"Invalid credentials for email {email}", user_id=user["UserID"] if user else None)
        
        # Recalculate remaining attempts
        _, _, new_failed = check_account_lockout(email)
        remaining_attempts = max(0, 5 - new_failed)
        return jsonify({
            "error": "Invalid email or password.",
            "attempts_remaining": remaining_attempts
        }), 401

    # Check if role matches expected role if specified by role-specific login
    if expected_role and user["Role"] != expected_role:
        record_login_attempt(email, is_success=False)
        log_audit("LOGIN_ROLE_MISMATCH", f"User {email} tried logging in via {expected_role} portal but role is {user['Role']}", user_id=user["UserID"])
        return jsonify({
            "error": f"Role mismatch: This account has role '{user['Role']}'. Please use the appropriate portal login."
        }), 403

    # 3. Successful login
    record_login_attempt(email, is_success=True)
    session["user_id"] = user["UserID"]
    session["user_role"] = user["Role"]
    session["last_active"] = time.time()
    session["csrf_token"] = secrets.token_hex(32)

    log_audit("USER_LOGIN", f"Successful login for {user['Name']} ({user['Role']})", user_id=user["UserID"])

    redirect_url = ROLE_DASHBOARDS.get(user["Role"], "/")
    user_info = {k: user[k] for k in ["UserID", "Name", "Email", "Phone", "Role", "Dept"]}

    return jsonify({
        "message": "Login successful",
        "user": user_info,
        "redirect_url": redirect_url,
        "csrf_token": session["csrf_token"]
    })

@app.route("/api/auth/register", methods=["POST"])
def api_auth_register():
    """
    Public registration:
    Strictly creates ONLY Student/Staff accounts.
    Rejects any attempt to register as technician, admin, or management.
    """
    data = request.get_json() or {}
    name = (data.get("name") or "").strip()
    email = (data.get("email") or "").strip().lower()
    phone = (data.get("phone") or "").strip()
    password = data.get("password") or ""
    dept = (data.get("dept") or "General").strip()

    # Reject attempt to escalate role
    requested_role = data.get("role")
    if requested_role and requested_role != "student_staff":
        return jsonify({
            "error": "Public registration is only permitted for Student/Staff accounts. Administrative and technician accounts must be created by a Facility Admin."
        }), 403

    if not name or not email or not password:
        return jsonify({"error": "Name, email, and password are required"}), 400

    if not re.match(r"^[^@]+@[^@]+\.[^@]+$", email):
        return jsonify({"error": "Invalid email address format"}), 400

    if len(password) < 6:
        return jsonify({"error": "Password must be at least 6 characters"}), 400

    # Check for existing email
    existing = query_db("SELECT UserID FROM Users WHERE LOWER(Email) = %s", (email,), fetchone=True)
    if existing:
        return jsonify({"error": "An account with this email already exists"}), 409

    pwd_hash = generate_password_hash(password)
    user_id = query_db(
        "INSERT INTO Users (Name, Email, Phone, PasswordHash, Role, Dept) VALUES (%s, %s, %s, %s, %s, %s)",
        (name, email, phone, pwd_hash, "student_staff", dept),
        commit=True
    )

    log_audit("PUBLIC_REGISTRATION", f"New Student/Staff registered: {name} ({email})", user_id=user_id)

    return jsonify({
        "message": "Registration successful. You can now log in.",
        "redirect_url": "/portal/login",
        "user_id": user_id
    }), 201

@app.route("/api/auth/logout", methods=["POST"])
def api_auth_logout():
    uid = session.get("user_id")
    if uid:
        log_audit("USER_LOGOUT", "User logged out", user_id=uid)
    session.clear()
    return jsonify({"message": "Logged out successfully", "redirect_url": "/"})

@app.route("/api/auth/demo-users", methods=["GET"])
def api_auth_demo_users():
    """Lists demo users ONLY when DEMO_MODE=true in .env, otherwise 403."""
    if not DEMO_MODE:
        return jsonify({"error": "Demo mode is disabled in production."}), 403
    users = query_db("SELECT UserID, Name, Email, Phone, Role, Dept FROM Users ORDER BY Role, UserID")
    return jsonify([normalize_row(u) for u in users])

# =====================================================================
# Student / Staff Portal API (/api/portal/...)
# =====================================================================

@app.route("/api/portal/metadata", methods=["GET"])
@role_required("student_staff", "facility_admin")
def api_portal_metadata():
    """Metadata needed for ticket submission: categories, buildings, facilities, priorities."""
    categories = query_db("SELECT CategoryID, CategoryName, Description FROM Categories ORDER BY CategoryName")
    buildings = query_db("SELECT BuildingID, BuildingName, Address FROM Buildings ORDER BY BuildingName")
    facilities = query_db("""
        SELECT f.FacilityID, f.BuildingID, f.RoomNo, f.Floor, f.Type, b.BuildingName 
        FROM Facilities f 
        JOIN Buildings b ON f.BuildingID = b.BuildingID 
        ORDER BY b.BuildingName, f.RoomNo
    """)
    priorities = query_db("SELECT PriorityID, Label, SLAHours FROM Priorities ORDER BY SLAHours ASC")
    return jsonify({
        "categories": [normalize_row(c) for c in categories],
        "buildings": [normalize_row(b) for b in buildings],
        "facilities": [normalize_row(f) for f in facilities],
        "priorities": [normalize_row(p) for p in priorities]
    })

@app.route("/api/portal/requests", methods=["GET"])
@role_required("student_staff")
def api_portal_get_my_requests():
    """
    Object-level check:
    Requesters can access ONLY their own requests.
    """
    user_id = session["user_id"]
    status = request.args.get("status")

    query = """
        SELECT r.RequestID, r.UserID, r.FacilityID, r.CategoryID, r.PriorityID,
               r.Description, r.Status, r.RequestDate,
               u.Name AS RequesterName, u.Email AS RequesterEmail,
               b.BuildingName, f.RoomNo, f.Floor,
               c.CategoryName,
               p.Label AS PriorityLabel, p.SLAHours,
               DATE_ADD(r.RequestDate, INTERVAL p.SLAHours HOUR) AS SLADueDate,
               fb.Rating, fb.Comments AS FeedbackComments, fb.FeedbackDate,
               (SELECT GROUP_CONCAT(u_tech.Name SEPARATOR ', ')
                FROM Assignments a
                JOIN Technicians t ON a.TechID = t.TechID
                JOIN Users u_tech ON t.UserID = u_tech.UserID
                WHERE a.RequestID = r.RequestID) AS AssignedTechnicians
        FROM Requests r
        JOIN Users u ON r.UserID = u.UserID
        JOIN Facilities f ON r.FacilityID = f.FacilityID
        JOIN Buildings b ON f.BuildingID = b.BuildingID
        JOIN Categories c ON r.CategoryID = c.CategoryID
        JOIN Priorities p ON r.PriorityID = p.PriorityID
        LEFT JOIN Feedback fb ON fb.RequestID = r.RequestID
        WHERE r.UserID = %s
    """
    params = [user_id]
    if status and status.lower() != "all":
        query += " AND r.Status = %s"
        params.append(status)

    query += " ORDER BY r.RequestDate DESC"
    rows = query_db(query, tuple(params))
    return jsonify([normalize_row(r) for r in rows])

@app.route("/api/portal/requests/<int:req_id>", methods=["GET"])
@role_required("student_staff")
def api_portal_get_request_details(req_id):
    """
    Object-level check: Requesters access ONLY their own requests.
    Reject anything else with 403.
    """
    user_id = session["user_id"]
    req_item = query_db("""
        SELECT r.RequestID, r.UserID, r.FacilityID, r.CategoryID, r.PriorityID,
               r.Description, r.Status, r.RequestDate,
               u.Name AS RequesterName, u.Email AS RequesterEmail, u.Phone AS RequesterPhone,
               b.BuildingName, b.Address AS BuildingAddress,
               f.RoomNo, f.Floor, f.Type AS FacilityType,
               c.CategoryName, c.Description AS CategoryDescription,
               p.Label AS PriorityLabel, p.SLAHours,
               DATE_ADD(r.RequestDate, INTERVAL p.SLAHours HOUR) AS SLADueDate,
               fb.Rating, fb.Comments AS FeedbackComments, fb.FeedbackDate
        FROM Requests r
        JOIN Users u ON r.UserID = u.UserID
        JOIN Facilities f ON r.FacilityID = f.FacilityID
        JOIN Buildings b ON f.BuildingID = b.BuildingID
        JOIN Categories c ON r.CategoryID = c.CategoryID
        JOIN Priorities p ON r.PriorityID = p.PriorityID
        LEFT JOIN Feedback fb ON fb.RequestID = r.RequestID
        WHERE r.RequestID = %s
    """, (req_id,), fetchone=True)

    if not req_item:
        return jsonify({"error": "Request not found"}), 404

    # OBJECT-LEVEL SECURITY CHECK
    if req_item["UserID"] != user_id:
        log_audit("UNAUTHORIZED_ACCESS_ATTEMPT", f"Requester UserID {user_id} attempted viewing RequestID {req_id} owned by UserID {req_item['UserID']}")
        return jsonify({"error": "Forbidden: You are only authorized to access your own requests."}), 403

    # Fetch status history
    history = query_db("""
        SELECT HistID, RequestID, OldStatus, NewStatus, ChangedOn
        FROM StatusHistory
        WHERE RequestID = %s
        ORDER BY HistID ASC
    """, (req_id,))

    norm = normalize_row(req_item)
    norm["status_history"] = [normalize_row(h) for h in history]
    return jsonify(norm)

@app.route("/api/portal/requests", methods=["POST"])
@role_required("student_staff")
def api_portal_create_request():
    """Creates a new maintenance request submitted by current student/staff user."""
    user_id = session["user_id"]
    data = request.get_json() or {}

    facility_id = data.get("facility_id") or data.get("FacilityID")
    category_id = data.get("category_id") or data.get("CategoryID")
    priority_id = data.get("priority_id") or data.get("PriorityID")
    description = (data.get("description") or "").strip()

    # Resolve category if string
    if isinstance(category_id, str) and not category_id.isdigit():
        c_row = query_db("SELECT CategoryID FROM Categories WHERE CategoryName = %s", (category_id,), fetchone=True)
        category_id = c_row["CategoryID"] if c_row else 1
    elif category_id:
        category_id = int(category_id)

    # Resolve priority if string
    if isinstance(priority_id, str) and not priority_id.isdigit():
        p_row = query_db("SELECT PriorityID FROM Priorities WHERE Label = %s", (priority_id,), fetchone=True)
        priority_id = p_row["PriorityID"] if p_row else 2
    elif priority_id:
        priority_id = int(priority_id)

    # Resolve facility from building_id + room_no if facility_id missing
    building_id = data.get("building_id") or data.get("BuildingID")
    room_no = (data.get("room_no") or data.get("room") or "General").strip()

    if not facility_id and building_id:
        fac = query_db(
            "SELECT FacilityID FROM Facilities WHERE BuildingID = %s AND RoomNo = %s",
            (building_id, room_no), fetchone=True
        )
        if fac:
            facility_id = fac["FacilityID"]
        else:
            facility_id = query_db(
                "INSERT INTO Facilities (BuildingID, RoomNo, Floor, Type) VALUES (%s, %s, %s, %s)",
                (building_id, room_no, "Ground Floor", "General"), commit=True
            )

    if not all([facility_id, category_id, priority_id, description]):
        return jsonify({"error": "Facility, Category, Priority, and Description are required"}), 400

    now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    req_id = query_db(
        "INSERT INTO Requests (UserID, FacilityID, CategoryID, PriorityID, Description, Status, RequestDate) VALUES (%s, %s, %s, %s, %s, %s, %s)",
        (user_id, facility_id, category_id, priority_id, description, "Open", now_str),
        commit=True
    )

    # Initial status in StatusHistory is populated automatically by MySQL trigger trg_requests_insert_history
    log_audit("REQUEST_CREATED", f"Maintenance request #{req_id} created by user #{user_id}", user_id=user_id)


    return jsonify({
        "message": "Maintenance request submitted successfully",
        "request_id": req_id,
        "ticket_number": f"REQ-2026-{req_id:03d}"
    }), 201

@app.route("/api/portal/requests/<int:req_id>/feedback", methods=["POST"])
@role_required("student_staff")
def api_portal_submit_feedback(req_id):
    """
    Object-level check: Requesters submit feedback ONLY for their own requests.
    Validates status is Resolved or Closed.
    """
    user_id = session["user_id"]
    req_item = query_db("SELECT RequestID, UserID, Status FROM Requests WHERE RequestID = %s", (req_id,), fetchone=True)
    if not req_item:
        return jsonify({"error": "Request not found"}), 404

    # OBJECT-LEVEL SECURITY CHECK
    if req_item["UserID"] != user_id:
        log_audit("UNAUTHORIZED_FEEDBACK_ATTEMPT", f"User #{user_id} attempted rating Request #{req_id} owned by #{req_item['UserID']}")
        return jsonify({"error": "Forbidden: You can only rate your own requests."}), 403

    if req_item["Status"] not in ["Resolved", "Closed"]:
        return jsonify({"error": "Feedback can only be submitted for Resolved or Closed requests."}), 400

    data = request.get_json() or {}
    try:
        rating_val = int(data.get("rating", 0))
    except (ValueError, TypeError):
        return jsonify({"error": "Rating must be an integer between 1 and 5"}), 400

    if rating_val < 1 or rating_val > 5:
        return jsonify({"error": "Rating must be between 1 and 5"}), 400

    comments = (data.get("comments") or data.get("feedback") or "").strip()
    now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    existing = query_db("SELECT FeedbackID FROM Feedback WHERE RequestID = %s", (req_id,), fetchone=True)
    if existing:
        query_db(
            "UPDATE Feedback SET Rating = %s, Comments = %s, FeedbackDate = %s WHERE FeedbackID = %s",
            (rating_val, comments, now_str, existing["FeedbackID"]), commit=True
        )
    else:
        query_db(
            "INSERT INTO Feedback (RequestID, UserID, Rating, Comments, FeedbackDate) VALUES (%s, %s, %s, %s, %s)",
            (req_id, user_id, rating_val, comments, now_str), commit=True
        )

    # Advance status to 'Closed' if currently 'Resolved' (trigger trg_requests_update_history logs to StatusHistory)
    if req_item["Status"] == "Resolved":
        query_db("UPDATE Requests SET Status = 'Closed' WHERE RequestID = %s", (req_id,), commit=True)
        log_audit("STATUS_CHANGED", f"Request #{req_id} transitioned to Closed upon feedback submission", user_id=user_id)

    log_audit("FEEDBACK_SUBMITTED", f"Feedback for request #{req_id}: rating {rating_val}/5", user_id=user_id)

    return jsonify({"message": "Feedback submitted successfully", "status": "Closed"}), 201


# =====================================================================
# Technician Console API (/api/technician/...)
# =====================================================================

def get_current_technician_record():
    """Finds Technicians table row for the logged-in user."""
    user_id = session.get("user_id")
    if not user_id:
        return None
    return query_db("SELECT TechID, UserID, Skill, Available FROM Technicians WHERE UserID = %s", (user_id,), fetchone=True)

@app.route("/api/technician/jobs", methods=["GET"])
@role_required("technician")
def api_technician_get_jobs():
    """
    Object-level check: Technicians access ONLY requests in their own Assignments.
    """
    tech = get_current_technician_record()
    if not tech:
        return jsonify({"error": "No technician profile linked to this user account."}), 403

    status = request.args.get("status")
    query = """
        SELECT r.RequestID, r.UserID, r.FacilityID, r.CategoryID, r.PriorityID,
               r.Description, r.Status, r.RequestDate,
               u.Name AS RequesterName, u.Phone AS RequesterPhone, u.Email AS RequesterEmail,
               b.BuildingName, f.RoomNo, f.Floor,
               c.CategoryName,
               p.Label AS PriorityLabel, p.SLAHours,
               DATE_ADD(r.RequestDate, INTERVAL p.SLAHours HOUR) AS SLADueDate,
               a.AssignID, a.AssignedOn
        FROM Requests r
        JOIN Assignments a ON r.RequestID = a.RequestID
        JOIN Users u ON r.UserID = u.UserID
        JOIN Facilities f ON r.FacilityID = f.FacilityID
        JOIN Buildings b ON f.BuildingID = b.BuildingID
        JOIN Categories c ON r.CategoryID = c.CategoryID
        JOIN Priorities p ON r.PriorityID = p.PriorityID
        WHERE a.TechID = %s
    """
    params = [tech["TechID"]]
    if status and status.lower() != "all":
        query += " AND r.Status = %s"
        params.append(status)

    query += " ORDER BY r.RequestDate DESC"
    jobs = query_db(query, tuple(params))
    return jsonify([normalize_row(j) for j in jobs])

@app.route("/api/technician/jobs/<int:req_id>", methods=["GET"])
@role_required("technician")
def api_technician_get_job_details(req_id):
    """
    Object-level check: Verify request is assigned to current technician.
    Reject anything else with 403.
    """
    tech = get_current_technician_record()
    if not tech:
        return jsonify({"error": "Technician profile not found"}), 403

    # Check assignment
    assignment = query_db(
        "SELECT AssignID FROM Assignments WHERE RequestID = %s AND TechID = %s",
        (req_id, tech["TechID"]), fetchone=True
    )
    if not assignment:
        log_audit("UNAUTHORIZED_TECH_ACCESS", f"Tech #{tech['TechID']} tried accessing unassigned Request #{req_id}")
        return jsonify({"error": "Forbidden: You are not assigned to this maintenance request."}), 403

    req_item = query_db("""
        SELECT r.RequestID, r.UserID, r.FacilityID, r.CategoryID, r.PriorityID,
               r.Description, r.Status, r.RequestDate,
               u.Name AS RequesterName, u.Email AS RequesterEmail, u.Phone AS RequesterPhone,
               b.BuildingName, b.Address AS BuildingAddress,
               f.RoomNo, f.Floor, f.Type AS FacilityType,
               c.CategoryName,
               p.Label AS PriorityLabel, p.SLAHours,
               DATE_ADD(r.RequestDate, INTERVAL p.SLAHours HOUR) AS SLADueDate
        FROM Requests r
        JOIN Users u ON r.UserID = u.UserID
        JOIN Facilities f ON r.FacilityID = f.FacilityID
        JOIN Buildings b ON f.BuildingID = b.BuildingID
        JOIN Categories c ON r.CategoryID = c.CategoryID
        JOIN Priorities p ON r.PriorityID = p.PriorityID
        WHERE r.RequestID = %s
    """, (req_id,), fetchone=True)

    # Work logs and materials
    work_logs = query_db("""
        SELECT wl.LogID, wl.AssignID, wl.WorkDate, wl.WorkDescription,
               u.Name AS TechnicianName
        FROM WorkLogs wl
        JOIN Assignments a ON wl.AssignID = a.AssignID
        JOIN Technicians t ON a.TechID = t.TechID
        JOIN Users u ON t.UserID = u.UserID
        WHERE a.RequestID = %s
        ORDER BY wl.WorkDate DESC
    """, (req_id,))

    for log in work_logs:
        mats = query_db("SELECT MatID, MaterialName, Qty, Cost, (Qty * Cost) AS TotalCost FROM Materials WHERE LogID = %s", (log["LogID"],))
        log["materials"] = [normalize_row(m) for m in mats]
        log["total_cost"] = sum(float(m["TotalCost"]) for m in mats)

    norm = normalize_row(req_item)
    norm["work_logs"] = [normalize_row(w) for w in work_logs]
    return jsonify(norm)

@app.route("/api/technician/jobs/<int:req_id>/work-logs", methods=["POST"])
@role_required("technician")
def api_technician_add_work_log(req_id):
    """
    Object-level check: Verify technician assignment.
    Adds work log + materials (cost in ₹).
    If status is 'Assigned', auto-advances status to 'In Progress'.
    """
    tech = get_current_technician_record()
    if not tech:
        return jsonify({"error": "Technician profile not found"}), 403

    assignment = query_db(
        "SELECT AssignID FROM Assignments WHERE RequestID = %s AND TechID = %s ORDER BY AssignID DESC LIMIT 1",
        (req_id, tech["TechID"]), fetchone=True
    )
    if not assignment:
        return jsonify({"error": "Forbidden: You are not assigned to this maintenance request."}), 403

    req_item = query_db("SELECT RequestID, Status FROM Requests WHERE RequestID = %s", (req_id,), fetchone=True)
    if not req_item:
        return jsonify({"error": "Request not found"}), 404

    if req_item["Status"] not in ["Assigned", "In Progress"]:
        return jsonify({"error": f"Cannot add work log: request status is '{req_item['Status']}'."}), 400

    data = request.get_json() or {}
    work_description = (data.get("work_description") or "").strip()
    materials = data.get("materials") or []

    if not work_description:
        return jsonify({"error": "Work description is required"}), 400

    now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    log_id = query_db(
        "INSERT INTO WorkLogs (AssignID, WorkDate, WorkDescription) VALUES (%s, %s, %s)",
        (assignment["AssignID"], now_str, work_description),
        commit=True
    )

    for mat in materials:
        m_name = (mat.get("material_name") or mat.get("MaterialName") or "").strip()
        try:
            m_qty = max(1, int(mat.get("qty") or mat.get("Qty") or 1))
        except (ValueError, TypeError):
            m_qty = 1
        try:
            m_cost = max(0.0, float(mat.get("cost") or mat.get("Cost") or 0.0))
        except (ValueError, TypeError):
            m_cost = 0.0
        if m_name:
            query_db(
                "INSERT INTO Materials (LogID, MaterialName, Qty, Cost) VALUES (%s, %s, %s, %s)",
                (log_id, m_name, m_qty, m_cost),
                commit=True
            )

    # Auto-advance Assigned -> In Progress (trigger trg_requests_update_history logs to StatusHistory)
    if req_item["Status"] == "Assigned":
        query_db("UPDATE Requests SET Status = 'In Progress' WHERE RequestID = %s", (req_id,), commit=True)
        log_audit("STATUS_CHANGED", f"Request #{req_id} transitioned to In Progress via WorkLog")

    log_audit("WORK_LOG_ADDED", f"Tech #{tech['TechID']} added work log #{log_id} to Request #{req_id}")

    return jsonify({"message": "Work log and materials recorded successfully", "log_id": log_id, "status": "In Progress"}), 201

@app.route("/api/technician/jobs/<int:req_id>/resolve", methods=["POST"])
@role_required("technician")
def api_technician_resolve_job(req_id):
    """
    Object-level check: Verify technician assignment.
    Transitions status forward from 'In Progress' to 'Resolved'.
    """
    tech = get_current_technician_record()
    if not tech:
        return jsonify({"error": "Technician profile not found"}), 403

    assignment = query_db(
        "SELECT AssignID FROM Assignments WHERE RequestID = %s AND TechID = %s",
        (req_id, tech["TechID"]), fetchone=True
    )
    if not assignment:
        return jsonify({"error": "Forbidden: You are not assigned to this maintenance request."}), 403

    req_item = query_db("SELECT RequestID, Status FROM Requests WHERE RequestID = %s", (req_id,), fetchone=True)
    if not req_item:
        return jsonify({"error": "Request not found"}), 404

    if req_item["Status"] != "In Progress":
        return jsonify({
            "error": f"Cannot resolve: request status is '{req_item['Status']}'. Status can only transition to Resolved from 'In Progress'."
        }), 400

    now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    query_db("UPDATE Requests SET Status = 'Resolved' WHERE RequestID = %s", (req_id,), commit=True)
    log_audit("STATUS_CHANGED", f"Tech #{tech['TechID']} marked Request #{req_id} as Resolved")

    return jsonify({"message": "Maintenance request marked as Resolved", "status": "Resolved"})


# =====================================================================
# Facility Admin Console API (/api/admin/...)
# =====================================================================

@app.route("/api/admin/requests", methods=["GET"])
@role_required("facility_admin")
def api_admin_get_requests():
    """All requests across campus with comprehensive filters."""
    status = request.args.get("status")
    category_id = request.args.get("category_id")
    priority_id = request.args.get("priority_id")
    building_id = request.args.get("building_id")
    search = request.args.get("search")

    query = """
        SELECT r.RequestID, r.UserID, r.FacilityID, r.CategoryID, r.PriorityID,
               r.Description, r.Status, r.RequestDate,
               u.Name AS RequesterName, u.Email AS RequesterEmail, u.Phone AS RequesterPhone, u.Dept AS RequesterDept,
               b.BuildingID, b.BuildingName, f.RoomNo, f.Floor,
               c.CategoryName,
               p.Label AS PriorityLabel, p.SLAHours,
               DATE_ADD(r.RequestDate, INTERVAL p.SLAHours HOUR) AS SLADueDate,
               fb.Rating, fb.Comments AS FeedbackComments,
               (SELECT GROUP_CONCAT(u_tech.Name SEPARATOR ', ')
                FROM Assignments a
                JOIN Technicians t ON a.TechID = t.TechID
                JOIN Users u_tech ON t.UserID = u_tech.UserID
                WHERE a.RequestID = r.RequestID) AS AssignedTechnicians,
               (SELECT GROUP_CONCAT(a.TechID SEPARATOR ', ')
                FROM Assignments a
                WHERE a.RequestID = r.RequestID) AS AssignedTechIDs
        FROM Requests r
        JOIN Users u ON r.UserID = u.UserID
        JOIN Facilities f ON r.FacilityID = f.FacilityID
        JOIN Buildings b ON f.BuildingID = b.BuildingID
        JOIN Categories c ON r.CategoryID = c.CategoryID
        JOIN Priorities p ON r.PriorityID = p.PriorityID
        LEFT JOIN Feedback fb ON fb.RequestID = r.RequestID
        WHERE 1=1
    """
    params = []
    if status and status.lower() != "all":
        query += " AND r.Status = %s"
        params.append(status)
    if category_id:
        query += " AND r.CategoryID = %s"
        params.append(category_id)
    if priority_id and priority_id.lower() != "all":
        query += " AND r.PriorityID = %s"
        params.append(priority_id)
    if building_id:
        query += " AND b.BuildingID = %s"
        params.append(building_id)
    if search:
        s_like = f"%{search.strip()}%"
        query += " AND (r.Description LIKE %s OR f.RoomNo LIKE %s OR b.BuildingName LIKE %s OR u.Name LIKE %s)"
        params.extend([s_like, s_like, s_like, s_like])

    query += " ORDER BY r.RequestDate DESC"
    requests_list = query_db(query, tuple(params))
    return jsonify([normalize_row(r) for r in requests_list])

@app.route("/api/admin/requests/<int:req_id>", methods=["GET"])
@role_required("facility_admin")
def api_admin_get_request_details(req_id):
    """Full request details for admin console."""
    req_item = query_db("""
        SELECT r.RequestID, r.UserID, r.FacilityID, r.CategoryID, r.PriorityID,
               r.Description, r.Status, r.RequestDate,
               u.Name AS RequesterName, u.Email AS RequesterEmail, u.Phone AS RequesterPhone, u.Dept AS RequesterDept,
               b.BuildingID, b.BuildingName, b.Address AS BuildingAddress,
               f.RoomNo, f.Floor, f.Type AS FacilityType,
               c.CategoryName, c.Description AS CategoryDescription,
               p.Label AS PriorityLabel, p.SLAHours,
               DATE_ADD(r.RequestDate, INTERVAL p.SLAHours HOUR) AS SLADueDate,
               fb.Rating, fb.Comments AS FeedbackComments, fb.FeedbackDate
        FROM Requests r
        JOIN Users u ON r.UserID = u.UserID
        JOIN Facilities f ON r.FacilityID = f.FacilityID
        JOIN Buildings b ON f.BuildingID = b.BuildingID
        JOIN Categories c ON r.CategoryID = c.CategoryID
        JOIN Priorities p ON r.PriorityID = p.PriorityID
        LEFT JOIN Feedback fb ON fb.RequestID = r.RequestID
        WHERE r.RequestID = %s
    """, (req_id,), fetchone=True)

    if not req_item:
        return jsonify({"error": "Request not found"}), 404

    assignments = query_db("""
        SELECT a.AssignID, a.RequestID, a.TechID, a.AssignedOn,
               u.Name AS TechnicianName, u.Email AS TechnicianEmail, u.Phone AS TechnicianPhone,
               t.Skill
        FROM Assignments a
        JOIN Technicians t ON a.TechID = t.TechID
        JOIN Users u ON t.UserID = u.UserID
        WHERE a.RequestID = %s
        ORDER BY a.AssignedOn ASC
    """, (req_id,))

    work_logs = query_db("""
        SELECT wl.LogID, wl.AssignID, wl.WorkDate, wl.WorkDescription,
               u.Name AS TechnicianName, t.Skill
        FROM WorkLogs wl
        JOIN Assignments a ON wl.AssignID = a.AssignID
        JOIN Technicians t ON a.TechID = t.TechID
        JOIN Users u ON t.UserID = u.UserID
        WHERE a.RequestID = %s
        ORDER BY wl.WorkDate DESC
    """, (req_id,))

    for log in work_logs:
        materials = query_db("SELECT MatID, MaterialName, Qty, Cost, (Qty * Cost) AS TotalCost FROM Materials WHERE LogID = %s", (log["LogID"],))
        log["materials"] = [normalize_row(m) for m in materials]
        log["total_cost"] = sum(float(m["TotalCost"]) for m in materials)

    history = query_db("""
        SELECT HistID, RequestID, OldStatus, NewStatus, ChangedOn
        FROM StatusHistory
        WHERE RequestID = %s
        ORDER BY HistID ASC
    """, (req_id,))

    norm = normalize_row(req_item)
    norm["assignments"] = [normalize_row(a) for a in assignments]
    norm["work_logs"] = [normalize_row(w) for w in work_logs]
    norm["status_history"] = [normalize_row(h) for h in history]
    return jsonify(norm)

@app.route("/api/admin/requests/<int:req_id>/assign", methods=["POST"])
@role_required("facility_admin")
def api_admin_assign_technician(req_id):
    """
    Facility Admin assigns a technician:
    - Inserts into Assignments
    - Updates Requests Status to 'Assigned' in ONE transaction
    - Trigger writes StatusHistory
    - Writes to AuditLog
    """
    data = request.get_json() or {}
    tech_id = data.get("TechID") or data.get("tech_id") or data.get("technician_id")

    if not tech_id:
        return jsonify({"error": "TechID is required"}), 400

    try:
        tech_id = int(tech_id)
    except (ValueError, TypeError):
        return jsonify({"error": "Invalid TechID format"}), 400

    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT RequestID, Status FROM Requests WHERE RequestID = %s", (req_id,))
            req_item = cur.fetchone()
            if not req_item:
                return jsonify({"error": "Request not found"}), 404

            cur.execute("SELECT TechID, UserID, Skill, Available FROM Technicians WHERE TechID = %s", (tech_id,))
            tech = cur.fetchone()
            if not tech:
                return jsonify({"error": "Technician not found"}), 404

            if req_item["Status"] not in ["Open", "Assigned"]:
                return jsonify({
                    "error": f"Cannot assign technician: request is currently '{req_item['Status']}'. Status can only move forward: Open -> Assigned -> In Progress -> Resolved -> Closed"
                }), 400

            now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            cur.execute(
                "INSERT INTO Assignments (RequestID, TechID, AssignedOn) VALUES (%s, %s, %s)",
                (req_id, tech_id, now_str)
            )
            assign_id = cur.lastrowid

            if req_item["Status"] == "Open":
                cur.execute("UPDATE Requests SET Status = 'Assigned' WHERE RequestID = %s", (req_id,))

        conn.commit()
    except Exception as e:
        conn.rollback()
        return jsonify({"error": f"Failed to assign technician: {str(e)}"}), 500
    finally:
        conn.close()

    log_audit("TECHNICIAN_ASSIGNED", f"Assigned TechID #{tech_id} to Request #{req_id} (Assignment #{assign_id})")

    return jsonify({
        "message": "Technician assigned successfully",
        "assignment_id": assign_id,
        "status": "Assigned"
    })

@app.route("/api/admin/requests/<int:req_id>/status", methods=["PUT"])
@role_required("facility_admin")
def api_admin_update_status(req_id):
    """
    Facility Admin manually updates status.
    Enforces forward-only transitions: Open -> Assigned -> In Progress -> Resolved -> Closed.
    """
    data = request.get_json() or {}
    new_status = data.get("status")
    valid_statuses = ["Open", "Assigned", "In Progress", "Resolved", "Closed"]

    if new_status not in valid_statuses:
        return jsonify({"error": f"Invalid status '{new_status}'. Must be one of {valid_statuses}"}), 400

    req_item = query_db("SELECT RequestID, Status FROM Requests WHERE RequestID = %s", (req_id,), fetchone=True)
    if not req_item:
        return jsonify({"error": "Request not found"}), 404

    current_status = req_item["Status"]
    allowed = VALID_TRANSITIONS.get(current_status, [])
    if new_status not in allowed:
        return jsonify({
            "error": f"Invalid status transition from '{current_status}' to '{new_status}'. Status can only move forward: Open -> Assigned -> In Progress -> Resolved -> Closed",
            "current_status": current_status,
            "attempted_status": new_status,
            "allowed_next_status": allowed
        }), 400

    try:
        query_db("UPDATE Requests SET Status = %s WHERE RequestID = %s", (new_status, req_id), commit=True)
    except Exception as e:
        return jsonify({"error": f"Database validation error: {str(e)}"}), 400

    log_audit("STATUS_CHANGED", f"Admin updated Request #{req_id} status from '{current_status}' to '{new_status}'")

    return jsonify({"message": f"Status updated to {new_status}", "status": new_status})


@app.route("/api/admin/technicians", methods=["GET"])
@role_required("facility_admin")
def api_admin_get_technicians():
    """Lists available technicians with skills and workload."""
    category_id = request.args.get("category_id")
    technicians = []

    if category_id:
        query = """
            SELECT t.TechID, t.UserID, t.Skill, t.Available,
                   u.Name, u.Email, u.Phone, u.Dept,
                   (SELECT COUNT(*) FROM Assignments a 
                    JOIN Requests r ON a.RequestID = r.RequestID 
                    WHERE a.TechID = t.TechID AND r.Status IN ('Assigned', 'In Progress')) AS active_jobs
            FROM Technicians t
            JOIN Users u ON t.UserID = u.UserID
            JOIN Categories c ON c.CategoryID = %s
            WHERE LOWER(TRIM(t.Skill)) = LOWER(TRIM(c.CategoryName)) AND t.Available = TRUE
            ORDER BY active_jobs ASC, u.Name ASC
        """
        technicians = query_db(query, (category_id,))

    if not technicians:
        query_all = """
            SELECT t.TechID, t.UserID, t.Skill, t.Available,
                   u.Name, u.Email, u.Phone, u.Dept,
                   (SELECT COUNT(*) FROM Assignments a 
                    JOIN Requests r ON a.RequestID = r.RequestID 
                    WHERE a.TechID = t.TechID AND r.Status IN ('Assigned', 'In Progress')) AS active_jobs
            FROM Technicians t
            JOIN Users u ON t.UserID = u.UserID
            WHERE t.Available = TRUE
            ORDER BY active_jobs ASC, u.Name ASC
        """
        technicians = query_db(query_all)

    return jsonify([normalize_row(t) for t in technicians])

@app.route("/api/admin/users", methods=["GET"])
@role_required("facility_admin")
def api_admin_get_users():
    """Admin Manage Users page: lists all registered accounts."""
    query = """
        SELECT u.UserID, u.Name, u.Email, u.Phone, u.Role, u.Dept,
               t.TechID, t.Skill, t.Available
        FROM Users u
        LEFT JOIN Technicians t ON u.UserID = t.UserID
        ORDER BY u.Role ASC, u.Name ASC
    """
    users = query_db(query)
    return jsonify([normalize_row(u) for u in users])

@app.route("/api/admin/users", methods=["POST"])
@role_required("facility_admin")
def api_admin_create_user():
    """
    Facility Admin creates Technician/Admin/Management/Student accounts.
    If technician, creates Technicians table record with Skill.
    Writes to AuditLog.
    """
    data = request.get_json() or {}
    name = (data.get("name") or "").strip()
    email = (data.get("email") or "").strip().lower()
    phone = (data.get("phone") or "").strip()
    role = (data.get("role") or "").strip()
    dept = (data.get("dept") or "Facilities").strip()
    password = data.get("password") or ""
    skill = (data.get("skill") or "").strip()

    allowed_roles = ["student_staff", "technician", "facility_admin", "management"]
    if role not in allowed_roles:
        return jsonify({"error": f"Invalid role '{role}'. Must be one of {allowed_roles}"}), 400

    if not name or not email or not password:
        return jsonify({"error": "Name, email, and password are required"}), 400

    if not re.match(r"^[^@]+@[^@]+\.[^@]+$", email):
        return jsonify({"error": "Invalid email address format"}), 400

    existing = query_db("SELECT UserID FROM Users WHERE LOWER(Email) = %s", (email,), fetchone=True)
    if existing:
        return jsonify({"error": "An account with this email already exists"}), 409

    pwd_hash = generate_password_hash(password)
    user_id = query_db(
        "INSERT INTO Users (Name, Email, Phone, PasswordHash, Role, Dept) VALUES (%s, %s, %s, %s, %s, %s)",
        (name, email, phone, pwd_hash, role, dept),
        commit=True
    )

    tech_id = None
    if role == "technician":
        tech_skill = skill if skill else "General Maintenance"
        tech_id = query_db(
            "INSERT INTO Technicians (UserID, Skill, Available) VALUES (%s, %s, %s)",
            (user_id, tech_skill, True),
            commit=True
        )

    log_audit("USER_CREATED", f"Admin created user #{user_id}: {name} ({role}), Skill={skill or 'N/A'}")

    return jsonify({
        "message": f"User '{name}' with role '{role}' created successfully",
        "user_id": user_id,
        "tech_id": tech_id
    }), 201

@app.route("/api/admin/audit-logs", methods=["GET"])
@role_required("facility_admin")
def api_admin_get_audit_logs():
    """Returns recent AuditLog entries for Admin console."""
    query = """
        SELECT al.LogID, al.UserID, al.Action, al.Details, al.IP, al.Timestamp,
               u.Name AS UserName, u.Email AS UserEmail, u.Role AS UserRole
        FROM AuditLog al
        LEFT JOIN Users u ON al.UserID = u.UserID
        ORDER BY al.LogID DESC
        LIMIT 100
    """
    logs = query_db(query)
    return jsonify([normalize_row(l) for l in logs])

# =====================================================================
# Executive Management Console API (/api/management/...)
# STRICTLY READ-ONLY!
# =====================================================================

@app.route("/api/management/dashboard", methods=["GET"])
@role_required("management")
def api_management_dashboard():
    """
    Executive Management Dashboard Analytics:
    - Total, Open, Resolved counts
    - SLA Compliance % (resolutions within Priority SLAHours)
    - Average Rating from Feedback
    - Total Materials Spend in ₹ (INR)
    - Requests by Category with spend
    - Requests by Priority
    - Recent StatusHistory timeline
    """
    # 1. Counts
    counts = query_db("""
        SELECT 
            COUNT(*) AS total,
            SUM(CASE WHEN Status IN ('Open', 'Assigned', 'In Progress') THEN 1 ELSE 0 END) AS open_count,
            SUM(CASE WHEN Status IN ('Resolved', 'Closed') THEN 1 ELSE 0 END) AS resolved_count,
            SUM(CASE WHEN Status = 'Closed' THEN 1 ELSE 0 END) AS closed_count
        FROM Requests
    """, fetchone=True)

    total_req = counts["total"] if counts and counts["total"] else 0
    open_req = counts["open_count"] if counts and counts["open_count"] else 0
    resolved_req = counts["resolved_count"] if counts and counts["resolved_count"] else 0

    # 2. SLA Compliance Rate
    sla_data = query_db("""
        SELECT 
            COUNT(DISTINCT r.RequestID) AS total_resolved,
            SUM(CASE 
                WHEN sh.ChangedOn <= DATE_ADD(r.RequestDate, INTERVAL p.SLAHours HOUR) THEN 1 
                ELSE 0 
            END) AS resolved_within_sla
        FROM Requests r
        JOIN Priorities p ON r.PriorityID = p.PriorityID
        JOIN StatusHistory sh ON r.RequestID = sh.RequestID AND sh.NewStatus = 'Resolved'
        WHERE r.Status IN ('Resolved', 'Closed')
    """, fetchone=True)

    if sla_data and sla_data["total_resolved"] and sla_data["total_resolved"] > 0:
        sla_pct = round((sla_data["resolved_within_sla"] / sla_data["total_resolved"]) * 100, 1)
    else:
        sla_pct = 100.0 if resolved_req > 0 else 0.0

    # 3. Average Rating
    rating_data = query_db("SELECT AVG(Rating) AS avg_rating, COUNT(*) AS count_ratings FROM Feedback", fetchone=True)
    avg_rating = round(rating_data["avg_rating"], 2) if rating_data and rating_data["avg_rating"] else 0.0
    ratings_count = rating_data["count_ratings"] if rating_data else 0

    # 4. Total Materials Cost in ₹
    cost_data = query_db("SELECT SUM(Cost * Qty) AS total_cost FROM Materials", fetchone=True)
    total_cost = round(cost_data["total_cost"], 2) if cost_data and cost_data["total_cost"] else 0.0

    # 5. Requests by Category & Spend
    by_category = query_db("""
        SELECT c.CategoryID, c.CategoryName,
               COUNT(DISTINCT r.RequestID) AS count,
               COALESCE(SUM(m.Cost * m.Qty), 0) AS total_category_cost
        FROM Categories c
        LEFT JOIN Requests r ON r.CategoryID = c.CategoryID
        LEFT JOIN Assignments a ON a.RequestID = r.RequestID
        LEFT JOIN WorkLogs w ON w.AssignID = a.AssignID
        LEFT JOIN Materials m ON m.LogID = w.LogID
        GROUP BY c.CategoryID, c.CategoryName
        ORDER BY count DESC, c.CategoryName ASC
    """)
    for cat in by_category:
        cat["total_category_cost"] = float(cat.get("total_category_cost") or 0.0)

    # 6. Requests by Priority
    by_priority = query_db("""
        SELECT p.Label, COUNT(r.RequestID) AS count
        FROM Priorities p
        LEFT JOIN Requests r ON r.PriorityID = p.PriorityID
        GROUP BY p.PriorityID, p.Label
        ORDER BY p.SLAHours ASC
    """)

    # 7. Recent StatusHistory Timeline
    timeline = query_db("""
        SELECT sh.HistID, sh.RequestID, sh.OldStatus, sh.NewStatus, sh.ChangedOn,
               c.CategoryName, b.BuildingName, f.RoomNo
        FROM StatusHistory sh
        JOIN Requests r ON sh.RequestID = r.RequestID
        JOIN Categories c ON r.CategoryID = c.CategoryID
        JOIN Facilities f ON r.FacilityID = f.FacilityID
        JOIN Buildings b ON f.BuildingID = b.BuildingID
        ORDER BY sh.HistID DESC
        LIMIT 15
    """)

    return jsonify({
        "total_requests": total_req,
        "open_requests": open_req,
        "resolved_requests": resolved_req,
        "sla_compliance_rate": sla_pct,
        "average_rating": avg_rating,
        "ratings_count": ratings_count,
        "total_materials_cost": total_cost,
        "requests_by_category": by_category,
        "requests_by_priority": by_priority,
        "recent_timeline": timeline
    })

@app.route("/api/management/audit-logs", methods=["GET"])
@role_required("management")
def api_management_get_audit_logs():
    """Returns AuditLog for Executive Management inspection."""
    query = """
        SELECT al.LogID, al.UserID, al.Action, al.Details, al.IP, al.Timestamp,
               u.Name AS UserName, u.Email AS UserEmail, u.Role AS UserRole
        FROM AuditLog al
        LEFT JOIN Users u ON al.UserID = u.UserID
        ORDER BY al.LogID DESC
        LIMIT 100
    """
    logs = query_db(query)
    return jsonify([normalize_row(l) for l in logs])

# =====================================================================
# System Status & Health Endpoint
# =====================================================================

@app.route("/api/status", methods=["GET"])
def api_status():
    status = get_engine_status()
    status["server_time"] = datetime.datetime.now().strftime("%d-%m-%Y %I:%M:%S %p IST")
    status["polling_interval_ms"] = 5000
    return jsonify(status)

# =====================================================================
# Error Handlers
# =====================================================================

@app.errorhandler(403)
def forbidden_error(e):
    if request.path.startswith("/api/"):
        return jsonify({"error": "Forbidden: Access denied."}), 403
    return render_template("403.html"), 403

@app.errorhandler(404)
def not_found_error(e):
    if request.path.startswith("/api/") and not request.path.startswith(("/api/index", "/api/index.py")):
        return jsonify({"error": "Endpoint not found"}), 404
    user = get_current_user_obj()
    return render_template("landing.html", user=user), 404

if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    debug = os.getenv("FLASK_DEBUG", "1") == "1"
    print(f"[*] Starting Campus FMS on http://127.0.0.1:{port}")
    app.run(host="0.0.0.0", port=port, debug=debug)
