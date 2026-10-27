"""
init_db.py - Creates (or upgrades) the RoadGuard database, its tables and your first admin account.

Run once from the backend folder:
    venv\\Scripts\\python.exe scripts\\init_db.py

It asks for the admin's name, email and password in the console
(the password is typed hidden and stored only as a bcrypt hash).
Safe to run again: existing tables and users are left alone.
"""
import getpass
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pyodbc  # noqa: E402

from app import config  # noqa: E402
from app.core.security import check_password_rules, hash_password  # noqa: E402


def connect(database: str):
    parts = [f"DRIVER={{{config.DB_DRIVER}}}", f"SERVER={config.DB_SERVER}",
             f"DATABASE={database}", "TrustServerCertificate=yes"]
    if config.DB_AUTH == "sql":
        parts += [f"UID={config.DB_USER}", f"PWD={config.DB_PASSWORD}"]
    else:
        parts.append("Trusted_Connection=yes")
    return pyodbc.connect(";".join(parts) + ";", autocommit=True)


def main():
    print(f"Connecting to SQL Server {config.DB_SERVER} ...")
    master = connect("master")
    master.cursor().execute(f"IF DB_ID(N'{config.DB_NAME}') IS NULL CREATE DATABASE [{config.DB_NAME}]")
    master.close()
    print(f"[OK] Database {config.DB_NAME} is ready")

    conn = connect(config.DB_NAME)
    cur = conn.cursor()
    for name in ("schema.sql", "migrations.sql"):          # tables first, then the v2 upgrades
        with open(os.path.join(os.path.dirname(__file__), name), encoding="utf-8") as f:
            sql = f.read()
        # run each "IF ... CREATE / ALTER ..." block separately (blocks are separated by a blank line)
        blocks = []
        for block in sql.split("\n\n"):
            code = "\n".join(line for line in block.splitlines() if not line.strip().startswith("--")).strip()
            if code:
                blocks.append(code)
        for block in blocks:
            cur.execute(block)
        print(f"[OK] {name}: {len(blocks)} steps done")

    cur.execute("SELECT COUNT(*) FROM Cameras")
    if cur.fetchone()[0] == 0:
        cameras = [
            ("Faizabad Interchange", "Murree Road, Rawalpindi", 33.6625, 73.0846),
            ("Saddar Chowk", "Bank Road, Rawalpindi", 33.5973, 73.0479),
            ("Zero Point", "Islamabad Expressway, Islamabad", 33.6935, 73.0652),
            ("Mobile phone camera", "Any location (live from the app)", None, None),
        ]
        cur.executemany("INSERT INTO Cameras (name, location, latitude, longitude) VALUES (?, ?, ?, ?)", cameras)
        print(f"[OK] Added {len(cameras)} sample camera locations")

    cur.execute("SELECT COUNT(*) FROM Users WHERE role = 'admin'")
    if cur.fetchone()[0] == 0:
        print("\nCreate the first ADMIN account")
        name = input("  Full name: ").strip() or "Admin"
        email = input("  Email: ").strip().lower()
        while True:
            password = getpass.getpass("  Password (hidden, 8+ chars with a letter and a number): ")
            try:
                check_password_rules(password)
                break
            except Exception as e:
                print("  ", getattr(e, "detail", e))
        cur.execute("INSERT INTO Users (full_name, email, password_hash, role) VALUES (?, ?, ?, 'admin')",
                    (name, email, hash_password(password)))
        print(f"[OK] Admin {email} created")
    else:
        print("[OK] An admin already exists - no new account created")
    conn.close()
    print("\nAll done. Start the API with start_project.bat")


if __name__ == "__main__":
    main()
