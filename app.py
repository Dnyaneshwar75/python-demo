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
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS reviews (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                training_id INTEGER NOT NULL,
                reviewer_name TEXT NOT NULL,
                rating INTEGER NOT NULL CHECK(rating BETWEEN 1 AND 5),
                feedback TEXT NOT NULL,
                review_date TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (training_id) REFERENCES trainings(id) ON DELETE CASCADE
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


# ── Reviews ──────────────────────────────────────────────────────────────────

@app.route("/reviews")
def reviews():
    search = request.args.get("search", "").strip()
    rating_filter = request.args.get("rating", "")

    query = """
        SELECT r.*, t.training_title, t.employee_name, t.department
        FROM reviews r
        JOIN trainings t ON r.training_id = t.id
        WHERE 1=1
    """
    params = []

    if search:
        like = f"%{search}%"
        query += " AND (r.reviewer_name LIKE ? OR t.training_title LIKE ? OR t.employee_name LIKE ? OR r.feedback LIKE ?)"
        params.extend([like, like, like, like])

    if rating_filter:
        query += " AND r.rating = ?"
        params.append(int(rating_filter))

    query += " ORDER BY r.created_at DESC"

    with get_db() as conn:
        all_reviews = conn.execute(query, params).fetchall()
        avg_row = conn.execute("SELECT AVG(rating) as avg_rating, COUNT(*) as total FROM reviews").fetchone()

    return render_template(
        "reviews.html",
        reviews=all_reviews,
        search=search,
        rating_filter=rating_filter,
        avg_rating=avg_row["avg_rating"],
        total_reviews=avg_row["total"],
    )


@app.route("/reviews/add/<int:training_id>", methods=["GET", "POST"])
def add_review(training_id):
    with get_db() as conn:
        training = conn.execute("SELECT * FROM trainings WHERE id = ?", (training_id,)).fetchone()

    if training is None:
        flash("Training record not found.", "danger")
        return redirect(url_for("index"))

    if request.method == "POST":
        reviewer_name = request.form.get("reviewer_name", "").strip()
        rating = request.form.get("rating", "").strip()
        feedback = request.form.get("feedback", "").strip()
        review_date = request.form.get("review_date", "").strip()

        errors = []
        if not reviewer_name:
            errors.append("Reviewer name is required.")
        if not rating or not rating.isdigit() or not (1 <= int(rating) <= 5):
            errors.append("A rating between 1 and 5 is required.")
        if not feedback:
            errors.append("Feedback text is required.")
        if not review_date:
            errors.append("Review date is required.")

        if errors:
            for error in errors:
                flash(error, "danger")
            return render_template("add_review.html", training=training, form=request.form)

        with get_db() as conn:
            conn.execute(
                """
                INSERT INTO reviews (training_id, reviewer_name, rating, feedback, review_date)
                VALUES (?, ?, ?, ?, ?)
                """,
                (training_id, reviewer_name, int(rating), feedback, review_date),
            )
            conn.commit()

        flash("Review submitted successfully!", "success")
        return redirect(url_for("reviews"))

    return render_template("add_review.html", training=training, form={})


@app.route("/reviews/delete/<int:review_id>", methods=["POST"])
def delete_review(review_id):
    with get_db() as conn:
        conn.execute("DELETE FROM reviews WHERE id = ?", (review_id,))
        conn.commit()
    flash("Review deleted.", "info")
    return redirect(url_for("reviews"))


if __name__ == "__main__":
    init_db()
    debug = os.environ.get("FLASK_DEBUG", "false").lower() == "true"
    host = os.environ.get("FLASK_HOST", "127.0.0.1")
    port = int(os.environ.get("FLASK_PORT", "5000"))
    app.run(debug=debug, host=host, port=port)
