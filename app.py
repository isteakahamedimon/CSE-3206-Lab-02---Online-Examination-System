import os
import sqlite3
import time
from functools import wraps
from flask import Flask, render_template, request, redirect, url_for, session, flash, g
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = "cse3206_secret_key_group_05"
DATABASE = "online_exam.db"

def get_db():
    db = getattr(g, '_database', None)
    if db is None:
        db = g._database = sqlite3.connect(DATABASE)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA foreign_keys = ON;")
    return db

@app.teardown_appcontext
def close_connection(exception):
    db = getattr(g, '_database', None)
    if db is not None:
        db.close()

def init_db():
    with app.app_context():
        db = get_db()
        with open("schema.sql", mode="r") as f:
            db.cursor().executescript(f.read())
        db.commit()

# --- Custom Access-Control Decorators ---
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if "user_id" not in session:
            flash("Please log in to access this page.", "warning")
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return decorated_function

def role_required(role):
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if session.get("role") != role:
                flash("Unauthorized access!", "danger")
                return redirect(url_for("dashboard"))
            return f(*args, **kwargs)
        return decorated_function
    return decorator

# --- Base Auth Routes ---
@app.route("/")
def index():
    if "user_id" in session:
        return redirect(url_for("dashboard"))
    return redirect(url_for("login"))

@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        name = request.form.get("name").strip()
        email = request.form.get("email").strip()
        password = request.form.get("password")
        role = request.form.get("role")
        
        roll = request.form.get("roll", "").strip() if role == "student" else None
        teacher_uid = request.form.get("teacher_uid", "").strip() if role == "teacher" else None
        department = request.form.get("department", "").strip()
        
        if not name or not email or not password or role not in ["student", "teacher"] or not department:
            flash("Please fill in all fields correctly.", "danger")
            return render_template("register.html")
            
        hashed_password = generate_password_hash(password)
        db = get_db()
        try:
            db.execute(
                "INSERT INTO users (name, email, password, role, roll, teacher_uid, department) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (name, email, hashed_password, role, roll, teacher_uid, department)
            )
            db.commit()
            flash("Registration successful! Please log in.", "success")
            return redirect(url_for("login"))
        except sqlite3.IntegrityError:
            flash("Email address is already registered.", "danger")
            
    return render_template("register.html")

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email").strip()
        password = request.form.get("password")
        
        db = get_db()
        user = db.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
        
        if user and check_password_hash(user["password"], password):
            session["user_id"] = user["id"]
            session["name"] = user["name"]
            session["role"] = user["role"]
            flash(f"Welcome back, {user['name']}!", "success")
            return redirect(url_for("dashboard"))
        else:
            flash("Invalid email or password.", "danger")
            
    return render_template("login.html")

@app.route("/logout")
def logout():
    session.clear()
    flash("You have been logged out.", "info")
    return redirect(url_for("login"))

@app.route("/profile")
@login_required
def profile():
    db = get_db()
    user = db.execute("SELECT name, email, role, roll, teacher_uid, department FROM users WHERE id = ?", (session["user_id"],)).fetchone()
    
    if user is None:
        session.clear()
        flash("Your session has expired. Please log in again.", "warning")
        return redirect(url_for("login"))
        
    stats = {}
    if user["role"] == "teacher":
        exams_count = db.execute("SELECT COUNT(*) FROM exams WHERE teacher_id = ?", (session["user_id"],)).fetchone()[0]
        stats["exams_created"] = exams_count
    else:
        subs = db.execute('''
            SELECT s.score, e.total_marks, e.title, s.submitted_at 
            FROM submissions s
            JOIN exams e ON s.exam_id = e.id
            WHERE s.student_id = ?
        ''', (session["user_id"],)).fetchall()
        stats["exams_taken"] = len(subs)
        stats["submissions"] = subs
        if len(subs) > 0:
            avg_perf = sum([int((sub["score"] / sub["total_marks"]) * 100) for sub in subs]) / len(subs)
            stats["average_percentage"] = round(avg_perf, 1)
        else:
            stats["average_percentage"] = 0
            
    return render_template("profile.html", user=user, stats=stats)


@app.route("/dashboard")
@login_required
def dashboard():
    db = get_db()
    user = db.execute("SELECT id, role, roll, department FROM users WHERE id = ?", (session["user_id"],)).fetchone()
    if user is None:
        session.clear()
        flash("Your session has expired. Please log in again.", "warning")
        return redirect(url_for("login"))

    if session["role"] == "teacher":
        exams = db.execute('''
            SELECT e.*, COUNT(s.id) as submission_count 
            FROM exams e 
            LEFT JOIN submissions s ON e.id = s.exam_id 
            WHERE e.teacher_id = ? 
            GROUP BY e.id
        ''', (session["user_id"],)).fetchall()
        return render_template("dashboard_teacher.html", exams=exams)
    else:
        # Student dashboard - select only PUBLIC exams matching student's department and roll pattern
        search_query = request.args.get("search", "").strip()
        student_roll = user["roll"] if user["roll"] else ""
        student_dept = user["department"] if user["department"] else ""
        
        # We fetch public exams where target_dept is empty OR matches student_dept,
        # AND target_roll_pattern is empty OR student_roll fits pattern (using SQL LIKE, e.g. '2203%')
        query_sql = '''
            SELECT e.*, u.name as teacher_name 
            FROM exams e 
            JOIN users u ON e.teacher_id = u.id 
            WHERE e.is_public = 1 
              AND (e.target_dept IS NULL OR e.target_dept = '' OR e.target_dept = ?)
              AND (e.target_roll_pattern IS NULL OR e.target_roll_pattern = '' OR ? LIKE e.target_roll_pattern)
        '''
        
        if search_query:
            query_sql += " AND e.title LIKE ?"
            exams_raw = db.execute(query_sql, (student_dept, student_roll, f"%{search_query}%")).fetchall()
        else:
            exams_raw = db.execute(query_sql, (student_dept, student_roll)).fetchall()
            
        submissions = db.execute(
            "SELECT exam_id, score, submitted_at FROM submissions WHERE student_id = ?",
            (session["user_id"],)
        ).fetchall()
        
        sub_map = {sub["exam_id"]: sub for sub in submissions}
        return render_template("dashboard_student.html", exams=exams_raw, sub_map=sub_map, search_query=search_query)

@app.route("/exams/create", methods=["GET", "POST"])
@login_required
@role_required("teacher")
def create_exam():
    if request.method == "POST":
        title = request.form.get("title").strip()
        duration = request.form.get("duration")
        total_marks = request.form.get("total_marks")
        target_dept = request.form.get("target_dept", "").strip()
        target_roll_pattern = request.form.get("target_roll_pattern", "").strip()
        
        if not title or not duration or not total_marks:
            flash("All fields are required.", "danger")
            return render_template("create_exam.html")
            
        db = get_db()
        db.execute(
            "INSERT INTO exams (teacher_id, title, duration, total_marks, is_public, target_dept, target_roll_pattern) VALUES (?, ?, ?, ?, 0, ?, ?)",
            (session["user_id"], title, int(duration), int(total_marks), target_dept, target_roll_pattern)
        )
        db.commit()
        flash("Exam created successfully as draft! Now add questions.", "success")
        return redirect(url_for("dashboard"))
        
    return render_template("create_exam.html")

@app.route("/exams/<int:exam_id>/questions", methods=["GET", "POST"])
@login_required
@role_required("teacher")
def manage_questions(exam_id):
    db = get_db()
    exam = db.execute("SELECT * FROM exams WHERE id = ? AND teacher_id = ?", (exam_id, session["user_id"])).fetchone()
    if not exam:
        flash("Exam not found or unauthorized.", "danger")
        return redirect(url_for("dashboard"))
        
    if request.method == "POST":
        question_text = request.form.get("question_text").strip()
        option_a = request.form.get("option_a").strip()
        option_b = request.form.get("option_b").strip()
        option_c = request.form.get("option_c").strip()
        option_d = request.form.get("option_d").strip()
        correct_option = request.form.get("correct_option")
        
        if not all([question_text, option_a, option_b, option_c, option_d, correct_option]):
            flash("All fields are required to add a question.", "danger")
        else:
            db.execute('''
                INSERT INTO questions (exam_id, question_text, option_a, option_b, option_c, option_d, correct_option)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (exam_id, question_text, option_a, option_b, option_c, option_d, correct_option))
            db.commit()
            flash("Question added successfully!", "success")
            
    questions = db.execute("SELECT * FROM questions WHERE exam_id = ?", (exam_id,)).fetchall()
    return render_template("questions.html", exam=exam, questions=questions)

@app.route("/exams/<int:exam_id>/questions/<int:question_id>/delete", methods=["POST"])
@login_required
@role_required("teacher")
def delete_question(exam_id, question_id):
    db = get_db()
    exam = db.execute("SELECT * FROM exams WHERE id = ? AND teacher_id = ?", (exam_id, session["user_id"])).fetchone()
    if not exam:
        flash("Unauthorized action.", "danger")
        return redirect(url_for("dashboard"))
        
    db.execute("DELETE FROM questions WHERE id = ? AND exam_id = ?", (question_id, exam_id))
    db.commit()
    flash("Question deleted successfully.", "success")
    return redirect(url_for("manage_questions", exam_id=exam_id))

@app.route("/exams/<int:exam_id>/take", methods=["GET", "POST"])
@login_required
@role_required("student")
def take_exam(exam_id):
    db = get_db()
    exam = db.execute("SELECT * FROM exams WHERE id = ?", (exam_id,)).fetchone()
    if not exam:
        flash("Exam not found.", "danger")
        return redirect(url_for("dashboard"))
        
    existing = db.execute("SELECT * FROM submissions WHERE student_id = ? AND exam_id = ?", (session["user_id"], exam_id)).fetchone()
    if existing:
        flash("You have already submitted this exam.", "warning")
        return redirect(url_for("dashboard"))
        
    questions = db.execute("SELECT id, question_text, option_a, option_b, option_c, option_d FROM questions WHERE exam_id = ?", (exam_id,)).fetchall()
    
    if not questions:
        flash("This exam has no questions yet and cannot be taken.", "warning")
        return redirect(url_for("dashboard"))

    if request.method == "GET":
        session[f"exam_start_{exam_id}"] = time.time()
        return render_template("take_exam.html", exam=exam, questions=questions)
        
    if request.method == "POST":
        # --- Pre-emptive Double-Submission Check ---
        existing_post = db.execute("SELECT * FROM submissions WHERE student_id = ? AND exam_id = ?", (session["user_id"], exam_id)).fetchone()
        if existing_post:
            flash("Security Warning: Duplicate submission blocked.", "danger")
            return redirect(url_for("dashboard"))

        # --- Server-Side Timer Validation (Anti-Cheat Engine) ---
        start_time = session.get(f"exam_start_{exam_id}")
        current_time = time.time()
        allowed_duration = (exam["duration"] * 60) + 30  # Includes a 30s network buffer
        
        if start_time is None:
            flash("Session expired or invalid exam initialization. Submission rejected.", "danger")
            return redirect(url_for("dashboard"))
            
        elapsed_seconds = current_time - start_time
        if elapsed_seconds > allowed_duration:
            flash(f"Submission rejected: Time limit exceeded by {int(elapsed_seconds - allowed_duration)}s.", "danger")
            return redirect(url_for("dashboard"))
            
        session.pop(f"exam_start_{exam_id}", None)
        
        # --- Automated MCQ Grading Engine ---
        student_answers = request.form
        db_questions = db.execute("SELECT id, correct_option FROM questions WHERE exam_id = ?", (exam_id,)).fetchall()
        
        correct_count = 0
        total_q = len(db_questions)
        
        for q in db_questions:
            q_id = str(q["id"])
            student_ans = student_answers.get(f"q_{q_id}")
            if student_ans == q["correct_option"]:
                correct_count += 1
                
        score = int((correct_count / total_q) * exam["total_marks"]) if total_q > 0 else 0
        
        try:
            db.execute(
                "INSERT INTO submissions (student_id, exam_id, score) VALUES (?, ?, ?)",
                (session["user_id"], exam_id, score)
            )
            db.commit()
            flash(f"{score}/{exam['total_marks']}", "exam_result")
        except sqlite3.IntegrityError:
            flash("Security Warning: Duplicate submission blocked.", "danger")
            
        return redirect(url_for("dashboard"))

@app.route("/gradebook/<int:exam_id>")
@login_required
@role_required("teacher")
def gradebook(exam_id):
    db = get_db()
    exam = db.execute("SELECT * FROM exams WHERE id = ? AND teacher_id = ?", (exam_id, session["user_id"])).fetchone()
    if not exam:
        flash("Unauthorized or exam not found.", "danger")
        return redirect(url_for("dashboard"))
    search = request.args.get("search", "").strip()
    if search:
        submissions = db.execute('''
            SELECT s.*, u.name as student_name, u.email as student_email, u.roll as student_roll, u.department as student_dept
            FROM submissions s 
            JOIN users u ON s.student_id = u.id 
            WHERE s.exam_id = ? AND (u.name LIKE ? OR u.email LIKE ? OR u.roll LIKE ?)
            ORDER BY s.submitted_at DESC
        ''', (exam_id, f"%{search}%", f"%{search}%", f"%{search}%")).fetchall()
    else:
        submissions = db.execute('''
            SELECT s.*, u.name as student_name, u.email as student_email, u.roll as student_roll, u.department as student_dept
            FROM submissions s 
            JOIN users u ON s.student_id = u.id 
            WHERE s.exam_id = ?
            ORDER BY s.submitted_at DESC
        ''', (exam_id,)).fetchall()
        
    return render_template("gradebook.html", exam=exam, submissions=submissions, search_query=search)

@app.route("/exams/<int:exam_id>/toggle-status", methods=["POST"])
@login_required
@role_required("teacher")
def toggle_exam_status(exam_id):
    db = get_db()
    exam = db.execute("SELECT * FROM exams WHERE id = ? AND teacher_id = ?", (exam_id, session["user_id"])).fetchone()
    if not exam:
        flash("Unauthorized or exam not found.", "danger")
        return redirect(url_for("dashboard"))
        
    # Toggle public state (is_public: 0 to 1, or 1 to 0)
    new_state = 1 if exam["is_public"] == 0 else 0
    db.execute("UPDATE exams SET is_public = ? WHERE id = ?", (new_state, exam_id))
    db.commit()
    
    status_msg = "Exam successfully deployed to students!" if new_state == 1 else "Exam reverted to draft (undeployed)."
    flash(status_msg, "success")
    return redirect(url_for("dashboard"))

if __name__ == "__main__":
    if not os.path.exists(DATABASE):
        init_db()
    app.run(debug=True, host="0.0.0.0", port=5000)
