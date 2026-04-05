import secrets
import sqlite3
import os
from flask import Flask, render_template, request, redirect, url_for, flash

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY") or secrets.token_hex(32)

DATABASE = os.path.join(os.path.dirname(__file__), "training.db")


def get_db():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with get_db() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS trainings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                employee_name TEXT NOT NULL,
                department TEXT NOT NULL,
                training_title TEXT NOT NULL,
                training_type TEXT NOT NULL,
                due_date TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'Pending',
                relevant_modules TEXT,
                notes TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        conn.commit()


@app.route("/", methods=["GET"])
def index():
    search = request.args.get("search", "").strip()
    status_filter = request.args.get("status", "")
    department_filter = request.args.get("department", "")

    query = "SELECT * FROM trainings WHERE 1=1"
    params = []

    if search:
        query += " AND (employee_name LIKE ? OR training_title LIKE ? OR department LIKE ?)"
        like = f"%{search}%"
        params.extend([like, like, like])

    if status_filter:
        query += " AND status = ?"
        params.append(status_filter)

    if department_filter:
        query += " AND department = ?"
        params.append(department_filter)

    query += " ORDER BY created_at DESC"

    with get_db() as conn:
        trainings = conn.execute(query, params).fetchall()
        departments = [
            row["department"]
            for row in conn.execute(
                "SELECT DISTINCT department FROM trainings ORDER BY department"
            ).fetchall()
        ]

    return render_template(
        "index.html",
        trainings=trainings,
        search=search,
        status_filter=status_filter,
        department_filter=department_filter,
        departments=departments,
    )


@app.route("/add", methods=["GET", "POST"])
def add_training():
    if request.method == "POST":
        employee_name = request.form.get("employee_name", "").strip()
        department = request.form.get("department", "").strip()
        training_title = request.form.get("training_title", "").strip()
        training_type = request.form.get("training_type", "").strip()
        due_date = request.form.get("due_date", "").strip()
        status = request.form.get("status", "Pending").strip()
        relevant_modules = request.form.get("relevant_modules", "").strip()
        notes = request.form.get("notes", "").strip()

        errors = []
        if not employee_name:
            errors.append("Employee name is required.")
        if not department:
            errors.append("Department is required.")
        if not training_title:
            errors.append("Training title is required.")
        if not training_type:
            errors.append("Training type is required.")
        if not due_date:
            errors.append("Due date is required.")

        if errors:
            for error in errors:
                flash(error, "danger")
            return render_template("add.html", form=request.form)

        with get_db() as conn:
            conn.execute(
                """
                INSERT INTO trainings
                    (employee_name, department, training_title, training_type,
                     due_date, status, relevant_modules, notes)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (employee_name, department, training_title, training_type,
                 due_date, status, relevant_modules, notes),
            )
            conn.commit()

        flash("Training requirement added successfully!", "success")
        return redirect(url_for("index"))

    return render_template("add.html", form={})


@app.route("/delete/<int:training_id>", methods=["POST"])
def delete_training(training_id):
    with get_db() as conn:
        conn.execute("DELETE FROM trainings WHERE id = ?", (training_id,))
        conn.commit()
    flash("Training record deleted.", "info")
    return redirect(url_for("index"))


if __name__ == "__main__":
    init_db()
    debug = os.environ.get("FLASK_DEBUG", "false").lower() == "true"
    host = os.environ.get("FLASK_HOST", "127.0.0.1")
    port = int(os.environ.get("FLASK_PORT", "5000"))
    app.run(debug=debug, host=host, port=port)
