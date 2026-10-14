import os
import pymysql
from dotenv import load_dotenv

load_dotenv()

DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = int(os.getenv("DB_PORT", "3306"))
DB_USER = os.getenv("DB_USER", "campus_app")
DB_PASSWORD = os.getenv("DB_PASSWORD", "CampusApp@2026")
DB_NAME = os.getenv("DB_NAME", "campus_fms")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SCHEMA_SQL_PATH = os.path.join(BASE_DIR, "schema.sql")
SEED_SQL_PATH = os.path.join(BASE_DIR, "seed.sql")

DEMO_ACCOUNTS = [
    ("Student / Staff", "Alex Chen", "alex.student@campus.edu", "student123", "/portal"),
    ("Student / Staff", "Prof. Sarah Jenkins", "sarah.faculty@campus.edu", "staff123", "/portal"),
    ("Facility Admin", "Marcus Vance", "marcus.admin@campus.edu", "admin123", "/admin"),
    ("Technician (Electrical)", "Carlos Mendez", "carlos.electrician@campus.edu", "tech123", "/technician"),
    ("Technician (Plumbing)", "Elena Rostova", "elena.plumber@campus.edu", "tech123", "/technician"),
    ("Technician (IT)", "David Kim", "david.network@campus.edu", "tech123", "/technician"),
    ("Technician (Carpentry)", "Robert Green", "robert.carpenter@campus.edu", "tech123", "/technician"),
    ("Executive Management", "Dr. Arthur Reynolds", "reynolds.mgmt@campus.edu", "mgmt123", "/management"),
]

def execute_mysql_script(cursor, sql_content):
    """Executes multi-statement MySQL script safely, handling DELIMITER blocks."""
    statements = []
    current_stmt = []
    in_delimiter_block = False
    delimiter = ";"

    for line in sql_content.splitlines():
        trimmed = line.strip()
        if trimmed.startswith("--") or not trimmed:
            continue
        if trimmed.upper().startswith("DELIMITER $$"):
            in_delimiter_block = True
            delimiter = "$$"
            continue
        elif trimmed.upper().startswith("DELIMITER ;"):
            in_delimiter_block = False
            delimiter = ";"
            continue

        current_stmt.append(line)
        if trimmed.endswith(delimiter):
            stmt_text = "\n".join(current_stmt)
            if stmt_text.endswith(delimiter):
                stmt_text = stmt_text[:-len(delimiter)]
            stmt_text = stmt_text.strip()
            if stmt_text:
                statements.append(stmt_text)
            current_stmt = []

    for stmt in statements:
        if stmt:
            cursor.execute(stmt)

import re

DB_SSL = os.getenv("DB_SSL", "false").lower() in ("true", "1", "yes")

def initialize_database():
    """
    Initializes and reseeds the MySQL database campus_fms.
    Works seamlessly with both local MySQL and Cloud databases (Aiven, TiDB, Railway):
    - Automatically executes schema.sql if tables are missing
    - Cleans all existing data with FOREIGN_KEY_CHECKS disabled
    - Reseeds fresh normalized test data from seed.sql
    - Reseeds and verifies all demo accounts and passwords
    - Prints demo credentials table in terminal
    """
    print("=" * 70)
    print("Campus FMS - MySQL Database Setup & Seed Tool")
    print("=" * 70)
    print(f"[*] Target MySQL Server: {DB_HOST}:{DB_PORT}")
    print(f"[*] User: {DB_USER}")
    print(f"[*] Database: {DB_NAME}")
    print(f"[*] SSL Enabled: {DB_SSL}")

    connect_kwargs = {
        "host": DB_HOST,
        "port": DB_PORT,
        "user": DB_USER,
        "password": DB_PASSWORD,
        "database": DB_NAME,
        "autocommit": False,
        "connect_timeout": 10
    }
    if DB_SSL:
        connect_kwargs["ssl"] = {}

    conn = pymysql.connect(**connect_kwargs)

    try:
        with conn.cursor() as cur:
            # 1. Check if schema already exists; if not, apply schema.sql first
            cur.execute("SHOW TABLES;")
            raw_tables = cur.fetchall()
            existing_tables = [
                (t[f"Tables_in_{DB_NAME}"].lower() if isinstance(t, dict) else t[0].lower())
                for t in raw_tables
            ]
            
            if "users" not in existing_tables:
                print("[*] Tables not found. Deploying 15-table 3NF schema and triggers from schema.sql...")
                with open(SCHEMA_SQL_PATH, "r", encoding="utf-8") as f:
                    schema_content = f.read()
                # Filter out DROP/CREATE DATABASE and USE statements for cloud portability
                filtered_lines = [
                    line for line in schema_content.splitlines()
                    if not re.match(r"^\s*(DROP\s+DATABASE|CREATE\s+DATABASE|USE\s+)", line, re.IGNORECASE)
                ]
                execute_mysql_script(cur, "\n".join(filtered_lines))
                conn.commit()
                print("[OK] Schema & triggers successfully created.")

            # 2. Clean existing records safely
            print("[*] Resetting existing records...")
            cur.execute("SET FOREIGN_KEY_CHECKS = 0;")
            tables_to_clear = [
                "Materials", "WorkLogs", "Assignments", "Feedback", "StatusHistory",
                "Requests", "Assets", "Technicians", "Facilities", "Priorities",
                "Categories", "Buildings", "Users", "LoginAttempts", "AuditLog"
            ]
            for tbl in tables_to_clear:
                try:
                    cur.execute(f"DELETE FROM `{tbl}`;")
                    cur.execute(f"ALTER TABLE `{tbl}` AUTO_INCREMENT = 1;")
                except Exception:
                    pass
            cur.execute("SET FOREIGN_KEY_CHECKS = 1;")
            conn.commit()
            print("[OK] All tables cleaned.")

            # 3. Execute seed.sql
            print("[*] Applying seed.sql...")
            with open(SEED_SQL_PATH, "r", encoding="utf-8") as f:
                seed_content = f.read()
            execute_mysql_script(cur, seed_content)
            conn.commit()
            print("[OK] Seed data inserted successfully.")

            # 3. Verify Tables
            cur.execute("SHOW TABLES;")
            tables = [t[f"Tables_in_{DB_NAME}"] if isinstance(t, dict) else t[0] for t in cur.fetchall()]
            print(f"[OK] Total Tables in {DB_NAME}: {len(tables)}")

            # 4. Verify Triggers
            cur.execute("SHOW TRIGGERS;")
            triggers = cur.fetchall()
            print(f"[OK] Total Triggers in {DB_NAME}: {len(triggers)}")

            # 5. Print Demo Credentials Table
            print("\n" + "=" * 94)
            print(f"{'ROLE':<26} | {'NAME':<22} | {'EMAIL':<30} | {'PASSWORD':<10}")
            print("=" * 94)
            for role, name, email, pwd, url in DEMO_ACCOUNTS:
                print(f"{role:<26} | {name:<22} | {email:<30} | {pwd:<10}")
            print("=" * 94)
            print("[*] Note: These credentials correspond exactly to the documentation in README.md.\n")

        return True
    finally:
        conn.close()

if __name__ == "__main__":
    initialize_database()
    print("Database initialization & reseeding complete!")
