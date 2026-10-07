import os
import pymysql
import pymysql.cursors
from dotenv import load_dotenv

# Load environment variables from .env
load_dotenv()

DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = int(os.getenv("DB_PORT", "3306"))
DB_USER = os.getenv("DB_USER", "root")
DB_PASSWORD = os.getenv("DB_PASSWORD", "")
DB_NAME = os.getenv("DB_NAME", "campus_fms")

def get_db_connection():
    """
    Returns an active MySQL database connection.
    Connects strictly to MySQL on localhost using .env credentials.
    Dual-engine fallback has been removed as per Review 1 specifications.
    """
    try:
        conn = pymysql.connect(
            host=DB_HOST,
            port=DB_PORT,
            user=DB_USER,
            password=DB_PASSWORD,
            database=DB_NAME,
            cursorclass=pymysql.cursors.DictCursor,
            autocommit=False,
            connect_timeout=3
        )
        return conn
    except pymysql.err.OperationalError as e:
        # If database campus_fms does not exist yet, create it
        if e.args[0] == 1049:  # Unknown database
            admin_conn = pymysql.connect(
                host=DB_HOST,
                port=DB_PORT,
                user=DB_USER,
                password=DB_PASSWORD,
                cursorclass=pymysql.cursors.DictCursor,
                autocommit=True,
                connect_timeout=3
            )
            with admin_conn.cursor() as cur:
                cur.execute(f"CREATE DATABASE IF NOT EXISTS `{DB_NAME}` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;")
            admin_conn.close()

            # Retry connecting to the created database
            conn = pymysql.connect(
                host=DB_HOST,
                port=DB_PORT,
                user=DB_USER,
                password=DB_PASSWORD,
                database=DB_NAME,
                cursorclass=pymysql.cursors.DictCursor,
                autocommit=False,
                connect_timeout=3
            )
            return conn
        raise

def query_db(query, args=(), fetchone=False, commit=False):
    """
    Executes a parameterized query safely against MySQL.
    Always uses %s placeholders and tuple arguments to prevent SQL injection.
    """
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(query, args)
            if commit:
                conn.commit()
                return cursor.lastrowid
            if fetchone:
                return cursor.fetchone()
            return cursor.fetchall()
    except Exception as err:
        if commit:
            conn.rollback()
        raise err
    finally:
        conn.close()

def get_engine_status():
    """Returns MySQL connection health and metadata."""
    conn = get_db_connection()
    with conn.cursor() as cur:
        cur.execute("SELECT VERSION() AS version;")
        ver = cur.fetchone()
    conn.close()
    return {
        "engine": "mysql",
        "host": DB_HOST,
        "port": DB_PORT,
        "database": DB_NAME,
        "mysql_version": ver["version"] if ver else "unknown"
    }
