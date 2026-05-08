"""
Control Board — Flask application.

Provides authenticated machine ON/OFF control over MQTT and
a live dashboard showing machine status.
"""

import os
import sqlite3
from functools import wraps
import threading
from Backend.Utils.SignalSender import publish_machine_signal
from Backend.Utils.SensorData import start_cloud_data_subscription

from dotenv import load_dotenv
load_dotenv()

DIGITAL_TWIN_BASE_URL = os.environ.get("DIGITAL_TWIN_BASE_URL", "http://localhost:8000/")
DASHBOARD_BASE_URL = os.environ.get("DASHBOARD_BASE_URL", "http://localhost:8086/orgs/2dee5ed4f7a56df1/dashboards/106c4dcc3053f000?lower=now()-15m&vars[machine]=")

from flask import (
    Flask,
    flash,
    jsonify,
    redirect,
    render_template,
    request,
    session,
    url_for,
)
from werkzeug.security import check_password_hash, generate_password_hash

# ── app setup ──────────────────────────────────────────────────

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET", os.urandom(32))

DB_PATH = os.getenv("CONTROLBOARD_DB_PATH", "controlboard.db")

# ── switch state setup ──────────────────────────────────────────────────


machine_data = {}
lock = threading.Lock()
start_cloud_data_subscription(machine_data, lock)


# ── helpers ────────────────────────────────────────────────────

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def login_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if "user_id" not in session:
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return wrapper


def get_user_machines(user_id):
    """Return list of machine_ids the user is authorized for."""
    db = get_db()
    rows = db.execute(
        "SELECT machine_id FROM user_machines WHERE user_id = ?", (user_id,)
    ).fetchall()
    db.close()
    return [r["machine_id"] for r in rows]


# ── pages ──────────────────────────────────────────────────────

@app.route("/")
@login_required
def dashboard():
    machines = get_user_machines(session["user_id"])
    return render_template(
        "dashboard.html",
        username=session["username"],
        role=session["role"],
        machines=machines,
        digital_twin_base_url=DIGITAL_TWIN_BASE_URL,
        dashboard_base_url=DASHBOARD_BASE_URL,
    )


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "GET":
        return render_template("login.html")

    username = request.form.get("username", "").strip()
    password = request.form.get("password", "")

    db = get_db()
    user = db.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()
    db.close()

    if user and check_password_hash(user["password_hash"], password):
        session["user_id"] = user["id"]
        session["username"] = user["username"]
        session["role"] = user["role"]
        return redirect(url_for("dashboard"))

    flash("Invalid username or password.", "error")
    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


# ── API ────────────────────────────────────────────────────────

@app.route("/api/control", methods=["POST"])
@login_required
def api_control():
    """Send ON / OFF command to a machine."""
    data = request.get_json(silent=True) or {}
    machine_id = data.get("machine_id")
    action = data.get("action")

    if action not in ("ON", "OFF"):
        return jsonify({"error": "action must be ON or OFF"}), 400

    allowed = get_user_machines(session["user_id"])
    if machine_id not in allowed:
        return jsonify({"error": "You are not authorized to control this machine."}), 403

    publish_machine_signal(machine_id, action=="ON")  

    return jsonify({"ok": True, "machine_id": machine_id, "action": action})


@app.route("/api/status")
@login_required
def api_status():
    """Return live status for the caller's authorized machines."""
    allowed = get_user_machines(session["user_id"])
    with lock:
        all_status = {mid: dict(data) for mid, data in machine_data.items()}
    result = {}
    for mid in allowed:
        result[mid] = all_status.get(mid, {"switch_state": "NA"})

    return jsonify(result)


# ── admin: manage users ───────────────────────────────────────

@app.route("/api/admin/users", methods=["GET"])
@login_required
def api_list_users():
    if session.get("role") != "admin":
        return jsonify({"error": "Admin only"}), 403

    db = get_db()
    users = db.execute("SELECT id, username, role FROM users").fetchall()
    result = []
    for u in users:
        machines = db.execute(
            "SELECT machine_id FROM user_machines WHERE user_id = ?", (u["id"],)
        ).fetchall()
        result.append({
            "id": u["id"],
            "username": u["username"],
            "role": u["role"],
            "machines": [m["machine_id"] for m in machines],
        })
    db.close()
    return jsonify(result)


@app.route("/api/admin/users", methods=["POST"])
@login_required
def api_create_user():
    if session.get("role") != "admin":
        return jsonify({"error": "Admin only"}), 403

    data = request.get_json(silent=True) or {}
    username = data.get("username", "").strip()
    password = data.get("password", "")
    role = data.get("role", "operator")
    machines = data.get("machines", [])

    if not username or not password:
        return jsonify({"error": "username and password required"}), 400

    db = get_db()
    try:
        db.execute(
            "INSERT INTO users (username, password_hash, role) VALUES (?, ?, ?)",
            (username, generate_password_hash(password), role),
        )
        user_id = db.execute("SELECT last_insert_rowid()").fetchone()[0]
        for mid in machines:
            db.execute(
                "INSERT OR IGNORE INTO user_machines (user_id, machine_id) VALUES (?, ?)",
                (user_id, mid),
            )
        db.commit()
    except sqlite3.IntegrityError:
        db.close()
        return jsonify({"error": "Username already exists"}), 409
    db.close()
    return jsonify({"ok": True, "user_id": user_id})


@app.route("/api/admin/users/<int:user_id>", methods=["DELETE"])
@login_required
def api_delete_user(user_id):
    if session.get("role") != "admin":
        return jsonify({"error": "Admin only"}), 403

    db = get_db()
    db.execute("DELETE FROM user_machines WHERE user_id = ?", (user_id,))
    db.execute("DELETE FROM users WHERE id = ?", (user_id,))
    db.commit()
    db.close()
    return jsonify({"ok": True})


# ── entry point ────────────────────────────────────────────────

if __name__ == "__main__":
    # Ensure DB exists
    if not os.path.exists(DB_PATH):
        from init_db import init
        init()

    app.run(host="0.0.0.0", port=5000, debug=False)
