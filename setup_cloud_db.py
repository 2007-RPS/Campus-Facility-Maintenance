import os
import re
import time
import pymysql
from dotenv import load_dotenv

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SCHEMA_SQL_PATH = os.path.join(BASE_DIR, "schema.sql")
SEED_SQL_PATH = os.path.join(BASE_DIR, "seed.sql")

# Credentials for Railway Cloud MySQL
DB_HOST = os.getenv("DB_HOST", "roundhouse.proxy.rlwy.net")
DB_PORT = int(os.getenv("DB_PORT", 17985))
DB_USER = os.getenv("DB_USER", "root")
DB_PASSWORD = os.getenv("DB_PASSWORD", "XQByadBEwryHlZzctAdgwnOmHfUETYBo")
DB_NAME = os.getenv("DB_NAME", "railway")

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

DB_SSL = os.getenv("DB_SSL", "false").lower() in ("true", "1", "yes")

def setup_cloud():
    print("=" * 70, flush=True)
    print("[*] Initializing Cloud MySQL Database for Campus FMS", flush=True)
    print("=" * 70, flush=True)
    print(f"[*] Cloud Host: {DB_HOST}:{DB_PORT}", flush=True)
    print(f"[*] User:       {DB_USER}", flush=True)
    print(f"[*] Database:   {DB_NAME}", flush=True)
    print(f"[*] SSL:        {DB_SSL}", flush=True)

    connect_kwargs = {
        "host": DB_HOST,
        "port": DB_PORT,
        "user": DB_USER,
        "password": DB_PASSWORD,
        "database": DB_NAME,
        "autocommit": False,
        "connect_timeout": 15
    }
    if DB_SSL:
        connect_kwargs["ssl"] = {}

    try:
        conn = pymysql.connect(**connect_kwargs)
    except Exception as e:
        print(f"\n[FAIL] Connection failed: {e}")
        print("\n[*] Tip: If Aiven is still showing 'REBUILDING' or 'STARTING', please wait 1-2 minutes until it turns green ('RUNNING'), then re-run this script!")
        return False

    try:
        with conn.cursor() as cur:
            # 1. Inspect existing tables
            cur.execute("SHOW TABLES;")
            raw_tables = cur.fetchall()
            existing_tables = [
                (t[f"Tables_in_{DB_NAME}"].lower() if isinstance(t, dict) else t[0].lower())
                for t in raw_tables
            ]

            # 2. Deploy schema.sql if tables are not yet present
            if "users" not in existing_tables:
                print("\n[*] Deploying 15-Table 3NF schema and triggers from schema.sql...")
                with open(SCHEMA_SQL_PATH, "r", encoding="utf-8") as f:
                    schema_content = f.read()

                # Filter out DROP/CREATE DATABASE and USE for cloud database compatibility
                filtered_lines = [
                    line for line in schema_content.splitlines()
                    if not re.match(r"^\s*(DROP\s+DATABASE|CREATE\s+DATABASE|USE\s+)", line, re.IGNORECASE)
                ]
                execute_mysql_script(cur, "\n".join(filtered_lines))
                conn.commit()
                print("[OK] 15 tables and database triggers created successfully!")

            # 3. Clean and reseed data safely
            print("\n[*] Resetting & seeding fresh demo records...")
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

            # 4. Insert seed data
            with open(SEED_SQL_PATH, "r", encoding="utf-8") as f:
                seed_content = f.read()
            filtered_seed = [
                line for line in seed_content.splitlines()
                if not re.match(r"^\s*USE\s+", line, re.IGNORECASE)
            ]
            execute_mysql_script(cur, "\n".join(filtered_seed))
            conn.commit()
            print("[OK] Sample campus data & accounts seeded successfully!", flush=True)

            # 5. Verify tables & triggers
            cur.execute("SHOW TABLES;")
            total_tables = len(cur.fetchall())
            cur.execute("SHOW TRIGGERS;")
            total_triggers = len(cur.fetchall())

            print("\n" + "=" * 70)
            print(f"[SUCCESS] Cloud Database Ready! Total Tables: {total_tables} | Triggers: {total_triggers}")
            print("=" * 70)
            return True

    finally:
        conn.close()

if __name__ == "__main__":
    setup_cloud()
