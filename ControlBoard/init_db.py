"""
Initialize the Control Board SQLite database with default users.

Run once:  python init_db.py
"""

import os
import sqlite3
from werkzeug.security import generate_password_hash

DB_PATH = os.getenv("CONTROLBOARD_DB_PATH", "controlboard.db")


def init():
    db_dir = os.path.dirname(DB_PATH)
    if db_dir:
        os.makedirs(db_dir, exist_ok=True)

    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    c.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            username      TEXT    UNIQUE NOT NULL,
            password_hash TEXT    NOT NULL,
            role          TEXT    DEFAULT 'operator'
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS user_machines (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id    INTEGER NOT NULL,
            machine_id TEXT    NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users(id),
            UNIQUE(user_id, machine_id)
        )
    """)

    # ── seed default users ──────────────────────────────────
    default_users = [
        ("admin",     "admin123",    "admin",    ["machine01", "machine02", "machine03"]),
        ("operator1", "operator123", "operator", ["machine01"]),
        ("operator2", "operator456", "operator", ["machine02"]),
    ]

    for username, password, role, machines in default_users:
        existing = c.execute("SELECT id FROM users WHERE username = ?", (username,)).fetchone()
        if existing:
            print(f"  User '{username}' already exists — skipping.")
            continue

        c.execute(
            "INSERT INTO users (username, password_hash, role) VALUES (?, ?, ?)",
            (username, generate_password_hash(password), role),
        )
        user_id = c.lastrowid

        for mid in machines:
            c.execute(
                "INSERT INTO user_machines (user_id, machine_id) VALUES (?, ?)",
                (user_id, mid),
            )
        print(f"  Created user '{username}' → machines {machines}")

    conn.commit()
    conn.close()
    print("\nDatabase initialized at", DB_PATH)


if __name__ == "__main__":
    init()
