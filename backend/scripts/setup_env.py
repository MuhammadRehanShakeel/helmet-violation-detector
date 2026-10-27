"""
setup_env.py - Creates backend/.env the first time (with a strong random JWT_SECRET).

Run:  venv\\Scripts\\python.exe scripts\\setup_env.py [SQL_SERVER_NAME]
Existing values in .env are never overwritten.
"""
import os
import secrets
import sys

BACKEND = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ENV = os.path.join(BACKEND, ".env")
EXAMPLE = os.path.join(BACKEND, ".env.example")


def read(path):
    values = {}
    if os.path.exists(path):
        for line in open(path, encoding="utf-8"):
            if "=" in line and not line.strip().startswith("#"):
                key, _, value = line.strip().partition("=")
                values[key] = value
    return values


def main():
    current = read(ENV)
    lines = open(EXAMPLE, encoding="utf-8").read().splitlines()
    defaults = {"JWT_SECRET": secrets.token_urlsafe(48)}
    if len(sys.argv) > 1:
        defaults["DB_SERVER"] = sys.argv[1]
    out = []
    for line in lines:
        if "=" in line and not line.strip().startswith("#"):
            key, _, value = line.partition("=")
            value = current.get(key) or defaults.get(key) or value
            out.append(f"{key}={value}")
        else:
            out.append(line)
    with open(ENV, "w", encoding="utf-8") as f:
        f.write("\n".join(out) + "\n")
    print("[OK] backend/.env is ready (JWT_SECRET is random and private)")


if __name__ == "__main__":
    main()
