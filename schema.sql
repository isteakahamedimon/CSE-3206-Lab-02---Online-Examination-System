-- Enable Foreign Key constraints in SQLite
PRAGMA foreign_keys = ON;

-- Users table (supports Students and Teachers)
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    email TEXT UNIQUE NOT NULL,
    password TEXT NOT NULL,
    role TEXT CHECK(role IN ('student', 'teacher')) NOT NULL,
    roll TEXT,             -- For Students
    teacher_uid TEXT,     -- For Teachers
    department TEXT        -- Academic Department (e.g. CSE, EEE, ME)
);

-- Exams table (created by Teachers)
CREATE TABLE IF NOT EXISTS exams (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    teacher_id INTEGER,
    title TEXT NOT NULL,
    duration INTEGER NOT NULL, -- in minutes
    total_marks INTEGER NOT NULL,
    is_public INTEGER DEFAULT 0, -- 0 for Draft/Undeployed, 1 for Deployed
    target_dept TEXT,            -- target department filter (e.g. CSE)
    target_roll_pattern TEXT,    -- target student roll pattern (e.g. 2203%)
    FOREIGN KEY(teacher_id) REFERENCES users(id) ON DELETE CASCADE
);

-- Questions table (linked to Exams)
CREATE TABLE IF NOT EXISTS questions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    exam_id INTEGER,
    question_text TEXT NOT NULL,
    option_a TEXT NOT NULL,
    option_b TEXT NOT NULL,
    option_c TEXT NOT NULL,
    option_d TEXT NOT NULL,
    correct_option TEXT CHECK(correct_option IN ('A', 'B', 'C', 'D')) NOT NULL,
    FOREIGN KEY(exam_id) REFERENCES exams(id) ON DELETE CASCADE
);

-- Submissions table with composite unique constraint for single-submission policy
CREATE TABLE IF NOT EXISTS submissions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id INTEGER,
    exam_id INTEGER,
    score INTEGER NOT NULL,
    submitted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(student_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY(exam_id) REFERENCES exams(id) ON DELETE CASCADE,
    UNIQUE(student_id, exam_id)
);

