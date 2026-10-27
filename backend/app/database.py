"""
database.py - Talks to Microsoft SQL Server.

Every query in the project goes through execute_query(). It always uses
"?" placeholders, so user input is never pasted into SQL text
(this is what makes SQL injection impossible).

Used by: every file in app/routes and app/services.
"""
import logging
import pyodbc

from app import config

log = logging.getLogger("database")


def _connection_string() -> str:
    """Build the connection text from the settings in config.py / .env."""
    parts = [
        f"DRIVER={{{config.DB_DRIVER}}}",
        f"SERVER={config.DB_SERVER}",
        f"DATABASE={config.DB_NAME}",
        "TrustServerCertificate=yes",
    ]
    if config.DB_AUTH == "sql":
        # SQL login (recommended: the limited login created by scripts/setup_db_login.sql)
        parts += [f"UID={config.DB_USER}", f"PWD={config.DB_PASSWORD}"]
    else:
        # Windows login of the person running the server
        parts.append("Trusted_Connection=yes")
    return ";".join(parts) + ";"


def get_connection():
    """Open a new connection to SQL Server. Remember to close it (execute_query does this for you)."""
    return pyodbc.connect(_connection_string())


def _rows_to_dicts(cursor, rows):
    columns = [col[0] for col in cursor.description]
    return [dict(zip(columns, row)) for row in rows]


def execute_query(query, params=None, fetch_one=False, fetch_all=False, commit=False):
    """
    Run one SQL statement safely.

    query     : SQL text with '?' placeholders, e.g. "SELECT * FROM Users WHERE email = ?"
    params    : values for the placeholders, e.g. (email,)
    fetch_one : return one row as a dict (or None)
    fetch_all : return all rows as a list of dicts
    commit    : save changes (INSERT / UPDATE / DELETE)
    """
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(query, params or ())

        if fetch_one:
            row = cursor.fetchone()
            result = _rows_to_dicts(cursor, [row])[0] if row else None
            if commit:
                conn.commit()
            return result

        if fetch_all:
            rows = cursor.fetchall()
            result = _rows_to_dicts(cursor, rows) if rows else []
            if commit:
                conn.commit()
            return result

        if commit:
            conn.commit()
        return True
    except Exception:
        conn.rollback()
        log.exception("Database query failed")
        raise
    finally:
        cursor.close()
        conn.close()


def execute_insert_and_get_id(query, params=None):
    """
    Run an INSERT and return the new row's id.
    The query should contain 'OUTPUT INSERTED.<id_column>' before VALUES,
    e.g. "INSERT INTO Cameras (name) OUTPUT INSERTED.camera_id VALUES (?)".
    """
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(query, params or ())
        row = cursor.fetchone()
        conn.commit()
        return int(row[0]) if row and row[0] is not None else None
    except Exception:
        conn.rollback()
        log.exception("Database insert failed")
        raise
    finally:
        cursor.close()
        conn.close()
