from flask import Flask, render_template, request, redirect, url_for, session
import sqlite3

app = Flask(__name__)
app.secret_key = "surplus_food_secret"


# ---------------- DATABASE ----------------
def get_db():
    conn = sqlite3.connect("database.db")
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_db()

    conn.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL UNIQUE,
            password TEXT NOT NULL,
            role TEXT NOT NULL
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS food (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            food_name TEXT NOT NULL,
            quantity TEXT NOT NULL,
            location TEXT NOT NULL,
            status TEXT DEFAULT 'Available',
            donor_username TEXT
        )
    """)

    # Safe migration for databases created by the original 35% prototype.
    columns = [row["name"] for row in conn.execute("PRAGMA table_info(food)").fetchall()]
    if "donor_username" not in columns:
        conn.execute("ALTER TABLE food ADD COLUMN donor_username TEXT")

    # Prototype admin account. Existing users are not changed.
     # Prototype admin account
     conn.execute("""
        INSERT INTO users (username, password, role)
        VALUES (?, ?, ?)
        ON CONFLICT(username) DO UPDATE SET
            password = excluded.password,
            role = excluded.role
      """, ("admin", "admin123", "Admin"))

init_db()


# ---------------- USER AUTH ----------------
@app.route("/")
def index():
    return render_template("index.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form["username"].strip()
        password = request.form["password"]
        role = request.form["role"]

        conn = get_db()
        try:
            conn.execute(
                "INSERT INTO users (username, password, role) VALUES (?, ?, ?)",
                (username, password, role)
            )
            conn.commit()
            conn.close()
            return redirect(url_for("login"))
        except sqlite3.IntegrityError:
            conn.close()
            return "Username already exists!"

    return render_template("register.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form["username"].strip()
        password = request.form["password"]

        conn = get_db()
        user = conn.execute(
            "SELECT * FROM users WHERE username=? AND password=?",
            (username, password)
        ).fetchone()
        conn.close()

        if user:
            session["username"] = user["username"]
            session["role"] = user["role"]

            if user["role"] == "Admin":
                return redirect(url_for("admin_dashboard"))

            return redirect(url_for("dashboard"))

        return "Invalid username or password!"

    return render_template("login.html")


@app.route("/dashboard")
def dashboard():
    if "username" not in session:
        return redirect(url_for("login"))

    if session.get("role") == "Admin":
        return redirect(url_for("admin_dashboard"))

    return render_template(
        "dashboard.html",
        username=session["username"],
        role=session["role"]
    )


# ---------------- DONOR / FOOD ----------------
@app.route("/donate", methods=["GET", "POST"])
def donate():
    if "username" not in session:
        return redirect(url_for("login"))

    if session.get("role") == "Admin":
        return redirect(url_for("admin_dashboard"))

    if request.method == "POST":
        food_name = request.form["food_name"].strip()
        quantity = request.form["quantity"].strip()
        location = request.form["location"].strip()

        conn = get_db()
        conn.execute("""
            INSERT INTO food
            (food_name, quantity, location, status, donor_username)
            VALUES (?, ?, ?, ?, ?)
        """, (
            food_name,
            quantity,
            location,
            "Available",
            session["username"]
        ))
        conn.commit()
        conn.close()

        return redirect(url_for("food_list"))

    return render_template("donate.html")


@app.route("/food")
def food_list():
    conn = get_db()
    foods = conn.execute(
        "SELECT * FROM food ORDER BY id DESC"
    ).fetchall()
    conn.close()

    return render_template("food_list.html", foods=foods)


# ---------------- ADMIN ----------------
def admin_required():
    return "username" in session and session.get("role") == "Admin"


@app.route("/admin/login", methods=["GET", "POST"])
def admin_login():
    if request.method == "POST":
        username = request.form["username"].strip()
        password = request.form["password"]

        conn = get_db()
        admin = conn.execute(
            "SELECT * FROM users WHERE username=? AND password=? AND role='Admin'",
            (username, password)
        ).fetchone()
        conn.close()

        if admin:
            session["username"] = admin["username"]
            session["role"] = "Admin"
            return redirect(url_for("admin_dashboard"))

        return "Invalid admin credentials!"

    return render_template("admin_login.html")


@app.route("/admin/dashboard")
def admin_dashboard():
    if not admin_required():
        return redirect(url_for("admin_login"))

    conn = get_db()
    total_food = conn.execute("SELECT COUNT(*) AS c FROM food").fetchone()["c"]
    available = conn.execute(
        "SELECT COUNT(*) AS c FROM food WHERE status='Available'"
    ).fetchone()["c"]
    approved = conn.execute(
        "SELECT COUNT(*) AS c FROM food WHERE status='Approved'"
    ).fetchone()["c"]
    collected = conn.execute(
        "SELECT COUNT(*) AS c FROM food WHERE status='Collected'"
    ).fetchone()["c"]
    rejected = conn.execute(
        "SELECT COUNT(*) AS c FROM food WHERE status='Rejected'"
    ).fetchone()["c"]
    total_users = conn.execute("SELECT COUNT(*) AS c FROM users").fetchone()["c"]
    recent_food = conn.execute(
        "SELECT * FROM food ORDER BY id DESC LIMIT 6"
    ).fetchall()
    conn.close()

    return render_template(
        "admin_dashboard.html",
        total_food=total_food,
        available=available,
        approved=approved,
        collected=collected,
        rejected=rejected,
        total_users=total_users,
        recent_food=recent_food
    )


@app.route("/admin/donations")
def admin_donations():
    if not admin_required():
        return redirect(url_for("admin_login"))

    conn = get_db()
    foods = conn.execute("SELECT * FROM food ORDER BY id DESC").fetchall()
    conn.close()

    return render_template("admin_donations.html", foods=foods)


@app.route("/admin/donation/<int:food_id>/status", methods=["POST"])
def update_donation_status(food_id):
    if not admin_required():
        return redirect(url_for("admin_login"))

    status = request.form["status"]
    allowed = {"Available", "Approved", "Rejected", "Collected"}

    if status not in allowed:
        return redirect(url_for("admin_donations"))

    conn = get_db()
    conn.execute(
        "UPDATE food SET status=? WHERE id=?",
        (status, food_id)
    )
    conn.commit()
    conn.close()

    return redirect(url_for("admin_donations"))


@app.route("/admin/users")
def admin_users():
    if not admin_required():
        return redirect(url_for("admin_login"))

    conn = get_db()
    users = conn.execute(
        "SELECT id, username, role FROM users ORDER BY id DESC"
    ).fetchall()
    conn.close()

    return render_template("admin_users.html", users=users)


@app.route("/admin/analytics")
def admin_analytics():
    if not admin_required():
        return redirect(url_for("admin_login"))

    conn = get_db()
    total = conn.execute("SELECT COUNT(*) AS c FROM food").fetchone()["c"]
    available = conn.execute(
        "SELECT COUNT(*) AS c FROM food WHERE status='Available'"
    ).fetchone()["c"]
    approved = conn.execute(
        "SELECT COUNT(*) AS c FROM food WHERE status='Approved'"
    ).fetchone()["c"]
    rejected = conn.execute(
        "SELECT COUNT(*) AS c FROM food WHERE status='Rejected'"
    ).fetchone()["c"]
    collected = conn.execute(
        "SELECT COUNT(*) AS c FROM food WHERE status='Collected'"
    ).fetchone()["c"]

    donor_count = conn.execute(
        "SELECT COUNT(*) AS c FROM users WHERE role='Donor'"
    ).fetchone()["c"]
    receiver_count = conn.execute(
        "SELECT COUNT(*) AS c FROM users WHERE role='Receiver'"
    ).fetchone()["c"]
    conn.close()

    return render_template(
        "admin_analytics.html",
        total=total,
        available=available,
        approved=approved,
        rejected=rejected,
        collected=collected,
        donor_count=donor_count,
        receiver_count=receiver_count
    )


@app.route("/admin/logout")
def admin_logout():
    session.clear()
    return redirect(url_for("index"))


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("index"))


if __name__ == "__main__":
    init_db()
    app.run(debug=True)
