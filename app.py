from flask import Flask, render_template, request, redirect, url_for, session
import sqlite3

app = Flask(__name__)
app.secret_key = "surplus_food_secret"


# Database connection
def get_db():
    conn = sqlite3.connect("database.db")
    conn.row_factory = sqlite3.Row
    return conn


# Create database tables
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
            status TEXT DEFAULT 'Available'
        )
    """)

    conn.commit()
    conn.close()
init_db()
    


# Home page
@app.route("/")
def index():
    return render_template("index.html")


# Register
@app.route("/register", methods=["GET", "POST"])
def register():

    if request.method == "POST":
        username = request.form["username"]
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


# Login
@app.route("/login", methods=["GET", "POST"])
def login():

    if request.method == "POST":

        username = request.form["username"]
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

            return redirect(url_for("dashboard"))

        return "Invalid username or password!"

    return render_template("login.html")


# Dashboard
@app.route("/dashboard")
def dashboard():

    if "username" not in session:
        return redirect(url_for("login"))

    return render_template(
        "dashboard.html",
        username=session["username"],
        role=session["role"]
    )


# Donate surplus food
@app.route("/donate", methods=["GET", "POST"])
def donate():

    if "username" not in session:
        return redirect(url_for("login"))

    if request.method == "POST":

        food_name = request.form["food_name"]
        quantity = request.form["quantity"]
        location = request.form["location"]

        conn = get_db()

        conn.execute("""
            INSERT INTO food
            (food_name, quantity, location, status)
            VALUES (?, ?, ?, ?)
        """, (food_name, quantity, location, "Available"))

        conn.commit()
        conn.close()

        return redirect(url_for("food_list"))

    return render_template("donate.html")


# View food donations
@app.route("/food")
def food_list():

    conn = get_db()

    foods = conn.execute(
        "SELECT * FROM food ORDER BY id DESC"
    ).fetchall()

    conn.close()

    return render_template(
        "food_list.html",
        foods=foods
    )


# Logout
@app.route("/logout")
def logout():

    session.clear()

    return redirect(url_for("index"))


if __name__ == "__main__":
    init_db()
    app.run(debug=True)
